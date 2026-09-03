"""Semantic document search API routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.services.document_service import DocumentNotFoundError, DocumentStorageError
from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingGenerationError,
)
from app.services.retrieval_service import (
    DocumentNotReadyError,
    InvalidSearchRequestError,
    SearchResult,
    search_document,
)
from app.services.vector_service import VectorIndexNotFoundError, VectorServiceError


router = APIRouter(prefix="/api/documents", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    top_k: int = Field(
        default=settings.retrieval_default_top_k,
        ge=1,
        le=settings.retrieval_max_top_k,
    )

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Search query cannot be empty.")
        return stripped


class SearchResultResponse(BaseModel):
    rank: int = Field(ge=1)
    chunk_id: str
    excerpt: str
    similarity_score: float = Field(ge=-1.0, le=1.0)
    page_number: int = Field(ge=1)


class SearchResponse(BaseModel):
    document_id: UUID
    query: str
    top_k: int = Field(ge=1)
    result_count: int = Field(ge=0)
    results: list[SearchResultResponse]


def _result_response(result: SearchResult) -> SearchResultResponse:
    return SearchResultResponse(
        rank=result.rank,
        chunk_id=result.chunk_id,
        excerpt=result.excerpt,
        similarity_score=result.similarity_score,
        page_number=result.page_number,
    )


@router.post("/{document_id}/search", response_model=SearchResponse)
def search_document_chunks(document_id: UUID, request: SearchRequest) -> SearchResponse:
    """Search one ready document using normalized cosine similarity."""

    try:
        results = search_document(str(document_id), request.query, request.top_k)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (DocumentNotReadyError, VectorIndexNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except EmbeddingGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except InvalidSearchRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (DocumentStorageError, VectorServiceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return SearchResponse(
        document_id=document_id,
        query=request.query,
        top_k=request.top_k,
        result_count=len(results),
        results=[_result_response(result) for result in results],
    )
