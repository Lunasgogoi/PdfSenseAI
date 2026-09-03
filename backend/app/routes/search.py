"""Semantic document search API routes."""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.core.dependencies import CurrentUser, Repository
from app.services.retrieval_service import (
    SearchResult,
    search_document,
)

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
def search_document_chunks(
    document_id: UUID,
    request: SearchRequest,
    user: CurrentUser,
    repository: Repository,
) -> SearchResponse:
    """Search one ready document using normalized cosine similarity."""

    normalized_id = str(document_id)
    repository.assert_document_owner(user.user_id, normalized_id)
    repository.consume_ai_request(user.user_id)
    results = search_document(normalized_id, request.query, request.top_k)

    return SearchResponse(
        document_id=document_id,
        query=request.query,
        top_k=request.top_k,
        result_count=len(results),
        results=[_result_response(result) for result in results],
    )
