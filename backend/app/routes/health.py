"""Liveness and dependency-readiness endpoints."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.config import settings
from app.services.account_service import (
    AccountServiceError,
    get_account_repository,
)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessChecks(BaseModel):
    storage: Literal["ready", "unavailable"]
    hugging_face: Literal["configured", "missing"]
    groq: Literal["configured", "missing"]
    mongodb: Literal["ready", "missing", "unavailable"]
    authentication: Literal["configured", "missing"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: ReadinessChecks


def _storage_is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path.is_dir() and os.access(path, os.W_OK)
    except OSError:
        return False


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report that the API process is alive."""

    return HealthResponse(status="ok")


@router.get(
    "/api/health/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
def readiness(response: Response) -> ReadinessResponse:
    """Check local storage and required provider configuration without external calls."""

    storage_ready = all(
        _storage_is_writable(path)
        for path in (settings.upload_dir, settings.vector_store_dir)
    )
    hf_ready = bool(settings.hf_token)
    groq_ready = bool(settings.groq_api_key)
    authentication_ready = bool(
        settings.jwt_secret_key and len(settings.jwt_secret_key) >= 32
    )
    mongodb_status: Literal["ready", "missing", "unavailable"]
    if not settings.mongodb_uri:
        mongodb_status = "missing"
    else:
        try:
            get_account_repository().ping()
            mongodb_status = "ready"
        except AccountServiceError:
            mongodb_status = "unavailable"
    is_ready = (
        storage_ready
        and hf_ready
        and groq_ready
        and mongodb_status == "ready"
        and authentication_ready
    )
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        checks=ReadinessChecks(
            storage="ready" if storage_ready else "unavailable",
            hugging_face="configured" if hf_ready else "missing",
            groq="configured" if groq_ready else "missing",
            mongodb=mongodb_status,
            authentication="configured" if authentication_ready else "missing",
        ),
    )
