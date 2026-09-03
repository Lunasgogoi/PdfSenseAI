"""Account registration and signed-session endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, EmailStr, Field, SecretStr

from app.core.config import settings
from app.core.dependencies import CurrentUser, Repository
from app.services.account_service import AccountRepository, QuotaSnapshot, UserRecord
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    hash_password,
    normalize_email,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class CredentialsRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=8, max_length=128)


class QuotaResponse(BaseModel):
    document_limit: int
    documents_used: int
    documents_remaining: int
    daily_ai_limit: int
    daily_ai_used: int
    daily_ai_remaining: int
    daily_reset_date: str


class UserResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    created_at: datetime
    quota: QuotaResponse


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class LogoutResponse(BaseModel):
    message: str


def _quota_response(quota: QuotaSnapshot) -> QuotaResponse:
    return QuotaResponse(
        document_limit=quota.document_limit,
        documents_used=quota.documents_used,
        documents_remaining=max(0, quota.document_limit - quota.documents_used),
        daily_ai_limit=quota.daily_ai_limit,
        daily_ai_used=quota.daily_ai_used,
        daily_ai_remaining=quota.daily_ai_remaining,
        daily_reset_date=quota.daily_reset_date,
    )


def _user_response(user: UserRecord, repository: AccountRepository) -> UserResponse:
    return UserResponse(
        user_id=UUID(user.user_id),
        email=user.email,
        created_at=user.created_at,
        quota=_quota_response(repository.get_quota(user.user_id)),
    )


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def register_account(
    request: CredentialsRequest,
    response: Response,
    repository: Repository,
) -> SessionResponse:
    email = normalize_email(str(request.email))
    user = repository.create_user(email, hash_password(request.password.get_secret_value()))
    token = create_access_token(user.user_id)
    _set_session_cookie(response, token)
    return SessionResponse(
        access_token=token,
        user=_user_response(user, repository),
    )


@router.post("/login", response_model=SessionResponse)
def login(
    request: CredentialsRequest,
    response: Response,
    repository: Repository,
) -> SessionResponse:
    user = authenticate_user(
        repository,
        str(request.email),
        request.password.get_secret_value(),
    )
    token = create_access_token(user.user_id)
    _set_session_cookie(response, token)
    return SessionResponse(
        access_token=token,
        user=_user_response(user, repository),
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response) -> LogoutResponse:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return LogoutResponse(message="Signed out successfully.")


@router.get("/me", response_model=UserResponse)
def current_account(user: CurrentUser, repository: Repository) -> UserResponse:
    return _user_response(user, repository)
