"""Page-aware semantic retrieval over isolated document indexes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.config import settings
from app.services.document_service import get_document
from app.services.embedding_service import embed_query
from app.services.vector_service import InvalidVectorDataError, load_document_index


class RetrievalServiceError(RuntimeError):
    """Base exception for expected retrieval failures."""


class InvalidSearchRequestError(RetrievalServiceError):
    """Raised when a direct service caller supplies invalid search input."""


class DocumentNotReadyError(RetrievalServiceError):
    """Raised when retrieval is requested before indexing is complete."""


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One ranked chunk returned by semantic retrieval."""

    rank: int
    chunk_id: str
    excerpt: str
    similarity_score: float
    page_number: int


def _validate_request(query: str, top_k: int) -> str:
    if not isinstance(query, str) or not query.strip():
        raise InvalidSearchRequestError("Search query cannot be empty.")
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise InvalidSearchRequestError("top_k must be an integer.")
    if top_k < 1 or top_k > settings.retrieval_max_top_k:
        raise InvalidSearchRequestError(
            f"top_k must be between 1 and {settings.retrieval_max_top_k}."
        )
    return query.strip()


def search_document(
    document_id: str,
    query: str,
    top_k: int | None = None,
) -> list[SearchResult]:
    """Return the most similar chunks from one document only."""

    requested_top_k = (
        settings.retrieval_default_top_k if top_k is None else top_k
    )
    validated_query = _validate_request(query, requested_top_k)

    document = get_document(document_id)
    if document.status != "ready":
        raise DocumentNotReadyError("Document is not ready for search.")

    loaded = load_document_index(document_id)
    query_vector = np.asarray(embed_query(validated_query), dtype=np.float32)
    expected_shape = (loaded.metadata.embedding_dimension,)
    if query_vector.shape != expected_shape or not np.isfinite(query_vector).all():
        raise InvalidVectorDataError(
            f"Query embedding must have shape {expected_shape} and finite values."
        )

    norm = float(np.linalg.norm(query_vector))
    if not np.isclose(norm, 1.0, rtol=1e-4, atol=1e-5):
        raise InvalidVectorDataError("Query embedding must be normalized.")

    result_count = min(requested_top_k, loaded.metadata.number_of_vectors)
    scores, row_ids = loaded.index.search(
        np.ascontiguousarray(query_vector.reshape(1, -1)),
        result_count,
    )

    results: list[SearchResult] = []
    for rank, (score, row_id) in enumerate(zip(scores[0], row_ids[0]), start=1):
        if row_id < 0 or row_id >= len(loaded.metadata.rows):
            raise InvalidVectorDataError("FAISS returned an invalid vector row.")
        row = loaded.metadata.rows[int(row_id)]
        page_number = row.metadata.get("page_number")
        if not isinstance(page_number, int) or isinstance(page_number, bool) or page_number < 1:
            raise InvalidVectorDataError("Vector row has invalid page metadata.")

        results.append(
            SearchResult(
                rank=rank,
                chunk_id=row.chunk_id,
                excerpt=row.text,
                similarity_score=max(-1.0, min(1.0, float(score))),
                page_number=page_number,
            )
        )
    return results
