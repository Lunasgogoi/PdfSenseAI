"""Filesystem-backed document workspace management."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.core.config import settings

MANIFEST_FILENAME = "manifest.json"
CHUNKS_FILENAME = "chunks.json"
SOURCE_FILENAME = "source.pdf"


class DocumentNotFoundError(FileNotFoundError):
    """Raised when a document workspace does not exist."""


class DocumentStorageError(RuntimeError):
    """Raised when persisted document data cannot be read or written."""


@dataclass(frozen=True, slots=True)
class DocumentManifest:
    """Metadata persisted for each uploaded document."""

    document_id: str
    filename: str
    stored_filename: str
    page_count: int
    number_of_chunks: int
    status: str
    created_at: str


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """A validated chunk loaded from a persisted document workspace."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]


def new_document_id() -> str:
    """Return a collision-resistant public identifier."""

    return str(uuid4())


def _normalize_document_id(document_id: str) -> str:
    try:
        return str(UUID(document_id))
    except (ValueError, AttributeError) as exc:
        raise DocumentNotFoundError("Document not found.") from exc


def document_workspace(document_id: str) -> Path:
    """Resolve a document path without accepting arbitrary path components."""

    normalized_id = _normalize_document_id(document_id)
    upload_root = settings.upload_dir.resolve()
    workspace = (upload_root / normalized_id).resolve()
    if workspace.parent != upload_root:
        raise DocumentStorageError("Could not resolve a safe document workspace.")
    return workspace


def create_document_workspace(document_id: str) -> Path:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    workspace = document_workspace(document_id)
    try:
        workspace.mkdir(exist_ok=False)
    except OSError as exc:
        raise DocumentStorageError("Could not create the document workspace.") from exc
    return workspace


def _write_json_atomic(path: Path, payload: object) -> None:
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("x", encoding="utf-8") as output_file:
            json.dump(payload, output_file, ensure_ascii=False, indent=2)
            output_file.write("\n")
        temporary_path.replace(path)
    except Exception as exc:
        temporary_path.unlink(missing_ok=True)
        raise DocumentStorageError(f"Could not write {path.name}.") from exc


def persist_document(
    workspace: Path,
    manifest: DocumentManifest,
    chunks: list[dict[str, object]],
) -> None:
    """Persist ingestion metadata and chunks after successful extraction."""

    _write_json_atomic(workspace / CHUNKS_FILENAME, chunks)
    _write_json_atomic(workspace / MANIFEST_FILENAME, asdict(manifest))


def update_document_status(document_id: str, status: str) -> DocumentManifest:
    """Atomically update a document's persisted processing status."""

    if not status.strip():
        raise DocumentStorageError("Document status cannot be empty.")
    workspace = document_workspace(document_id)
    manifest = get_document(document_id)
    updated_manifest = replace(manifest, status=status)
    _write_json_atomic(workspace / MANIFEST_FILENAME, asdict(updated_manifest))
    return updated_manifest


def _load_manifest(path: Path) -> DocumentManifest:
    try:
        with path.open("r", encoding="utf-8") as input_file:
            return DocumentManifest(**json.load(input_file))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise DocumentStorageError("Could not read document metadata.") from exc


def get_document(document_id: str) -> DocumentManifest:
    manifest_path = document_workspace(document_id) / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise DocumentNotFoundError("Document not found.")
    return _load_manifest(manifest_path)


def load_document_chunks(document_id: str) -> list[DocumentChunk]:
    """Load and validate the page-aware chunks for one document."""

    normalized_id = _normalize_document_id(document_id)
    manifest = get_document(normalized_id)
    chunks_path = document_workspace(normalized_id) / CHUNKS_FILENAME
    try:
        with chunks_path.open("r", encoding="utf-8") as input_file:
            payload = json.load(input_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise DocumentStorageError("Could not read document chunks.") from exc

    if not isinstance(payload, list) or len(payload) != manifest.number_of_chunks:
        raise DocumentStorageError("Document chunk count is inconsistent.")

    chunks: list[DocumentChunk] = []
    for chunk_index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise DocumentStorageError("Document chunk data is invalid.")
        chunk_id = item.get("chunk_id")
        text = item.get("text")
        metadata = item.get("metadata")
        expected_chunk_id = f"{normalized_id}:{chunk_index}"
        if chunk_id != expected_chunk_id:
            raise DocumentStorageError("Document chunk ordering is inconsistent.")
        if not isinstance(text, str) or not text.strip():
            raise DocumentStorageError("Document chunk text is invalid.")
        if not isinstance(metadata, dict):
            raise DocumentStorageError("Document chunk metadata is invalid.")
        page_number = metadata.get("page_number")
        if (
            not isinstance(page_number, int)
            or isinstance(page_number, bool)
            or page_number < 1
            or page_number > manifest.page_count
        ):
            raise DocumentStorageError("Document chunk page metadata is invalid.")
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                text=text,
                metadata=dict(metadata),
            )
        )
    return chunks


def list_documents() -> list[DocumentManifest]:
    if not settings.upload_dir.exists():
        return []

    documents = [
        _load_manifest(manifest_path)
        for manifest_path in settings.upload_dir.glob(f"*/{MANIFEST_FILENAME}")
    ]
    return sorted(documents, key=lambda document: document.created_at, reverse=True)


def delete_document(document_id: str) -> None:
    """Delete source artifacts and any future vector index for a document."""

    workspace = document_workspace(document_id)
    if not (workspace / MANIFEST_FILENAME).is_file():
        raise DocumentNotFoundError("Document not found.")

    vector_root = settings.vector_store_dir.resolve()
    vector_workspace = (vector_root / _normalize_document_id(document_id)).resolve()
    if vector_workspace.parent != vector_root:
        raise DocumentStorageError("Could not resolve a safe vector workspace.")

    try:
        shutil.rmtree(workspace)
        if vector_workspace.exists():
            shutil.rmtree(vector_workspace)
    except OSError as exc:
        raise DocumentStorageError("Could not delete the document.") from exc


def remove_document_workspace(workspace: Path) -> None:
    """Remove a known workspace after an interrupted ingestion attempt."""

    if workspace.exists() and workspace.parent == settings.upload_dir.resolve():
        shutil.rmtree(workspace, ignore_errors=True)
