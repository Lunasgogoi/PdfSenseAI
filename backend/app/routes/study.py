"""Study-material generation API routes."""

from typing import Self
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from app.core.config import settings
from app.core.dependencies import CurrentUser, Repository
from app.services.study_service import (
    MCQ,
    Flashcard,
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
def create_study_materials(
    request: StudyRequest,
    user: CurrentUser,
    repository: Repository,
) -> StudyResponse:
    """Generate validated MCQs and flashcards for a ready document."""

    document_id = str(request.document_id)
    repository.assert_document_owner(user.user_id, document_id)
    repository.consume_ai_request(user.user_id)
    materials = generate_study_materials(
        document_id,
        request.mcq_count,
        request.flashcard_count,
    )

    return StudyResponse(
        document_id=request.document_id,
        mcqs=materials.mcqs,
        flashcards=materials.flashcards,
    )
