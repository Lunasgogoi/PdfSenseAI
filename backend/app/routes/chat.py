"""Grounded RAG chat API routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.services.document_service import DocumentNotFoundError, DocumentStorageError
from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingGenerationError,
)
from app.services.llm_service import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.services.rag_service import Citation, answer_question
from app.services.retrieval_service import DocumentNotReadyError
from app.services.vector_service import VectorIndexNotFoundError, VectorServiceError


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
def chat_with_document(request: ChatRequest) -> ChatResponse:
    """Answer a question using only evidence from one ready document."""

    try:
        result = answer_question(str(request.document_id), request.query)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (DocumentNotReadyError, VectorIndexNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (EmbeddingConfigurationError, LLMConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LLMRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except (EmbeddingGenerationError, LLMProviderError, LLMTimeoutError, LLMResponseError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except (DocumentStorageError, VectorServiceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return ChatResponse(
        document_id=request.document_id,
        answer=result.answer,
        citations=[_citation_response(citation) for citation in result.citations],
    )
