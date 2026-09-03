"""PDF upload, text extraction, and chunking services."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pymupdf
from fastapi import UploadFile
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.services.document_service import (
    SOURCE_FILENAME,
    DocumentManifest,
    create_document_workspace,
    new_document_id,
    persist_document,
    remove_document_workspace,
    update_document_status,
)
from app.services.embedding_service import EmbeddingServiceError
from app.services.vector_service import (
    VectorServiceError,
    build_document_index,
    remove_vector_workspace,
)

READ_BUFFER_SIZE = 1024 * 1024


class PDFServiceError(Exception):
    """Base exception for expected PDF pipeline failures."""


class UnsupportedFileError(PDFServiceError):
    """Raised when an upload is not presented as a PDF."""


class PDFTooLargeError(PDFServiceError):
    """Raised when an upload exceeds the configured size limit."""


class InvalidPDFError(PDFServiceError):
    """Raised when a PDF is malformed, encrypted, or has no usable text."""


class PDFProcessingError(PDFServiceError):
    """Raised when a PDF cannot be saved or processed."""


@dataclass(frozen=True, slots=True)
class PDFChunk:
    """A text chunk and the metadata needed for later retrieval/citation."""

    page_content: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProcessedPDF:
    """Result of the first-stage PDF processing pipeline."""

    document_id: str
    filename: str
    stored_path: Path
    page_count: int
    chunks: list[PDFChunk]
    status: str


def _safe_filename(filename: str) -> str:
    """Remove path components and unsafe characters from a client filename."""

    basename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(basename).stem).strip("._")
    return f"{stem or 'document'}.pdf"


async def _save_upload(upload: UploadFile, destination: Path) -> None:
    """Stream an upload to disk while enforcing the configured size limit."""

    bytes_written = 0
    try:
        with destination.open("xb") as output_file:
            while data := await upload.read(READ_BUFFER_SIZE):
                bytes_written += len(data)
                if bytes_written > settings.max_upload_bytes:
                    raise PDFTooLargeError(
                        f"PDF exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit."
                    )
                output_file.write(data)
    except PDFTooLargeError:
        destination.unlink(missing_ok=True)
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise PDFProcessingError("Could not save the uploaded PDF.") from exc


def _extract_and_chunk(pdf_path: Path, source_name: str) -> tuple[int, list[PDFChunk]]:
    """Extract and split each page separately so page metadata is retained."""

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )
    chunks: list[PDFChunk] = []

    try:
        # Opening a byte stream avoids a lingering Windows file handle when
        # PyMuPDF rejects malformed input, so failed workspaces can be cleaned.
        with pymupdf.open(stream=pdf_path.read_bytes(), filetype="pdf") as document:
            if document.needs_pass:
                raise InvalidPDFError("Password-protected PDFs are not supported.")

            page_count = document.page_count
            for page_index, page in enumerate(document):
                page_text = page.get_text("text").strip()
                if not page_text:
                    continue

                for page_chunk_index, chunk_text in enumerate(splitter.split_text(page_text)):
                    chunks.append(
                        PDFChunk(
                            page_content=chunk_text,
                            metadata={
                                "source": source_name,
                                "page_number": page_index + 1,
                                "page_chunk_index": page_chunk_index,
                            },
                        )
                    )

            return page_count, chunks
    except InvalidPDFError:
        raise
    except (pymupdf.EmptyFileError, pymupdf.FileDataError) as exc:
        raise InvalidPDFError("The uploaded file is not a valid PDF.") from exc
    except Exception as exc:
        raise PDFProcessingError("Could not extract text from the PDF.") from exc


async def process_pdf_upload(upload: UploadFile) -> ProcessedPDF:
    """Validate, persist, extract, and chunk an uploaded PDF."""

    filename = upload.filename or ""
    if Path(filename).suffix.lower() != ".pdf":
        raise UnsupportedFileError("Only PDF files are accepted.")

    if upload.content_type not in {"application/pdf", "application/x-pdf"}:
        raise UnsupportedFileError("Only PDF files are accepted.")

    header = await upload.read(1024)
    await upload.seek(0)
    if b"%PDF-" not in header:
        raise InvalidPDFError("The uploaded file is not a valid PDF.")

    document_id = new_document_id()
    workspace: Path | None = None
    try:
        workspace = create_document_workspace(document_id)
        stored_path = workspace / SOURCE_FILENAME
        safe_filename = _safe_filename(filename)
        await _save_upload(upload, stored_path)
        page_count, chunks = _extract_and_chunk(stored_path, safe_filename)
        if not chunks:
            raise InvalidPDFError("The PDF contains no extractable text.")

        persisted_chunks = [
            {
                "chunk_id": f"{document_id}:{chunk_index}",
                "text": chunk.page_content,
                "metadata": {
                    **chunk.metadata,
                    "chunk_index": chunk_index,
                },
            }
            for chunk_index, chunk in enumerate(chunks)
        ]
        manifest = DocumentManifest(
            document_id=document_id,
            filename=safe_filename,
            stored_filename=SOURCE_FILENAME,
            page_count=page_count,
            number_of_chunks=len(chunks),
            status="ingested",
            created_at=datetime.now(UTC).isoformat(),
        )
        persist_document(workspace, manifest, persisted_chunks)
        try:
            build_document_index(document_id, persisted_chunks)
            manifest = update_document_status(document_id, "ready")
        except (EmbeddingServiceError, VectorServiceError) as exc:
            raise PDFProcessingError("Could not create the document index.") from exc

        return ProcessedPDF(
            document_id=document_id,
            filename=safe_filename,
            stored_path=stored_path,
            page_count=page_count,
            chunks=chunks,
            status=manifest.status,
        )
    except Exception:
        if workspace is not None:
            remove_document_workspace(workspace)
            remove_vector_workspace(document_id)
        raise
