"""Document workspace management API routes."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.services.document_service import (
    DocumentManifest,
    DocumentNotFoundError,
    DocumentStorageError,
    delete_document,
    get_document,
    list_documents,
)


router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    document_id: UUID
    filename: str
    page_count: int = Field(ge=0)
    number_of_chunks: int = Field(ge=0)
    status: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


def _response_from_manifest(manifest: DocumentManifest) -> DocumentResponse:
    return DocumentResponse(
        document_id=UUID(manifest.document_id),
        filename=manifest.filename,
        page_count=manifest.page_count,
        number_of_chunks=manifest.number_of_chunks,
        status=manifest.status,
        created_at=datetime.fromisoformat(manifest.created_at),
    )


def _storage_error(exc: DocumentStorageError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exc),
    )


@router.get("", response_model=DocumentListResponse)
def get_documents() -> DocumentListResponse:
    try:
        documents = list_documents()
    except DocumentStorageError as exc:
        raise _storage_error(exc) from exc
    return DocumentListResponse(
        documents=[_response_from_manifest(document) for document in documents]
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_details(document_id: UUID) -> DocumentResponse:
    try:
        document = get_document(str(document_id))
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DocumentStorageError as exc:
        raise _storage_error(exc) from exc
    return _response_from_manifest(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(document_id: UUID) -> Response:
    try:
        delete_document(str(document_id))
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DocumentStorageError as exc:
        raise _storage_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
