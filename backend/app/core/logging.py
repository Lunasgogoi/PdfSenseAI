"""Structured application logging and request correlation."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

STANDARD_LOG_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in STANDARD_LOG_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Configure the PdfSense logger without changing host-process loggers."""

    logger = logging.getLogger("pdfsense")
    logger.setLevel(level.upper())
    logger.propagate = False
    if not any(getattr(handler, "_pdfsense_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler._pdfsense_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach request IDs and emit a completion event for every response."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        started = perf_counter()
        response = await call_next(request)
        duration_ms = round((perf_counter() - started) * 1_000, 2)
        response.headers["X-Request-ID"] = request_id
        logging.getLogger("pdfsense.requests").info(
            "request_completed",
            extra={
                "request_id": request_id,
                "http_method": request.method,
                "http_path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
