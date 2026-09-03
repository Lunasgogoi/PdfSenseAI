"""Shared FastAPI dependencies for persistence and authentication."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.services.account_service import (
    AccountRepository,
    AuthenticationError,
    UserRecord,
    get_account_repository,
)
from app.services.auth_service import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_repository() -> AccountRepository:
    return get_account_repository()


Repository = Annotated[AccountRepository, Depends(get_repository)]


def get_current_user(
    request: Request,
    repository: Repository,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ],
) -> UserRecord:
    token = credentials.credentials if credentials else request.cookies.get(
        settings.auth_cookie_name
    )
    if not token:
        raise AuthenticationError("Authentication is required.")
    user = repository.find_user_by_id(decode_access_token(token))
    if user is None:
        raise AuthenticationError("Authentication is required.")
    return user


CurrentUser = Annotated[UserRecord, Depends(get_current_user)]
