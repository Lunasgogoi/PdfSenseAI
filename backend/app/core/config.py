"""Central application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _cors_origins() -> tuple[str, ...]:
    configured = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    return tuple(origin.strip() for origin in configured.split(",") if origin.strip())


def _runtime_path(name: str, default: Path) -> Path:
    configured = os.getenv(name)
    return Path(configured).resolve() if configured else default


def _boolean_setting(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    """Runtime settings, with environment-variable overrides where useful."""

    app_host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    app_port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    upload_dir: Path = field(
        default_factory=lambda: _runtime_path("UPLOAD_DIR", PROJECT_ROOT / "uploads")
    )
    vector_store_dir: Path = field(
        default_factory=lambda: _runtime_path(
            "VECTOR_STORE_DIR", PROJECT_ROOT / "vector_store"
        )
    )
    max_upload_bytes: int = field(
        default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
    )
    chunk_size: int = 1_000
    chunk_overlap: int = 200
    embedding_model_name: str = field(
        default_factory=lambda: os.getenv(
            "EMBEDDING_MODEL_NAME", "mixedbread-ai/mxbai-embed-large-v1"
        )
    )
    embedding_provider: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "hf-inference")
    )
    embedding_dimension: int = field(
        default_factory=lambda: int(os.getenv("EMBEDDING_DIMENSION", "1024"))
    )
    embedding_batch_size: int = field(
        default_factory=lambda: int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
    )
    embedding_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "60"))
    )
    retrieval_default_top_k: int = field(
        default_factory=lambda: int(os.getenv("RETRIEVAL_DEFAULT_TOP_K", "5"))
    )
    retrieval_max_top_k: int = field(
        default_factory=lambda: int(os.getenv("RETRIEVAL_MAX_TOP_K", "20"))
    )
    hf_token: str | None = field(
        default_factory=lambda: os.getenv("HF_TOKEN"),
        repr=False,
    )
    groq_api_key: str | None = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY"),
        repr=False,
    )
    mongodb_uri: str | None = field(
        default_factory=lambda: os.getenv("MONGODB_URI"),
        repr=False,
    )
    mongodb_database: str = field(
        default_factory=lambda: os.getenv("MONGODB_DATABASE", "pdfsense")
    )
    mongodb_timeout_ms: int = field(
        default_factory=lambda: int(os.getenv("MONGODB_TIMEOUT_MS", "5000"))
    )
    jwt_secret_key: str | None = field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY"),
        repr=False,
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = field(
        default_factory=lambda: int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
    )
    auth_cookie_name: str = field(
        default_factory=lambda: os.getenv("AUTH_COOKIE_NAME", "pdfsense_session")
    )
    auth_cookie_secure: bool = field(
        default_factory=lambda: _boolean_setting("AUTH_COOKIE_SECURE")
    )
    user_document_limit: int = field(
        default_factory=lambda: int(os.getenv("USER_DOCUMENT_LIMIT", "10"))
    )
    user_daily_ai_limit: int = field(
        default_factory=lambda: int(os.getenv("USER_DAILY_AI_LIMIT", "50"))
    )
    chat_history_limit: int = field(
        default_factory=lambda: int(os.getenv("CHAT_HISTORY_LIMIT", "100"))
    )
    groq_model: str = field(
        default_factory=lambda: os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")
    )
    groq_temperature: float = field(
        default_factory=lambda: float(os.getenv("GROQ_TEMPERATURE", "0.2"))
    )
    groq_max_completion_tokens: int = field(
        default_factory=lambda: int(os.getenv("GROQ_MAX_COMPLETION_TOKENS", "1024"))
    )
    groq_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("GROQ_TIMEOUT_SECONDS", "60"))
    )
    groq_max_retries: int = field(
        default_factory=lambda: int(os.getenv("GROQ_MAX_RETRIES", "2"))
    )
    rag_top_k: int = field(
        default_factory=lambda: int(os.getenv("RAG_TOP_K", "5"))
    )
    summary_batch_characters: int = field(
        default_factory=lambda: int(os.getenv("SUMMARY_BATCH_CHARACTERS", "12000"))
    )
    summary_intermediate_max_tokens: int = field(
        default_factory=lambda: int(
            os.getenv("SUMMARY_INTERMEDIATE_MAX_TOKENS", "512")
        )
    )
    summary_final_max_tokens: int = field(
        default_factory=lambda: int(os.getenv("SUMMARY_FINAL_MAX_TOKENS", "1536"))
    )
    summary_max_reduction_rounds: int = field(
        default_factory=lambda: int(os.getenv("SUMMARY_MAX_REDUCTION_ROUNDS", "8"))
    )
    study_context_characters: int = field(
        default_factory=lambda: int(os.getenv("STUDY_CONTEXT_CHARACTERS", "24000"))
    )
    study_max_completion_tokens: int = field(
        default_factory=lambda: int(os.getenv("STUDY_MAX_COMPLETION_TOKENS", "4096"))
    )
    study_max_items_per_type: int = field(
        default_factory=lambda: int(os.getenv("STUDY_MAX_ITEMS_PER_TYPE", "20"))
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    static_dir: Path = field(
        default_factory=lambda: _runtime_path("STATIC_DIR", PROJECT_ROOT / "static")
    )
    cors_origins: tuple[str, ...] = field(default_factory=_cors_origins)


settings = Settings()
