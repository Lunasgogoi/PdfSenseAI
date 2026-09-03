"""Integration tests for Module 1 document ingestion."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from uuid import UUID, uuid4

import pymupdf
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.core.config import settings
from app.main import app
from app.services.embedding_service import EmbeddingGenerationError


def make_pdf(page_texts: list[str], *, password: str | None = None) -> bytes:
    document = pymupdf.open()
    for page_text in page_texts:
        page = document.new_page()
        if page_text:
            page.insert_textbox(
                pymupdf.Rect(72, 72, 540, 770),
                page_text,
                fontsize=11,
            )

    options: dict[str, object] = {}
    if password is not None:
        options = {
            "encryption": pymupdf.PDF_ENCRYPT_AES_256,
            "owner_pw": "owner-password",
            "user_pw": password,
        }

    pdf_bytes = document.tobytes(**options)
    document.close()
    return pdf_bytes


class DocumentIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temporary_root = Path(self.temporary_directory.name)
        self.previous_upload_dir = settings.upload_dir
        self.previous_vector_store_dir = settings.vector_store_dir
        self.previous_max_upload_bytes = settings.max_upload_bytes
        settings.upload_dir = self.temporary_root / "uploads"
        settings.vector_store_dir = self.temporary_root / "vector_store"
        settings.max_upload_bytes = 25 * 1024 * 1024
        self.embedding_patcher = patch(
            "app.services.vector_service.embed_documents",
            side_effect=self._fake_embeddings,
        )
        self.mock_embed_documents = self.embedding_patcher.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.embedding_patcher.stop()
        settings.upload_dir = self.previous_upload_dir
        settings.vector_store_dir = self.previous_vector_store_dir
        settings.max_upload_bytes = self.previous_max_upload_bytes
        self.temporary_directory.cleanup()

    @staticmethod
    def _fake_embeddings(texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), settings.embedding_dimension), dtype=np.float32)
        vectors[:, 0] = 1.0
        return vectors

    def upload(
        self,
        filename: str,
        content: bytes,
        content_type: str = "application/pdf",
    ):
        return self.client.post(
            "/api/upload",
            files={"file": (filename, content, content_type)},
        )

    def test_upload_persists_page_aware_workspace(self) -> None:
        response = self.upload(
            "../../Quarterly Report.pdf",
            make_pdf(["Revenue increased this quarter.", "Risks are listed here."]),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        document_id = payload["document_id"]
        UUID(document_id)
        self.assertEqual(payload["filename"], "Quarterly_Report.pdf")
        self.assertEqual(payload["page_count"], 2)
        self.assertEqual(payload["number_of_chunks"], 2)
        self.assertEqual(payload["status"], "ready")

        workspace = settings.upload_dir / document_id
        self.assertTrue((workspace / "source.pdf").is_file())
        self.assertTrue((workspace / "manifest.json").is_file())
        self.assertTrue((workspace / "chunks.json").is_file())

        vector_workspace = settings.vector_store_dir / document_id
        self.assertTrue((vector_workspace / "index.faiss").is_file())
        self.assertTrue((vector_workspace / "metadata.json").is_file())

        chunks = json.loads((workspace / "chunks.json").read_text(encoding="utf-8"))
        self.assertEqual([chunk["metadata"]["page_number"] for chunk in chunks], [1, 2])
        self.assertEqual(
            [chunk["metadata"]["chunk_index"] for chunk in chunks],
            [0, 1],
        )

    def test_same_named_documents_are_isolated_and_listed_after_new_client(self) -> None:
        pdf = make_pdf(["A document with extractable text."])
        first = self.upload("same.pdf", pdf).json()
        second = self.upload("same.pdf", pdf).json()

        self.assertNotEqual(first["document_id"], second["document_id"])
        self.assertTrue((settings.upload_dir / first["document_id"]).is_dir())
        self.assertTrue((settings.upload_dir / second["document_id"]).is_dir())

        with TestClient(app) as restarted_client:
            response = restarted_client.get("/api/documents")

        self.assertEqual(response.status_code, 200)
        listed_ids = {
            document["document_id"] for document in response.json()["documents"]
        }
        self.assertEqual(listed_ids, {first["document_id"], second["document_id"]})

        details = self.client.get(f"/api/documents/{first['document_id']}")
        self.assertEqual(details.status_code, 200)
        self.assertEqual(details.json()["filename"], "same.pdf")

    def test_delete_removes_document_and_vector_workspaces(self) -> None:
        uploaded = self.upload("delete.pdf", make_pdf(["Delete this document."])).json()
        document_id = uploaded["document_id"]
        vector_workspace = settings.vector_store_dir / document_id
        self.assertTrue(vector_workspace.is_dir())

        response = self.client.delete(f"/api/documents/{document_id}")

        self.assertEqual(response.status_code, 204)
        self.assertFalse((settings.upload_dir / document_id).exists())
        self.assertFalse(vector_workspace.exists())
        self.assertEqual(
            self.client.get(f"/api/documents/{document_id}").status_code,
            404,
        )

    def test_rejects_non_pdf_extension_and_mime_type(self) -> None:
        pdf = make_pdf(["Valid PDF bytes."])
        self.assertEqual(self.upload("notes.txt", pdf).status_code, 415)
        self.assertEqual(
            self.upload("notes.pdf", pdf, "text/plain").status_code,
            415,
        )

    def test_rejects_malformed_encrypted_and_textless_pdfs(self) -> None:
        malformed = self.upload("broken.pdf", b"%PDF-not-a-real-document")
        encrypted = self.upload(
            "encrypted.pdf",
            make_pdf(["Secret text."], password="secret"),
        )
        textless = self.upload("blank.pdf", make_pdf([""]))

        self.assertEqual(malformed.status_code, 422)
        self.assertEqual(encrypted.status_code, 422)
        self.assertEqual(textless.status_code, 422)
        self.assertEqual(list(settings.upload_dir.glob("*")), [])

    def test_rejects_oversized_upload_and_removes_partial_workspace(self) -> None:
        settings.max_upload_bytes = 16

        response = self.upload("large.pdf", b"%PDF-" + (b"x" * 100))

        self.assertEqual(response.status_code, 413)
        self.assertEqual(list(settings.upload_dir.glob("*")), [])

    def test_missing_document_returns_not_found(self) -> None:
        missing_id = uuid4()
        self.assertEqual(
            self.client.get(f"/api/documents/{missing_id}").status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(f"/api/documents/{missing_id}").status_code,
            404,
        )

    def test_indexing_failure_removes_both_workspaces(self) -> None:
        self.mock_embed_documents.side_effect = EmbeddingGenerationError(
            "Hosted inference failed."
        )

        response = self.upload("failure.pdf", make_pdf(["Index this text."]))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(list(settings.upload_dir.glob("*")), [])
        if settings.vector_store_dir.exists():
            self.assertEqual(list(settings.vector_store_dir.glob("*")), [])


if __name__ == "__main__":
    unittest.main()
