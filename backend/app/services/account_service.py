"""MongoDB-backed users, ownership, quotas, and chat history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.errors import ConfigurationError, DuplicateKeyError, PyMongoError
from pymongo.server_api import ServerApi

from app.core.config import settings
from app.services.document_service import DocumentManifest, DocumentNotFoundError


class AccountServiceError(RuntimeError):
    """Base error for account persistence operations."""


class DatabaseConfigurationError(AccountServiceError):
    """Raised when MongoDB has not been configured."""


class DatabaseUnavailableError(AccountServiceError):
    """Raised when MongoDB cannot complete an operation."""


class UserAlreadyExistsError(AccountServiceError):
    """Raised when an email address is already registered."""


class AuthenticationError(AccountServiceError):
    """Raised when credentials or a session token are invalid."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when supplied login credentials do not match an account."""


class QuotaExceededError(AccountServiceError):
    """Raised when a user has exhausted a persisted quota."""


@dataclass(frozen=True, slots=True)
class UserRecord:
    user_id: str
    email: str
    password_hash: str
    created_at: datetime
    document_limit: int
    daily_ai_limit: int


@dataclass(frozen=True, slots=True)
class QuotaSnapshot:
    document_limit: int
    documents_used: int
    daily_ai_limit: int
    daily_ai_used: int
    daily_ai_remaining: int
    daily_reset_date: str


@dataclass(frozen=True, slots=True)
class ChatTurnRecord:
    turn_id: str
    document_id: str
    query: str
    answer: str
    citations: list[dict[str, object]]
    created_at: datetime


class AccountRepository(Protocol):
    def ping(self) -> None: ...

    def create_user(self, email: str, password_hash: str) -> UserRecord: ...

    def find_user_by_email(self, email: str) -> UserRecord | None: ...

    def find_user_by_id(self, user_id: str) -> UserRecord | None: ...

    def get_quota(self, user_id: str) -> QuotaSnapshot: ...

    def reserve_document_slot(self, user_id: str) -> None: ...

    def release_document_slot(self, user_id: str) -> None: ...

    def add_document(self, user_id: str, manifest: DocumentManifest) -> None: ...

    def list_owned_document_ids(self, user_id: str) -> list[str]: ...

    def assert_document_owner(self, user_id: str, document_id: str) -> None: ...

    def remove_document(self, user_id: str, document_id: str) -> None: ...

    def consume_ai_request(self, user_id: str) -> QuotaSnapshot: ...

    def add_chat_turn(
        self,
        user_id: str,
        document_id: str,
        query: str,
        answer: str,
        citations: list[dict[str, object]],
    ) -> ChatTurnRecord: ...

    def list_chat_turns(self, user_id: str, document_id: str) -> list[ChatTurnRecord]: ...

    def clear_chat_turns(self, user_id: str, document_id: str) -> None: ...


def _user_record(document: dict[str, Any]) -> UserRecord:
    return UserRecord(
        user_id=str(document["_id"]),
        email=str(document["email"]),
        password_hash=str(document["password_hash"]),
        created_at=document["created_at"],
        document_limit=int(document.get("document_limit", settings.user_document_limit)),
        daily_ai_limit=int(document.get("daily_ai_limit", settings.user_daily_ai_limit)),
    )


def _chat_record(document: dict[str, Any]) -> ChatTurnRecord:
    return ChatTurnRecord(
        turn_id=str(document["_id"]),
        document_id=str(document["document_id"]),
        query=str(document["query"]),
        answer=str(document["answer"]),
        citations=list(document.get("citations", [])),
        created_at=document["created_at"],
    )


