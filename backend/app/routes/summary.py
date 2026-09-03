"""Document summary API routes."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.dependencies import CurrentUser, Repository
from app.services.summary_service import summarize_document

router = APIRouter(prefix="/api", tags=["summaries"])


class SummaryRequest(BaseModel):
    document_id: UUID
    detail: Literal["brief", "detailed"] = "brief"


class SummaryResponse(BaseModel):
    document_id: UUID
    detail: Literal["brief", "detailed"]
    summary: str


@router.post("/summary", response_model=SummaryResponse)
def create_document_summary(
    request: SummaryRequest,
    user: CurrentUser,
    repository: Repository,
) -> SummaryResponse:
    """Generate a brief or detailed grounded document summary."""

    document_id = str(request.document_id)
    repository.assert_document_owner(user.user_id, document_id)
    repository.consume_ai_request(user.user_id)
    result = summarize_document(document_id, request.detail)

    return SummaryResponse(
        document_id=request.document_id,
        detail=result.detail,
        summary=result.summary,
    )
