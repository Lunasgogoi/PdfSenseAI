"""Integration and opt-in live tests for the study API."""

from __future__ import annotations

import json
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


def generated_payload(mcq_count: int, flashcard_count: int) -> str:
    return json.dumps(
        {
            "mcqs": [
                {
                    "question": f"What is fact {index}?",
                    "choices": ["One", "Two", "Three", "Four"],
                    "answer": "Two",
                }
                for index in range(mcq_count)
            ],
            "flashcards": [
                {"front": f"Front {index}", "back": f"Back {index}"}
                for index in range(flashcard_count)
            ],
        }
    )


class StudyAPITests(unittest.TestCase):
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
                    "study.pdf",
                    make_pdf(["The capital is Dispur.", "Assam is known for tea."]),
                    "application/pdf",
                )
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["document_id"]

    def test_study_endpoint_returns_validated_requested_counts(self) -> None:
        document_id = self.upload_document()
        with patch(
            "app.services.study_service.generate_json_completion",
            return_value=generated_payload(2, 3),
        ):
            response = self.client.post(
                "/api/study",
                json={
                    "document_id": document_id,
                    "mcq_count": 2,
                    "flashcard_count": 3,
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["document_id"], document_id)
        self.assertEqual(len(payload["mcqs"]), 2)
        self.assertEqual(len(payload["flashcards"]), 3)
        self.assertIn(payload["mcqs"][0]["answer"], payload["mcqs"][0]["choices"])

    def test_request_validation_and_missing_document(self) -> None:
        invalid_requests = [
            {"document_id": "not-a-uuid", "mcq_count": 1, "flashcard_count": 1},
            {"document_id": str(uuid4()), "mcq_count": 0, "flashcard_count": 0},
            {"document_id": str(uuid4()), "mcq_count": -1, "flashcard_count": 1},
            {"document_id": str(uuid4()), "mcq_count": 21, "flashcard_count": 1},
        ]
        for request_body in invalid_requests:
            with self.subTest(request=request_body):
                self.assertEqual(
                    self.client.post("/api/study", json=request_body).status_code,
                    422,
                )

        self.assertEqual(
            self.client.post(
                "/api/study",
                json={
                    "document_id": str(uuid4()),
                    "mcq_count": 1,
                    "flashcard_count": 1,
                },
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
                "app.services.study_service.generate_json_completion",
                side_effect=failure,
            ):
                response = self.client.post(
                    "/api/study",
                    json={
                        "document_id": document_id,
                        "mcq_count": 1,
                        "flashcard_count": 1,
                    },
                )
                self.assertEqual(response.status_code, expected_status)


@unittest.skipUnless(
    os.getenv("RUN_LIVE_STUDY_API_TEST") == "1"
    and os.getenv("HF_TOKEN")
    and os.getenv("GROQ_API_KEY"),
    "Set both API keys and RUN_LIVE_STUDY_API_TEST=1 for a live study test.",
)
class LiveStudyAPITests(unittest.TestCase):
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

    def test_live_mcqs_and_flashcards(self) -> None:
        upload = self.client.post(
            "/api/upload",
            files={
                "file": (
                    "live-study.pdf",
                    make_pdf(
                        [
                            "The capital of Assam is Dispur.",
                            "Kaziranga National Park is known for one-horned rhinoceroses.",
                        ]
                    ),
                    "application/pdf",
                )
            },
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        document_id = upload.json()["document_id"]

        response = self.client.post(
            "/api/study",
            json={
                "document_id": document_id,
                "mcq_count": 2,
                "flashcard_count": 2,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload["mcqs"]), 2)
        self.assertEqual(len(payload["flashcards"]), 2)
        for mcq in payload["mcqs"]:
            self.assertEqual(len(mcq["choices"]), 4)
            self.assertIn(mcq["answer"], mcq["choices"])
        for flashcard in payload["flashcards"]:
            self.assertTrue(flashcard["front"].strip())
            self.assertTrue(flashcard["back"].strip())

        self.assertEqual(
            self.client.delete(f"/api/documents/{document_id}").status_code,
            204,
        )


if __name__ == "__main__":
    unittest.main()
