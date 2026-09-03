"""Document summary API routes."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.document_service import DocumentNotFoundError, DocumentStorageError
from app.services.llm_service import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.services.summary_service import (
    SummaryDocumentNotReadyError,
    SummaryServiceError,
    summarize_document,
)


router = APIRouter(prefix="/api", tags=["summaries"])


class SummaryRequest(BaseModel):
    document_id: UUID
    detail: Literal["brief", "detailed"] = "brief"


class SummaryResponse(BaseModel):
    document_id: UUID
    detail: Literal["brief", "detailed"]
    summary: str


@router.post("/summary", response_model=SummaryResponse)
def create_document_summary(request: SummaryRequest) -> SummaryResponse:
    """Generate a brief or detailed grounded document summary."""

    try:
        result = summarize_document(str(request.document_id), request.detail)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SummaryDocumentNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LLMRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except (LLMProviderError, LLMTimeoutError, LLMResponseError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except (DocumentStorageError, SummaryServiceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return SummaryResponse(
        document_id=request.document_id,
        detail=result.detail,
        summary=result.summary,
    )
