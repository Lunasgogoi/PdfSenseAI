"""Integration tests for Module 4 semantic retrieval."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import numpy as np
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.document_service import update_document_status
from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingGenerationError,
)
from tests.test_document_ingestion import make_pdf


class RetrievalAPITests(unittest.TestCase):
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
        self.document_embedding_patcher = patch(
            "app.services.vector_service.embed_documents",
            side_effect=self._document_embeddings,
        )
        self.document_embedding_patcher.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.document_embedding_patcher.stop()
        settings.upload_dir = self.previous_upload_dir
        settings.vector_store_dir = self.previous_vector_store_dir
        settings.embedding_dimension = self.previous_dimension
        settings.embedding_model_name = self.previous_model_name
        self.temporary_directory.cleanup()

    @staticmethod
    def _document_embeddings(texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            if "capital" in lowered or "alpha" in lowered:
                vectors.append([1.0, 0.0, 0.0])
            elif "tea" in lowered or "beta" in lowered:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return np.asarray(vectors, dtype=np.float32)

    def upload(self, filename: str, page_texts: list[str]) -> dict[str, object]:
        response = self.client.post(
            "/api/upload",
            files={
                "file": (filename, make_pdf(page_texts), "application/pdf"),
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_known_question_returns_correct_page_and_ranked_metadata(self) -> None:
        document = self.upload(
            "assam.pdf",
            [
                "The capital of Assam is Dispur.",
                "Assam is known for its extensive tea estates.",
                "Kaziranga is home to the one-horned rhinoceros.",
            ],
        )

        with patch(
            "app.services.retrieval_service.embed_query",
            return_value=np.array([0.0, 1.0, 0.0], dtype=np.float32),
        ):
            response = self.client.post(
                f"/api/documents/{document['document_id']}/search",
                json={"query": "What crop is Assam famous for?", "top_k": 2},
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["document_id"], document["document_id"])
        self.assertEqual(payload["query"], "What crop is Assam famous for?")
        self.assertEqual(payload["top_k"], 2)
        self.assertEqual(payload["result_count"], 2)
        self.assertEqual(payload["results"][0]["rank"], 1)
        self.assertEqual(payload["results"][0]["page_number"], 2)
        self.assertIn("tea estates", payload["results"][0]["excerpt"])
        self.assertEqual(payload["results"][0]["similarity_score"], 1.0)
        self.assertTrue(
            payload["results"][0]["chunk_id"].startswith(document["document_id"])
        )

    def test_default_top_k_is_five_and_caps_at_document_size(self) -> None:
        document = self.upload(
            "short.pdf",
            ["The capital is Dispur.", "Tea grows here."],
        )
        with patch(
            "app.services.retrieval_service.embed_query",
            return_value=np.array([1.0, 0.0, 0.0], dtype=np.float32),
        ):
            response = self.client.post(
                f"/api/documents/{document['document_id']}/search",
                json={"query": "capital"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["top_k"], 5)
        self.assertEqual(response.json()["result_count"], 2)

    def test_search_cannot_leak_chunks_between_documents(self) -> None:
        first = self.upload("first.pdf", ["Alpha belongs to the first document."])
        second = self.upload("second.pdf", ["Beta belongs to the second document."])

        with patch(
            "app.services.retrieval_service.embed_query",
            return_value=np.array([1.0, 0.0, 0.0], dtype=np.float32),
        ):
            response = self.client.post(
                f"/api/documents/{second['document_id']}/search",
                json={"query": "Find alpha", "top_k": 5},
            )

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertIn("Beta", results[0]["excerpt"])
        self.assertNotIn("Alpha", results[0]["excerpt"])
        self.assertTrue(results[0]["chunk_id"].startswith(second["document_id"]))
        self.assertFalse(results[0]["chunk_id"].startswith(first["document_id"]))

    def test_request_validation_rejects_bad_query_top_k_and_uuid(self) -> None:
        document_id = uuid4()
        for request_body in (
            {"query": "   "},
            {"query": "valid", "top_k": 0},
            {"query": "valid", "top_k": 21},
        ):
            response = self.client.post(
                f"/api/documents/{document_id}/search",
                json=request_body,
            )
            self.assertEqual(response.status_code, 422)

        self.assertEqual(
            self.client.post(
                "/api/documents/not-a-uuid/search",
                json={"query": "valid"},
            ).status_code,
            422,
        )

    def test_missing_document_and_index_have_clear_status_codes(self) -> None:
        missing_response = self.client.post(
            f"/api/documents/{uuid4()}/search",
            json={"query": "anything"},
        )
        self.assertEqual(missing_response.status_code, 404)

        document = self.upload("missing-index.pdf", ["Alpha text."])
        shutil.rmtree(settings.vector_store_dir / str(document["document_id"]))
        missing_index_response = self.client.post(
            f"/api/documents/{document['document_id']}/search",
            json={"query": "alpha"},
        )
        self.assertEqual(missing_index_response.status_code, 409)

    def test_not_ready_document_returns_conflict(self) -> None:
        document = self.upload("processing.pdf", ["Alpha text."])
        update_document_status(str(document["document_id"]), "ingested")

        response = self.client.post(
            f"/api/documents/{document['document_id']}/search",
            json={"query": "alpha"},
        )
        self.assertEqual(response.status_code, 409)

    def test_embedding_configuration_and_provider_failures_are_mapped(self) -> None:
        document = self.upload("errors.pdf", ["Alpha text."])
        endpoint = f"/api/documents/{document['document_id']}/search"

        with patch(
            "app.services.retrieval_service.embed_query",
            side_effect=EmbeddingConfigurationError("HF_TOKEN is required."),
        ):
            configuration_response = self.client.post(
                endpoint,
                json={"query": "alpha"},
            )
        self.assertEqual(configuration_response.status_code, 503)

        with patch(
            "app.services.retrieval_service.embed_query",
            side_effect=EmbeddingGenerationError("Provider unavailable."),
        ):
            provider_response = self.client.post(
                endpoint,
                json={"query": "alpha"},
            )
        self.assertEqual(provider_response.status_code, 502)


if __name__ == "__main__":
    unittest.main()
