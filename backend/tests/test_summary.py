"""Integration and opt-in live tests for the summary API."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import numpy as np
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import embedding_service, llm_service
from app.services.llm_service import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from tests.fakes import install_test_auth, remove_test_auth
from tests.test_document_ingestion import make_pdf


class SummaryAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temporary_root = Path(self.temporary_directory.name)
        self.previous_upload_dir = settings.upload_dir
        self.previous_vector_store_dir = settings.vector_store_dir
        self.previous_dimension = settings.embedding_dimension
        self.previous_model_name = settings.embedding_model_name
        settings.upload_dir = self.temporary_root / "uploads"
        settings.vector_store_dir = self.temporary_root / "vector_store"
        settings.embedding_dimension = 3
        settings.embedding_model_name = "test/mxbai"
        self.embedding_patcher = patch(
            "app.services.vector_service.embed_documents",
            side_effect=self._fake_embeddings,
        )
        self.embedding_patcher.start()
        self.account_repository = install_test_auth(app)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        remove_test_auth(app)
        self.embedding_patcher.stop()
        settings.upload_dir = self.previous_upload_dir
        settings.vector_store_dir = self.previous_vector_store_dir
        settings.embedding_dimension = self.previous_dimension
        settings.embedding_model_name = self.previous_model_name
        self.temporary_directory.cleanup()

    @staticmethod
    def _fake_embeddings(texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), 3), dtype=np.float32)
        vectors[:, 0] = 1.0
        return vectors

    def upload_document(self) -> str:
        response = self.client.post(
            "/api/upload",
            files={
                "file": (
                    "summary.pdf",
                    make_pdf(["First important fact.", "Second important finding."]),
                    "application/pdf",
                )
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["document_id"]

    def test_brief_default_and_detailed_summary_responses(self) -> None:
        document_id = self.upload_document()
        with patch(
            "app.services.summary_service.generate_json_completion",
            return_value='{"summary":"Grounded document summary."}',
        ):
            brief = self.client.post(
                "/api/summary",
                json={"document_id": document_id},
            )
            detailed = self.client.post(
                "/api/summary",
                json={"document_id": document_id, "detail": "detailed"},
            )

        self.assertEqual(brief.status_code, 200, brief.text)
        self.assertEqual(brief.json()["detail"], "brief")
        self.assertEqual(brief.json()["summary"], "Grounded document summary.")
        self.assertEqual(detailed.status_code, 200, detailed.text)
        self.assertEqual(detailed.json()["detail"], "detailed")

    def test_validation_and_missing_document(self) -> None:
        self.assertEqual(
            self.client.post(
                "/api/summary",
                json={"document_id": "not-a-uuid", "detail": "brief"},
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                "/api/summary",
                json={"document_id": str(uuid4()), "detail": "medium"},
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                "/api/summary",
                json={"document_id": str(uuid4()), "detail": "brief"},
            ).status_code,
            404,
        )

    def test_llm_failures_have_stable_http_statuses(self) -> None:
        document_id = self.upload_document()
        failures = [
            (LLMConfigurationError("Missing key."), 503),
            (LLMRateLimitError("Rate limited."), 429),
            (LLMTimeoutError("Timed out."), 502),
            (LLMProviderError("Provider failed."), 502),
            (LLMResponseError("Malformed response."), 502),
        ]
        for failure, expected_status in failures:
            with self.subTest(failure=type(failure).__name__), patch(
                "app.services.summary_service.generate_json_completion",
                side_effect=failure,
            ):
                response = self.client.post(
                    "/api/summary",
                    json={"document_id": document_id, "detail": "brief"},
                )
                self.assertEqual(response.status_code, expected_status)


@unittest.skipUnless(
    os.getenv("RUN_LIVE_SUMMARY_API_TEST") == "1"
    and os.getenv("HF_TOKEN")
    and os.getenv("GROQ_API_KEY"),
    "Set both API keys and RUN_LIVE_SUMMARY_API_TEST=1 for a live summary test.",
)
class LiveSummaryAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temporary_root = Path(self.temporary_directory.name)
        self.previous_upload_dir = settings.upload_dir
        self.previous_vector_store_dir = settings.vector_store_dir
        settings.upload_dir = self.temporary_root / "uploads"
        settings.vector_store_dir = self.temporary_root / "vector_store"
        embedding_service.clear_embedding_client_cache()
        llm_service.clear_groq_client_cache()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        embedding_service.clear_embedding_client_cache()
        llm_service.clear_groq_client_cache()
        settings.upload_dir = self.previous_upload_dir
        settings.vector_store_dir = self.previous_vector_store_dir
        self.temporary_directory.cleanup()

    def test_live_brief_summary(self) -> None:
        upload = self.client.post(
            "/api/upload",
            files={
                "file": (
                    "live-summary.pdf",
                    make_pdf(
                        [
                            "Project Aurora launches in October 2028.",
                            "Its approved budget is 2.5 million dollars.",
                        ]
                    ),
                    "application/pdf",
                )
            },
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        document_id = upload.json()["document_id"]

        response = self.client.post(
            "/api/summary",
            json={"document_id": document_id, "detail": "brief"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        summary = response.json()["summary"].lower()
        self.assertIn("aurora", summary)
        self.assertIn("2028", summary)

        self.assertEqual(
            self.client.delete(f"/api/documents/{document_id}").status_code,
            204,
        )


if __name__ == "__main__":
    unittest.main()
