"""Study-material generation API routes."""

from typing import Self
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from app.core.config import settings
from app.services.document_service import DocumentNotFoundError, DocumentStorageError
from app.services.llm_service import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.services.study_service import (
    Flashcard,
    MCQ,
    StudyDocumentNotReadyError,
    StudyServiceError,
    generate_study_materials,
)


router = APIRouter(prefix="/api", tags=["study"])


class StudyRequest(BaseModel):
    document_id: UUID
    mcq_count: int = Field(default=5, ge=0, le=settings.study_max_items_per_type)
    flashcard_count: int = Field(
        default=5,
        ge=0,
        le=settings.study_max_items_per_type,
    )

    @model_validator(mode="after")
    def at_least_one_item_is_required(self) -> Self:
        if self.mcq_count == 0 and self.flashcard_count == 0:
            raise ValueError("Request at least one study item.")
        return self


class StudyResponse(BaseModel):
    document_id: UUID
    mcqs: list[MCQ]
    flashcards: list[Flashcard]


@router.post("/study", response_model=StudyResponse)
def create_study_materials(request: StudyRequest) -> StudyResponse:
    """Generate validated MCQs and flashcards for a ready document."""

    try:
        materials = generate_study_materials(
            str(request.document_id),
            request.mcq_count,
            request.flashcard_count,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StudyDocumentNotReadyError as exc:
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
    except (DocumentStorageError, StudyServiceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return StudyResponse(
        document_id=request.document_id,
        mcqs=materials.mcqs,
        flashcards=materials.flashcards,
    )
