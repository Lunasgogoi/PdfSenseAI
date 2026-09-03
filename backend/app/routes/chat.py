"""Grounded RAG chat API routes."""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.core.dependencies import CurrentUser, Repository
from app.services.rag_service import Citation, answer_question

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    document_id: UUID
    query: str = Field(min_length=1, max_length=4_000)

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Question cannot be empty.")
        return stripped


class CitationResponse(BaseModel):
    chunk_id: str
    page_number: int = Field(ge=1)
    excerpt: str
    similarity_score: float = Field(ge=-1.0, le=1.0)


class ChatResponse(BaseModel):
    document_id: UUID
    answer: str
    citations: list[CitationResponse]


def _citation_response(citation: Citation) -> CitationResponse:
    return CitationResponse(
        chunk_id=citation.chunk_id,
        page_number=citation.page_number,
        excerpt=citation.excerpt,
        similarity_score=citation.similarity_score,
    )


@router.post("/chat", response_model=ChatResponse)
def chat_with_document(
    request: ChatRequest,
    user: CurrentUser,
    repository: Repository,
) -> ChatResponse:
    """Answer a question using only evidence from one ready document."""

    document_id = str(request.document_id)
    repository.assert_document_owner(user.user_id, document_id)
    repository.consume_ai_request(user.user_id)
    result = answer_question(document_id, request.query)
    citations = [_citation_response(citation) for citation in result.citations]
    repository.add_chat_turn(
        user.user_id,
        document_id,
        request.query,
        result.answer,
        [citation.model_dump() for citation in citations],
    )

    return ChatResponse(
        document_id=request.document_id,
        answer=result.answer,
        citations=citations,
    )
