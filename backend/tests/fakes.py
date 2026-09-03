"""In-memory account repository helpers for API integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI

from app.core.config import settings
from app.core.dependencies import get_current_user, get_repository
from app.services.account_service import (
    AuthenticationError,
    ChatTurnRecord,
    QuotaExceededError,
    QuotaSnapshot,
    UserAlreadyExistsError,
    UserRecord,
)
from app.services.document_service import DocumentManifest, DocumentNotFoundError

TEST_USER = UserRecord(
    user_id="11111111-1111-4111-8111-111111111111",
    email="reader@example.com",
    password_hash="unused-in-authenticated-route-tests",
    created_at=datetime.now(UTC),
    document_limit=100,
    daily_ai_limit=1_000,
)


class FakeAccountRepository:
    def __init__(self) -> None:
        self.users: dict[str, UserRecord] = {TEST_USER.user_id: TEST_USER}
        self.documents: dict[str, tuple[str, DocumentManifest]] = {}
        self.chat_turns: dict[tuple[str, str], list[ChatTurnRecord]] = {}
        self.document_counts: dict[str, int] = {TEST_USER.user_id: 0}
        self.ai_counts: dict[str, int] = {TEST_USER.user_id: 0}

    def ping(self) -> None:
        return None

    def create_user(self, email: str, password_hash: str) -> UserRecord:
        if self.find_user_by_email(email):
            raise UserAlreadyExistsError("An account with this email already exists.")
        user = UserRecord(
            user_id=str(uuid4()),
            email=email,
            password_hash=password_hash,
            created_at=datetime.now(UTC),
            document_limit=settings.user_document_limit,
            daily_ai_limit=settings.user_daily_ai_limit,
        )
        self.users[user.user_id] = user
        self.document_counts[user.user_id] = 0
        self.ai_counts[user.user_id] = 0
        return user

    def find_user_by_email(self, email: str) -> UserRecord | None:
        return next((user for user in self.users.values() if user.email == email), None)

    def find_user_by_id(self, user_id: str) -> UserRecord | None:
        return self.users.get(user_id)

    def _user(self, user_id: str) -> UserRecord:
        user = self.find_user_by_id(user_id)
        if user is None:
            raise AuthenticationError("Authentication is required.")
        return user

    def get_quota(self, user_id: str) -> QuotaSnapshot:
        user = self._user(user_id)
        used = self.ai_counts.get(user_id, 0)
        return QuotaSnapshot(
            document_limit=user.document_limit,
            documents_used=self.document_counts.get(user_id, 0),
            daily_ai_limit=user.daily_ai_limit,
            daily_ai_used=used,
            daily_ai_remaining=max(0, user.daily_ai_limit - used),
            daily_reset_date=datetime.now(UTC).date().isoformat(),
        )

    def reserve_document_slot(self, user_id: str) -> None:
        user = self._user(user_id)
        used = self.document_counts.get(user_id, 0)
        if used >= user.document_limit:
            raise QuotaExceededError("Your document quota has been reached.")
        self.document_counts[user_id] = used + 1

    def release_document_slot(self, user_id: str) -> None:
        self.document_counts[user_id] = max(
            0,
            self.document_counts.get(user_id, 0) - 1,
        )

    def add_document(self, user_id: str, manifest: DocumentManifest) -> None:
        self._user(user_id)
        self.documents[manifest.document_id] = (user_id, manifest)

    def list_owned_document_ids(self, user_id: str) -> list[str]:
        return [
            document_id
            for document_id, (owner_id, _) in reversed(self.documents.items())
            if owner_id == user_id
        ]

    def assert_document_owner(self, user_id: str, document_id: str) -> None:
        owned = self.documents.get(document_id)
        if owned is None or owned[0] != user_id:
            raise DocumentNotFoundError("Document not found.")

    def remove_document(self, user_id: str, document_id: str) -> None:
        self.assert_document_owner(user_id, document_id)
        del self.documents[document_id]
        self.release_document_slot(user_id)
        self.chat_turns.pop((user_id, document_id), None)

    def consume_ai_request(self, user_id: str) -> QuotaSnapshot:
        user = self._user(user_id)
        used = self.ai_counts.get(user_id, 0)
        if used >= user.daily_ai_limit:
            raise QuotaExceededError("Your daily AI request quota has been reached.")
        self.ai_counts[user_id] = used + 1
        return self.get_quota(user_id)

    def add_chat_turn(
        self,
        user_id: str,
        document_id: str,
        query: str,
        answer: str,
        citations: list[dict[str, object]],
    ) -> ChatTurnRecord:
        turn = ChatTurnRecord(
            turn_id=str(uuid4()),
            document_id=document_id,
            query=query,
            answer=answer,
            citations=citations,
            created_at=datetime.now(UTC),
        )
        self.chat_turns.setdefault((user_id, document_id), []).append(turn)
        return turn

    def list_chat_turns(
        self,
        user_id: str,
        document_id: str,
    ) -> list[ChatTurnRecord]:
        return list(self.chat_turns.get((user_id, document_id), []))

    def clear_chat_turns(self, user_id: str, document_id: str) -> None:
        self.chat_turns.pop((user_id, document_id), None)


def install_test_auth(app: FastAPI) -> FakeAccountRepository:
    repository = FakeAccountRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    return repository


def remove_test_auth(app: FastAPI) -> None:
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_repository, None)