class MongoAccountRepository:
    """Small repository layer around the collections PdfSense owns."""

    def __init__(self, uri: str, database_name: str, timeout_ms: int) -> None:
        self.client: MongoClient[dict[str, Any]] = MongoClient(
            uri,
            server_api=ServerApi("1"),
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            tz_aware=True,
        )
        self.database = self.client[database_name]
        self.users = self.database["users"]
        self.documents = self.database["documents"]
        self.chat_turns = self.database["chat_turns"]
        self._ready = False
        self._ready_lock = Lock()

    def _ensure_ready(self) -> None:
        if self._ready:
            return
        with self._ready_lock:
            if self._ready:
                return
            try:
                self.client.admin.command("ping")
                self.users.create_index("email", unique=True)
                self.documents.create_index("document_id", unique=True)
                self.documents.create_index(
                    [("owner_id", ASCENDING), ("created_at", DESCENDING)]
                )
                self.chat_turns.create_index(
                    [("owner_id", ASCENDING), ("document_id", ASCENDING), ("created_at", ASCENDING)]
                )
            except ConfigurationError as exc:
                raise DatabaseConfigurationError("MONGODB_URI is invalid.") from exc
            except PyMongoError as exc:
                raise DatabaseUnavailableError("MongoDB is unavailable.") from exc
            self._ready = True

    def ping(self) -> None:
        self._ensure_ready()

    def create_user(self, email: str, password_hash: str) -> UserRecord:
        self._ensure_ready()
        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "_id": str(uuid4()),
            "email": email,
            "password_hash": password_hash,
            "created_at": now,
            "document_limit": settings.user_document_limit,
            "document_count": 0,
            "daily_ai_limit": settings.user_daily_ai_limit,
            "daily_ai_used": 0,
            "daily_ai_date": now.date().isoformat(),
        }
        try:
            self.users.insert_one(document)
        except DuplicateKeyError as exc:
            raise UserAlreadyExistsError("An account with this email already exists.") from exc
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not create the account.") from exc
        return _user_record(document)

    def find_user_by_email(self, email: str) -> UserRecord | None:
        self._ensure_ready()
        try:
            document = self.users.find_one({"email": email})
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not read the account.") from exc
        return _user_record(document) if document else None

    def find_user_by_id(self, user_id: str) -> UserRecord | None:
        self._ensure_ready()
        try:
            document = self.users.find_one({"_id": user_id})
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not read the account.") from exc
        return _user_record(document) if document else None

    def _user_document(self, user_id: str) -> dict[str, Any]:
        try:
            document = self.users.find_one({"_id": user_id})
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not read account quotas.") from exc
        if not document:
            raise AuthenticationError("Authentication is required.")
        return document

    def get_quota(self, user_id: str) -> QuotaSnapshot:
        self._ensure_ready()
        document = self._user_document(user_id)
        today = datetime.now(UTC).date().isoformat()
        daily_used = (
            int(document.get("daily_ai_used", 0))
            if document.get("daily_ai_date") == today
            else 0
        )
        document_limit = int(document.get("document_limit", settings.user_document_limit))
        daily_limit = int(document.get("daily_ai_limit", settings.user_daily_ai_limit))
        return QuotaSnapshot(
            document_limit=document_limit,
            documents_used=int(document.get("document_count", 0)),
            daily_ai_limit=daily_limit,
            daily_ai_used=daily_used,
            daily_ai_remaining=max(0, daily_limit - daily_used),
            daily_reset_date=today,
        )

    def reserve_document_slot(self, user_id: str) -> None:
        self._ensure_ready()
        query = {
            "_id": user_id,
            "$expr": {
                "$lt": [
                    {"$ifNull": ["$document_count", 0]},
                    {"$ifNull": ["$document_limit", settings.user_document_limit]},
                ]
            },
        }
        try:
            document = self.users.find_one_and_update(
                query,
                {"$inc": {"document_count": 1}},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not reserve document storage.") from exc
        if document is None:
            if self.find_user_by_id(user_id) is None:
                raise AuthenticationError("Authentication is required.")
            raise QuotaExceededError("Your document quota has been reached.")

    def release_document_slot(self, user_id: str) -> None:
        self._ensure_ready()
        try:
            self.users.update_one(
                {"_id": user_id, "document_count": {"$gt": 0}},
                {"$inc": {"document_count": -1}},
            )
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not update document quota.") from exc

    def add_document(self, user_id: str, manifest: DocumentManifest) -> None:
        self._ensure_ready()
        try:
            self.documents.insert_one(
                {
                    "_id": manifest.document_id,
                    "document_id": manifest.document_id,
                    "owner_id": user_id,
                    "filename": manifest.filename,
                    "page_count": manifest.page_count,
                    "number_of_chunks": manifest.number_of_chunks,
                    "status": manifest.status,
                    "created_at": datetime.fromisoformat(manifest.created_at),
                }
            )
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not register document ownership.") from exc

    def list_owned_document_ids(self, user_id: str) -> list[str]:
        self._ensure_ready()
        try:
            cursor = self.documents.find({"owner_id": user_id}, {"document_id": 1}).sort(
                "created_at", DESCENDING
            )
            return [str(document["document_id"]) for document in cursor]
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not list your documents.") from exc

    def assert_document_owner(self, user_id: str, document_id: str) -> None:
        self._ensure_ready()
        try:
            owned = self.documents.find_one(
                {"document_id": document_id, "owner_id": user_id},
                {"_id": 1},
            )
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not verify document ownership.") from exc
        if not owned:
            raise DocumentNotFoundError("Document not found.")

    def remove_document(self, user_id: str, document_id: str) -> None:
        self._ensure_ready()
        try:
            result = self.documents.delete_one(
                {"document_id": document_id, "owner_id": user_id}
            )
            if result.deleted_count:
                self.users.update_one(
                    {"_id": user_id, "document_count": {"$gt": 0}},
                    {"$inc": {"document_count": -1}},
                )
                self.chat_turns.delete_many(
                    {"owner_id": user_id, "document_id": document_id}
                )
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not remove document metadata.") from exc

    def consume_ai_request(self, user_id: str) -> QuotaSnapshot:
        self._ensure_ready()
        today = datetime.now(UTC).date().isoformat()
        try:
            self.users.update_one(
                {"_id": user_id, "daily_ai_date": {"$ne": today}},
                {"$set": {"daily_ai_date": today, "daily_ai_used": 0}},
            )
            document = self.users.find_one_and_update(
                {
                    "_id": user_id,
                    "$expr": {
                        "$lt": [
                            {"$ifNull": ["$daily_ai_used", 0]},
                            {"$ifNull": ["$daily_ai_limit", settings.user_daily_ai_limit]},
                        ]
                    },
                },
                {"$inc": {"daily_ai_used": 1}},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not update AI request quota.") from exc
        if document is None:
            if self.find_user_by_id(user_id) is None:
                raise AuthenticationError("Authentication is required.")
            raise QuotaExceededError("Your daily AI request quota has been reached.")
        return self.get_quota(user_id)

    def add_chat_turn(
        self,
        user_id: str,
        document_id: str,
        query: str,
        answer: str,
        citations: list[dict[str, object]],
    ) -> ChatTurnRecord:
        self._ensure_ready()
        document: dict[str, Any] = {
            "_id": str(uuid4()),
            "owner_id": user_id,
            "document_id": document_id,
            "query": query,
            "answer": answer,
            "citations": citations,
            "created_at": datetime.now(UTC),
        }
        try:
            self.chat_turns.insert_one(document)
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not save chat history.") from exc
        return _chat_record(document)

    def list_chat_turns(self, user_id: str, document_id: str) -> list[ChatTurnRecord]:
        self._ensure_ready()
        try:
            cursor = (
                self.chat_turns.find({"owner_id": user_id, "document_id": document_id})
                .sort("created_at", DESCENDING)
                .limit(settings.chat_history_limit)
            )
            records = [_chat_record(document) for document in cursor]
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not read chat history.") from exc
        records.reverse()
        return records

    def clear_chat_turns(self, user_id: str, document_id: str) -> None:
        self._ensure_ready()
        try:
            self.chat_turns.delete_many({"owner_id": user_id, "document_id": document_id})
        except PyMongoError as exc:
            raise DatabaseUnavailableError("Could not clear chat history.") from exc


@lru_cache(maxsize=4)
def _repository(uri: str, database_name: str, timeout_ms: int) -> MongoAccountRepository:
    return MongoAccountRepository(uri, database_name, timeout_ms)


def get_account_repository() -> AccountRepository:
    if not settings.mongodb_uri:
        raise DatabaseConfigurationError("MONGODB_URI is required.")
    try:
        return _repository(
            settings.mongodb_uri,
            settings.mongodb_database,
            settings.mongodb_timeout_ms,
        )
    except (PyMongoError, ValueError) as exc:
        raise DatabaseConfigurationError("MONGODB_URI is invalid.") from exc


def clear_account_repository_cache() -> None:
    _repository.cache_clear()
