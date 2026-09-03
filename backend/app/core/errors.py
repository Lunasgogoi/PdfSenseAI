"""Central HTTP error mapping for application service failures."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.account_service import (
    AccountServiceError,
    AuthenticationError,
    DatabaseConfigurationError,
    DatabaseUnavailableError,
    InvalidCredentialsError,
    QuotaExceededError,
    UserAlreadyExistsError,
)
from app.services.document_service import DocumentNotFoundError, DocumentStorageError
from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingGenerationError,
    InvalidEmbeddingInputError,
)
from app.services.llm_service import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.services.pdf_service import (
    InvalidPDFError,
    PDFProcessingError,
    PDFTooLargeError,
    UnsupportedFileError,
)
from app.services.retrieval_service import (
    DocumentNotReadyError,
    InvalidSearchRequestError,
)
from app.services.study_service import (
    InvalidStudyRequestError,
    StudyDocumentNotReadyError,
    StudyServiceError,
)
from app.services.summary_service import SummaryDocumentNotReadyError, SummaryServiceError
from app.services.vector_service import VectorIndexNotFoundError, VectorServiceError

logger = logging.getLogger("pdfsense.errors")


@dataclass(frozen=True, slots=True)
class ErrorMapping:
    exception_type: type[Exception]
    status_code: int
    code: str


# Subclasses must appear before their parent service exceptions.
ERROR_MAPPINGS: Final[tuple[ErrorMapping, ...]] = (
    ErrorMapping(UserAlreadyExistsError, status.HTTP_409_CONFLICT, "user_already_exists"),
    ErrorMapping(InvalidCredentialsError, status.HTTP_401_UNAUTHORIZED, "invalid_credentials"),
    ErrorMapping(AuthenticationError, status.HTTP_401_UNAUTHORIZED, "authentication_required"),
    ErrorMapping(QuotaExceededError, status.HTTP_429_TOO_MANY_REQUESTS, "quota_exceeded"),
    ErrorMapping(DatabaseConfigurationError, status.HTTP_503_SERVICE_UNAVAILABLE, "database_not_configured"),
    ErrorMapping(DatabaseUnavailableError, status.HTTP_503_SERVICE_UNAVAILABLE, "database_unavailable"),
    ErrorMapping(DocumentNotFoundError, status.HTTP_404_NOT_FOUND, "document_not_found"),
    ErrorMapping(UnsupportedFileError, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_file"),
    ErrorMapping(PDFTooLargeError, status.HTTP_413_CONTENT_TOO_LARGE, "pdf_too_large"),
    ErrorMapping(InvalidPDFError, status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_pdf"),
    ErrorMapping(InvalidSearchRequestError, status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_search_request"),
    ErrorMapping(InvalidEmbeddingInputError, status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_embedding_input"),
    ErrorMapping(InvalidStudyRequestError, status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_study_request"),
    ErrorMapping(DocumentNotReadyError, status.HTTP_409_CONFLICT, "document_not_ready"),
    ErrorMapping(VectorIndexNotFoundError, status.HTTP_409_CONFLICT, "vector_index_not_found"),
    ErrorMapping(SummaryDocumentNotReadyError, status.HTTP_409_CONFLICT, "document_not_ready"),
    ErrorMapping(StudyDocumentNotReadyError, status.HTTP_409_CONFLICT, "document_not_ready"),
    ErrorMapping(EmbeddingConfigurationError, status.HTTP_503_SERVICE_UNAVAILABLE, "embedding_not_configured"),
    ErrorMapping(LLMConfigurationError, status.HTTP_503_SERVICE_UNAVAILABLE, "llm_not_configured"),
    ErrorMapping(LLMRateLimitError, status.HTTP_429_TOO_MANY_REQUESTS, "llm_rate_limited"),
    ErrorMapping(EmbeddingGenerationError, status.HTTP_502_BAD_GATEWAY, "embedding_provider_error"),
    ErrorMapping(LLMTimeoutError, status.HTTP_502_BAD_GATEWAY, "llm_timeout"),
    ErrorMapping(LLMProviderError, status.HTTP_502_BAD_GATEWAY, "llm_provider_error"),
    ErrorMapping(LLMResponseError, status.HTTP_502_BAD_GATEWAY, "invalid_llm_response"),
    ErrorMapping(PDFProcessingError, status.HTTP_500_INTERNAL_SERVER_ERROR, "pdf_processing_error"),
    ErrorMapping(DocumentStorageError, status.HTTP_500_INTERNAL_SERVER_ERROR, "document_storage_error"),
    ErrorMapping(VectorServiceError, status.HTTP_500_INTERNAL_SERVER_ERROR, "vector_service_error"),
    ErrorMapping(SummaryServiceError, status.HTTP_500_INTERNAL_SERVER_ERROR, "summary_service_error"),
    ErrorMapping(StudyServiceError, status.HTTP_500_INTERNAL_SERVER_ERROR, "study_service_error"),
    ErrorMapping(AccountServiceError, status.HTTP_500_INTERNAL_SERVER_ERROR, "account_service_error"),
)


def _mapping_for(exc: Exception) -> ErrorMapping:
    for mapping in ERROR_MAPPINGS:
        if isinstance(exc, mapping.exception_type):
            return mapping
    raise LookupError(f"No HTTP mapping registered for {type(exc).__name__}.")


async def service_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a stable public error envelope and log the failure once."""

    mapping = _mapping_for(exc)
    log_method = logger.error if mapping.status_code >= 500 else logger.warning
    log_method(
        "service_error",
        extra={
            "error_code": mapping.code,
            "http_method": request.method,
            "http_path": request.url.path,
            "status_code": mapping.status_code,
        },
    )
    headers = {"WWW-Authenticate": "Bearer"} if mapping.status_code == 401 else None
    return JSONResponse(
        status_code=mapping.status_code,
        content={"detail": str(exc), "code": mapping.code},
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all service-to-HTTP mappings on an application."""

    for mapping in ERROR_MAPPINGS:
        app.add_exception_handler(mapping.exception_type, service_error_handler)
