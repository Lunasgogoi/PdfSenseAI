"""PDF upload API routes."""

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.services.pdf_service import (
    InvalidPDFError,
    PDFTooLargeError,
    PDFProcessingError,
    UnsupportedFileError,
    process_pdf_upload,
)


router = APIRouter(prefix="/api", tags=["documents"])


class UploadPDFResponse(BaseModel):
    """Public response returned after a PDF is processed."""

    document_id: str
    filename: str
    page_count: int = Field(ge=0)
    number_of_chunks: int = Field(ge=0)
    status: str
    message: str


@router.post("/upload", response_model=UploadPDFResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadPDFResponse:
    """Upload a PDF and run extraction and text chunking."""

    try:
        result = await process_pdf_upload(file)
    except UnsupportedFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except PDFTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except InvalidPDFError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except PDFProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
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
