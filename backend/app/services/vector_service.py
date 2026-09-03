"""Per-document FAISS index creation and persistence."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import UUID

import numpy as np

from app.core.config import settings
from app.services.embedding_service import embed_documents


INDEX_FILENAME = "index.faiss"
METADATA_FILENAME = "metadata.json"
METADATA_SCHEMA_VERSION = 1


class VectorServiceError(RuntimeError):
    """Base exception for expected vector-index failures."""


class InvalidVectorDataError(VectorServiceError):
    """Raised when chunks, vectors, or persisted metadata are inconsistent."""


class VectorIndexNotFoundError(VectorServiceError):
    """Raised when a document has no persisted vector index."""


class VectorStorageError(VectorServiceError):
    """Raised when a FAISS workspace cannot be read or written."""


@dataclass(frozen=True, slots=True)
class VectorRow:
    """Metadata associated with one FAISS row."""

    row_id: int
    chunk_id: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class VectorIndexMetadata:
    """The persisted contract required to safely reload an index."""

    schema_version: int
    document_id: str
    model_name: str
    embedding_dimension: int
    index_type: str
    metric: str
    normalized: bool
    number_of_vectors: int
    created_at: str
    rows: list[VectorRow]


@dataclass(frozen=True, slots=True)
class LoadedVectorIndex:
    """A validated FAISS index and its row-to-chunk mapping."""

    index: Any
    metadata: VectorIndexMetadata


def _normalize_document_id(document_id: str) -> str:
    try:
        return str(UUID(document_id))
    except (ValueError, AttributeError) as exc:
        raise VectorIndexNotFoundError("Vector index not found.") from exc


def vector_workspace(document_id: str) -> Path:
    """Resolve a vector path without accepting arbitrary path components."""

    normalized_id = _normalize_document_id(document_id)
    vector_root = settings.vector_store_dir.resolve()
    workspace = (vector_root / normalized_id).resolve()
    if workspace.parent != vector_root:
        raise VectorStorageError("Could not resolve a safe vector workspace.")
    return workspace


def _validated_rows(
    document_id: str,
    chunks: Sequence[Mapping[str, object]],
) -> list[VectorRow]:
    if not chunks:
        raise InvalidVectorDataError("At least one document chunk is required.")

    rows: list[VectorRow] = []
    seen_chunk_ids: set[str] = set()
    for row_id, chunk in enumerate(chunks):
        chunk_id = chunk.get("chunk_id")
        text = chunk.get("text")
        metadata = chunk.get("metadata")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise InvalidVectorDataError("Every chunk must have a chunk_id.")
        if chunk_id in seen_chunk_ids:
            raise InvalidVectorDataError("Chunk IDs must be unique within a document.")
        if not isinstance(text, str) or not text.strip():
            raise InvalidVectorDataError("Every chunk must contain text.")
        if not isinstance(metadata, Mapping):
            raise InvalidVectorDataError("Every chunk must contain metadata.")

        expected_chunk_id = f"{document_id}:{row_id}"
        if chunk_id != expected_chunk_id:
            raise InvalidVectorDataError(
                "Chunk ordering does not match the document workspace."
            )

        rows.append(
            VectorRow(
                row_id=row_id,
                chunk_id=chunk_id,
                text=text,
                metadata=dict(metadata),
            )
        )
        seen_chunk_ids.add(chunk_id)
    return rows


def _write_metadata_atomic(path: Path, metadata: VectorIndexMetadata) -> None:
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    payload = asdict(metadata)
    try:
        with temporary_path.open("x", encoding="utf-8") as output_file:
            json.dump(payload, output_file, ensure_ascii=False, indent=2)
            output_file.write("\n")
        temporary_path.replace(path)
    except Exception as exc:
        temporary_path.unlink(missing_ok=True)
        raise VectorStorageError("Could not persist vector metadata.") from exc


def build_document_index(
    document_id: str,
    chunks: Sequence[Mapping[str, object]],
) -> VectorIndexMetadata:
    """Embed chunks and persist an isolated inner-product FAISS index."""

    normalized_id = _normalize_document_id(document_id)
    rows = _validated_rows(normalized_id, chunks)
    vectors = np.asarray(
        embed_documents([row.text for row in rows]),
        dtype=np.float32,
    )
    expected_shape = (len(rows), settings.embedding_dimension)
    if vectors.shape != expected_shape or not np.isfinite(vectors).all():
        raise InvalidVectorDataError(
            f"Embedding matrix must have shape {expected_shape} and finite values."
        )

    norms = np.linalg.norm(vectors, axis=1)
    if not np.allclose(norms, 1.0, rtol=1e-4, atol=1e-5):
        raise InvalidVectorDataError("FAISS requires normalized document embeddings.")

    try:
        import faiss
    except ImportError as exc:
        raise VectorStorageError("FAISS is not installed.") from exc

    workspace = vector_workspace(normalized_id)
    created_workspace = False
    temporary_index_path = workspace / f"{INDEX_FILENAME}.tmp"
    try:
        settings.vector_store_dir.mkdir(parents=True, exist_ok=True)
        workspace.mkdir(exist_ok=False)
        created_workspace = True

        index = faiss.IndexFlatIP(settings.embedding_dimension)
        index.add(np.ascontiguousarray(vectors))
        metadata = VectorIndexMetadata(
            schema_version=METADATA_SCHEMA_VERSION,
            document_id=normalized_id,
            model_name=settings.embedding_model_name,
            embedding_dimension=settings.embedding_dimension,
            index_type="IndexFlatIP",
            metric="inner_product",
            normalized=True,
            number_of_vectors=len(rows),
            created_at=datetime.now(UTC).isoformat(),
            rows=rows,
        )

        faiss.write_index(index, str(temporary_index_path))
        temporary_index_path.replace(workspace / INDEX_FILENAME)
        _write_metadata_atomic(workspace / METADATA_FILENAME, metadata)
        return metadata
    except VectorServiceError:
        if created_workspace:
            shutil.rmtree(workspace, ignore_errors=True)
        raise
    except Exception as exc:
        if created_workspace:
            shutil.rmtree(workspace, ignore_errors=True)
        raise VectorStorageError("Could not build the vector index.") from exc


def _load_metadata(path: Path) -> VectorIndexMetadata:
    try:
        with path.open("r", encoding="utf-8") as input_file:
            payload = json.load(input_file)
        payload["rows"] = [VectorRow(**row) for row in payload["rows"]]
        return VectorIndexMetadata(**payload)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise VectorStorageError("Could not read vector metadata.") from exc


def _validate_loaded_metadata(
    document_id: str,
    metadata: VectorIndexMetadata,
) -> None:
    if metadata.schema_version != METADATA_SCHEMA_VERSION:
        raise InvalidVectorDataError("Unsupported vector metadata version.")
    if metadata.document_id != document_id:
        raise InvalidVectorDataError("Vector metadata belongs to another document.")
    if metadata.model_name != settings.embedding_model_name:
        raise InvalidVectorDataError("Vector index uses a different embedding model.")
    if metadata.embedding_dimension != settings.embedding_dimension:
        raise InvalidVectorDataError("Vector index has an unexpected dimension.")
    if metadata.index_type != "IndexFlatIP" or metadata.metric != "inner_product":
        raise InvalidVectorDataError("Vector index has an unsupported index type.")
    if not metadata.normalized:
        raise InvalidVectorDataError("Vector index metadata is not normalized.")
    if metadata.number_of_vectors != len(metadata.rows):
        raise InvalidVectorDataError("Vector row metadata count is inconsistent.")
    if any(row.row_id != row_id for row_id, row in enumerate(metadata.rows)):
        raise InvalidVectorDataError("Vector row metadata is not contiguous.")


def load_document_index(document_id: str) -> LoadedVectorIndex:
    """Reload and validate a document index from disk."""

    normalized_id = _normalize_document_id(document_id)
    workspace = vector_workspace(normalized_id)
    index_path = workspace / INDEX_FILENAME
    metadata_path = workspace / METADATA_FILENAME
    if not index_path.is_file() or not metadata_path.is_file():
        raise VectorIndexNotFoundError("Vector index not found.")

    metadata = _load_metadata(metadata_path)
    _validate_loaded_metadata(normalized_id, metadata)
    try:
        import faiss

        index = faiss.read_index(str(index_path))
    except Exception as exc:
        raise VectorStorageError("Could not read the FAISS index.") from exc

    if index.d != metadata.embedding_dimension:
        raise InvalidVectorDataError("FAISS index dimension is inconsistent.")
    if index.ntotal != metadata.number_of_vectors:
        raise InvalidVectorDataError("FAISS index row count is inconsistent.")
    if type(index).__name__ != metadata.index_type:
        raise InvalidVectorDataError("FAISS index type is inconsistent.")
    return LoadedVectorIndex(index=index, metadata=metadata)


def remove_vector_workspace(document_id: str) -> None:
    """Remove a known vector workspace after failed processing."""

    workspace = vector_workspace(document_id)
    if workspace.exists() and workspace.parent == settings.vector_store_dir.resolve():
        shutil.rmtree(workspace, ignore_errors=True)
