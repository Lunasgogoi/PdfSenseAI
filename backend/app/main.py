"""Application entry point for the PdfSense backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.search import router as search_router
from app.routes.summary import router as summary_router
from app.routes.study import router as study_router
from app.routes.upload import router as upload_router


app = FastAPI(
    title="PdfSense API",
    description="AI-powered PDF document intelligence API.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(summary_router)
app.include_router(study_router)
