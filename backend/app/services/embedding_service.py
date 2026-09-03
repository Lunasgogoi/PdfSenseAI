"""Hosted Mixedbread embedding generation for documents and search queries."""

from __future__ import annotations

from threading import Lock
from typing import Any, Sequence

import numpy as np
from numpy.typing import NDArray

from app.core.config import settings


FloatMatrix = NDArray[np.float32]
FloatVector = NDArray[np.float32]

_client: Any | None = None
_client_lock = Lock()


class EmbeddingServiceError(RuntimeError):
    """Base exception for expected embedding service failures."""


class InvalidEmbeddingInputError(EmbeddingServiceError):
    """Raised when text supplied for embedding is empty or invalid."""


class EmbeddingConfigurationError(EmbeddingServiceError):
    """Raised when hosted embedding access is not configured."""


class EmbeddingGenerationError(EmbeddingServiceError):
    """Raised when the model returns invalid embeddings."""


def _create_embedding_client(provider: str, token: str, timeout: float) -> Any:
    """Construct the Hugging Face client only when first needed."""

    from huggingface_hub import InferenceClient

    return InferenceClient(
        provider=provider,
        api_key=token,
        timeout=timeout,
    )


def get_embedding_client() -> Any:
    """Return the process-wide hosted inference client."""

    global _client
    if _client is not None:
        return _client
    if not settings.hf_token:
        raise EmbeddingConfigurationError(
            "HF_TOKEN is required for hosted embedding inference."
        )

    with _client_lock:
        if _client is None:
            try:
                _client = _create_embedding_client(
                    settings.embedding_provider,
                    settings.hf_token,
                    settings.embedding_timeout_seconds,
                )
            except Exception as exc:
                raise EmbeddingConfigurationError(
                    "Could not configure the Hugging Face inference client."
                ) from exc
    return _client


def clear_embedding_client_cache() -> None:
    """Release the cached API client for tests or controlled reconfiguration."""

    global _client
    with _client_lock:
        _client = None


def _validate_texts(texts: Sequence[str]) -> list[str]:
    if isinstance(texts, (str, bytes)) or len(texts) == 0:
        raise InvalidEmbeddingInputError("At least one text is required.")

    validated: list[str] = []
    for text in texts:
        if not isinstance(text, str) or not text.strip():
            raise InvalidEmbeddingInputError("Embedding text cannot be empty.")
        validated.append(text)
    return validated


def _normalize_and_validate(vectors: object, expected_count: int) -> FloatMatrix:
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim == 1 and expected_count == 1:
        matrix = matrix.reshape(1, -1)

    expected_shape = (expected_count, settings.embedding_dimension)
    if matrix.shape != expected_shape:
        raise EmbeddingGenerationError(
            f"Embedding model returned shape {matrix.shape}; expected {expected_shape}."
        )
    if not np.isfinite(matrix).all():
        raise EmbeddingGenerationError("Embedding model returned non-finite values.")

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms <= np.finfo(np.float32).eps):
        raise EmbeddingGenerationError("Embedding model returned a zero-length vector.")

    return np.asarray(matrix / norms, dtype=np.float32)


def _encode(texts: list[str], *, prompt_name: str | None = None) -> FloatMatrix:
    client = get_embedding_client()
    if settings.embedding_batch_size < 1:
        raise EmbeddingConfigurationError("EMBEDDING_BATCH_SIZE must be positive.")

    request_options: dict[str, object] = {
        "model": settings.embedding_model_name,
        "normalize": True,
        "dimensions": settings.embedding_dimension,
    }
    if prompt_name is not None:
        request_options["prompt_name"] = prompt_name

    batches: list[FloatMatrix] = []
    try:
        for start in range(0, len(texts), settings.embedding_batch_size):
            batch = texts[start : start + settings.embedding_batch_size]
            vectors = client.feature_extraction(batch, **request_options)
            batches.append(_normalize_and_validate(vectors, len(batch)))
    except Exception as exc:
        if isinstance(exc, EmbeddingServiceError):
            raise
        raise EmbeddingGenerationError("Could not generate embeddings.") from exc

    return np.concatenate(batches, axis=0)


def embed_documents(texts: Sequence[str]) -> FloatMatrix:
    """Embed document chunks without applying a query instruction."""

    return _encode(_validate_texts(texts))


def embed_query(query: str) -> FloatVector:
    """Embed a search query using Mixedbread's retrieval prompt."""

    if not isinstance(query, str) or not query.strip():
        raise InvalidEmbeddingInputError("Search query cannot be empty.")
    return _encode([query], prompt_name="query")[0]
