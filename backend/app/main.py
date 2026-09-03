"""Application entry point for the PdfSense backend."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import RequestLoggingMiddleware, configure_logging
from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.health import router as health_router
from app.routes.history import router as history_router
from app.routes.search import router as search_router
from app.routes.study import router as study_router
from app.routes.summary import router as summary_router
from app.routes.upload import router as upload_router

configure_logging(settings.log_level)

app = FastAPI(
    title="PdfSense API",
    description="AI-powered PDF document intelligence API.",
    version="0.1.0",
)

register_error_handlers(app)
app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(documents_router)
app.include_router(history_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(summary_router)
app.include_router(study_router)


def mount_frontend(application: FastAPI, static_dir: Path) -> bool:
    """Mount a production frontend bundle when one is present."""

    if not (static_dir / "index.html").is_file():
        return False
    application.mount(
        "/",
        StaticFiles(directory=str(static_dir), html=True),
        name="frontend",
    )
    return True


mount_frontend(app, settings.static_dir)
