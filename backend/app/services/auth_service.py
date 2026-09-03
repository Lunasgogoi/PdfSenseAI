"""Password hashing and signed session-token operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings
from app.services.account_service import (
    AccountRepository,
    AuthenticationError,
    DatabaseConfigurationError,
    InvalidCredentialsError,
    UserRecord,
)


@lru_cache(maxsize=1)
def _password_hash() -> PasswordHash:
    return PasswordHash.recommended()


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _password_hash().hash("pdfsense-dummy-password")


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_password(password: str) -> str:
    return _password_hash().hash(password)


def authenticate_user(
    repository: AccountRepository,
    email: str,
    password: str,
) -> UserRecord:
    user = repository.find_user_by_email(normalize_email(email))
    if user is None:
        _password_hash().verify(password, _dummy_hash())
        raise InvalidCredentialsError("Invalid email or password.")
    if not _password_hash().verify(password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password.")
    return user


def _jwt_secret() -> str:
    secret = settings.jwt_secret_key
    if not secret or len(secret) < 32:
        raise DatabaseConfigurationError(
            "JWT_SECRET_KEY must contain at least 32 characters."
        )
    return secret


def create_access_token(user_id: str) -> str:
    if settings.access_token_expire_minutes <= 0:
        raise DatabaseConfigurationError(
            "ACCESS_TOKEN_EXPIRE_MINUTES must be greater than zero."
        )
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {
            "sub": user_id,
            "type": "access",
            "iat": now,
            "exp": expires,
        },
        _jwt_secret(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as exc:
        raise AuthenticationError("Authentication is required.") from exc
    subject = payload.get("sub")
    if payload.get("type") != "access" or not isinstance(subject, str) or not subject:
        raise AuthenticationError("Authentication is required.")
    return subject
