"""Groq chat-completion client and failure normalization."""

from __future__ import annotations

from threading import Lock
from typing import Any, Sequence

from app.core.config import settings


_client: Any | None = None
_client_lock = Lock()


class LLMServiceError(RuntimeError):
    """Base exception for expected LLM service failures."""


class LLMConfigurationError(LLMServiceError):
    """Raised when Groq access is not configured correctly."""


class LLMProviderError(LLMServiceError):
    """Raised when Groq rejects or cannot complete a request."""


class LLMRateLimitError(LLMProviderError):
    """Raised when Groq rate-limits a request."""


class LLMTimeoutError(LLMProviderError):
    """Raised when Groq does not respond within the configured timeout."""


class LLMResponseError(LLMServiceError):
    """Raised when Groq returns an empty or malformed completion."""


def _create_groq_client(api_key: str, timeout: float, max_retries: int) -> Any:
    from groq import Groq

    return Groq(
        api_key=api_key,
        timeout=timeout,
        max_retries=max_retries,
    )


def get_groq_client() -> Any:
    """Return one process-wide Groq client."""

    global _client
    if _client is not None:
        return _client
    if not settings.groq_api_key:
        raise LLMConfigurationError("GROQ_API_KEY is required for chat inference.")
    if settings.groq_timeout_seconds <= 0:
        raise LLMConfigurationError("GROQ_TIMEOUT_SECONDS must be positive.")
    if settings.groq_max_retries < 0:
        raise LLMConfigurationError("GROQ_MAX_RETRIES cannot be negative.")

    with _client_lock:
        if _client is None:
            try:
                _client = _create_groq_client(
                    settings.groq_api_key,
                    settings.groq_timeout_seconds,
                    settings.groq_max_retries,
                )
            except Exception as exc:
                raise LLMConfigurationError(
                    "Could not configure the Groq client."
                ) from exc
    return _client


def clear_groq_client_cache() -> None:
    """Release the cached client for tests or controlled reconfiguration."""

    global _client
    with _client_lock:
        _client = None


def generate_json_completion(
    messages: Sequence[dict[str, str]],
    *,
    max_completion_tokens: int | None = None,
) -> str:
    """Generate one non-thinking JSON chat completion through Groq."""

    if not messages:
        raise LLMConfigurationError("At least one chat message is required.")
    if not 0 <= settings.groq_temperature <= 2:
        raise LLMConfigurationError("GROQ_TEMPERATURE must be between 0 and 2.")
    token_limit = (
        settings.groq_max_completion_tokens
        if max_completion_tokens is None
        else max_completion_tokens
    )
    if token_limit < 1:
        raise LLMConfigurationError("GROQ_MAX_COMPLETION_TOKENS must be positive.")

    client = get_groq_client()
    try:
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=list(messages),
            temperature=settings.groq_temperature,
            max_completion_tokens=token_limit,
            reasoning_effort="none",
            response_format={"type": "json_object"},
            citation_options="disabled",
        )
    except Exception as exc:
        try:
            from groq import APITimeoutError, RateLimitError
        except ImportError:
            APITimeoutError = ()  # type: ignore[assignment, misc]
            RateLimitError = ()  # type: ignore[assignment, misc]

        if isinstance(exc, RateLimitError):
            raise LLMRateLimitError("Groq rate limit exceeded.") from exc
        if isinstance(exc, APITimeoutError):
            raise LLMTimeoutError("Groq request timed out.") from exc
        raise LLMProviderError("Groq could not generate a completion.") from exc

    try:
        content = completion.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise LLMResponseError("Groq returned an invalid completion.") from exc
    if not isinstance(content, str) or not content.strip():
        raise LLMResponseError("Groq returned an empty completion.")
    return content.strip()
