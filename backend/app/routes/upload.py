"""PDF upload API routes."""

import logging

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.core.dependencies import CurrentUser, Repository
from app.services.account_service import AccountServiceError
from app.services.document_service import delete_document, get_document
from app.services.pdf_service import process_pdf_upload

router = APIRouter(prefix="/api", tags=["documents"])
logger = logging.getLogger("pdfsense.upload")


class UploadPDFResponse(BaseModel):
    """Public response returned after a PDF is processed."""

    document_id: str
    filename: str
    page_count: int = Field(ge=0)
    number_of_chunks: int = Field(ge=0)
    status: str
    message: str


@router.post("/upload", response_model=UploadPDFResponse)
async def upload_pdf(
    user: CurrentUser,
    repository: Repository,
    file: UploadFile = File(...),
) -> UploadPDFResponse:
    """Upload a PDF and run extraction and text chunking."""

    await run_in_threadpool(repository.reserve_document_slot, user.user_id)
    result = None
    try:
        result = await process_pdf_upload(file)
        manifest = await run_in_threadpool(get_document, result.document_id)
        await run_in_threadpool(repository.add_document, user.user_id, manifest)
    except Exception:
        if result is not None:
            try:
                await run_in_threadpool(delete_document, result.document_id)
            except Exception:
                logger.exception("orphaned_document_cleanup_failed")
        try:
            await run_in_threadpool(repository.release_document_slot, user.user_id)
        except AccountServiceError:
            logger.exception("document_quota_release_failed")
        raise
    finally:
        await file.close()

    return UploadPDFResponse(
        document_id=result.document_id,
        filename=result.filename,
        page_count=result.page_count,
        number_of_chunks=len(result.chunks),
        status=result.status,
        message="PDF uploaded and processed successfully.",
    )
