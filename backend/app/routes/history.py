"""Persistent per-document chat-history endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.core.dependencies import CurrentUser, Repository
from app.services.account_service import ChatTurnRecord

router = APIRouter(prefix="/api/documents", tags=["chat history"])


class HistoryCitationResponse(BaseModel):
    chunk_id: str
    page_number: int = Field(ge=1)
    excerpt: str
    similarity_score: float = Field(ge=-1.0, le=1.0)


class ChatTurnResponse(BaseModel):
    turn_id: UUID
    document_id: UUID
    query: str
    answer: str
    citations: list[HistoryCitationResponse]
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    document_id: UUID
    turns: list[ChatTurnResponse]


def _turn_response(turn: ChatTurnRecord) -> ChatTurnResponse:
    return ChatTurnResponse(
        turn_id=UUID(turn.turn_id),
        document_id=UUID(turn.document_id),
        query=turn.query,
        answer=turn.answer,
        citations=[HistoryCitationResponse(**citation) for citation in turn.citations],
        created_at=turn.created_at,
    )


@router.get("/{document_id}/chat-history", response_model=ChatHistoryResponse)
def get_chat_history(
    document_id: UUID,
    user: CurrentUser,
    repository: Repository,
) -> ChatHistoryResponse:
    normalized_id = str(document_id)
    repository.assert_document_owner(user.user_id, normalized_id)
    turns = repository.list_chat_turns(user.user_id, normalized_id)
    return ChatHistoryResponse(
        document_id=document_id,
        turns=[_turn_response(turn) for turn in turns],
    )


@router.delete("/{document_id}/chat-history", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_history(
    document_id: UUID,
    user: CurrentUser,
    repository: Repository,
) -> Response:
    normalized_id = str(document_id)
    repository.assert_document_owner(user.user_id, normalized_id)
    repository.clear_chat_turns(user.user_id, normalized_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
