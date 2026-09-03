"""Integration tests for the Module 5 chat API."""

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
from app.services.rag_service import NOT_FOUND_ANSWER
from tests.test_document_ingestion import make_pdf


class ChatAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temporary_root = Path(self.temporary_directory.name)
        self.previous_upload_dir = settings.upload_dir
        self.previous_vector_store_dir = settings.vector_store_dir
        self.previous_dimension = settings.embedding_dimension
        self.previous_model_name = settings.embedding_model_name
        self.previous_rag_top_k = settings.rag_top_k
        settings.upload_dir = self.temporary_root / "uploads"
        settings.vector_store_dir = self.temporary_root / "vector_store"
        settings.embedding_dimension = 3
        settings.embedding_model_name = "test/mxbai"
        settings.rag_top_k = 5
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
        settings.rag_top_k = self.previous_rag_top_k
        self.temporary_directory.cleanup()

    @staticmethod
    def _document_embeddings(texts: list[str]) -> np.ndarray:
        vectors = []
        for text in texts:
            if "revenue" in text.lower():
                vectors.append([1.0, 0.0, 0.0])
            else:
                vectors.append([0.0, 1.0, 0.0])
        return np.asarray(vectors, dtype=np.float32)

    def upload_document(self) -> dict[str, object]:
        response = self.client.post(
            "/api/upload",
            files={
                "file": (
                    "report.pdf",
                    make_pdf(
                        [
                            "The company was founded in 2018.",
                            "Annual revenue increased by ten percent.",
                        ]
                    ),
                    "application/pdf",
                )
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def chat(self, document_id: str, query: str = "How did revenue change?"):
        return self.client.post(
            "/api/chat",
            json={"document_id": document_id, "query": query},
        )

    def test_chat_returns_citation_page_from_retrieved_metadata(self) -> None:
        document = self.upload_document()
        with patch(
            "app.services.retrieval_service.embed_query",
            return_value=np.array([1.0, 0.0, 0.0], dtype=np.float32),
        ), patch(
            "app.services.rag_service.generate_json_completion",
            return_value=(
                '{"answer":"Revenue increased by ten percent.",'
                '"source_ids":["S1"]}'
            ),
        ):
            response = self.chat(str(document["document_id"]))

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["document_id"], document["document_id"])
        self.assertEqual(payload["answer"], "Revenue increased by ten percent.")
        self.assertEqual(len(payload["citations"]), 1)
        self.assertEqual(payload["citations"][0]["page_number"], 2)
        self.assertIn("revenue", payload["citations"][0]["excerpt"].lower())
        self.assertTrue(
            payload["citations"][0]["chunk_id"].startswith(document["document_id"])
        )

    def test_out_of_document_answer_is_explicit(self) -> None:
        document = self.upload_document()
        with patch(
            "app.services.retrieval_service.embed_query",
            return_value=np.array([0.0, 1.0, 0.0], dtype=np.float32),
        ), patch(
            "app.services.rag_service.generate_json_completion",
            return_value='{"answer":"NOT_FOUND","source_ids":[]}',
        ):
            response = self.chat(
                str(document["document_id"]),
                "What is the CEO's favorite meal?",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], NOT_FOUND_ANSWER)
        self.assertEqual(response.json()["citations"], [])

    def test_request_validation_and_missing_document(self) -> None:
        self.assertEqual(
            self.client.post(
                "/api/chat",
                json={"document_id": "not-a-uuid", "query": "hello"},
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                "/api/chat",
                json={"document_id": str(uuid4()), "query": "   "},
            ).status_code,
            422,
        )
        self.assertEqual(self.chat(str(uuid4()), "hello").status_code, 404)

    def test_llm_failures_have_stable_http_statuses(self) -> None:
        document = self.upload_document()
        query_vector = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        failures = [
            (LLMConfigurationError("Missing key."), 503),
            (LLMRateLimitError("Rate limited."), 429),
            (LLMTimeoutError("Timed out."), 502),
            (LLMProviderError("Provider failed."), 502),
            (LLMResponseError("Malformed response."), 502),
        ]
        for failure, expected_status in failures:
            with self.subTest(failure=type(failure).__name__), patch(
                "app.services.retrieval_service.embed_query",
                return_value=query_vector,
            ), patch(
                "app.services.rag_service.generate_json_completion",
                side_effect=failure,
            ):
                response = self.chat(str(document["document_id"]))
                self.assertEqual(response.status_code, expected_status)

@unittest.skipUnless(
    os.getenv("RUN_LIVE_RAG_API_TEST") == "1"
    and os.getenv("HF_TOKEN")
    and os.getenv("GROQ_API_KEY"),
    "Set both API keys and RUN_LIVE_RAG_API_TEST=1 for a live RAG test.",
)
class LiveRAGAPITests(unittest.TestCase):
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

    def test_live_upload_retrieval_answer_and_citation(self) -> None:
        upload = self.client.post(
            "/api/upload",
            files={
                "file": (
                    "live-rag.pdf",
                    make_pdf(
                        [
                            "Project Aurora launches on 14 October 2028.",
                            "The approved budget is 2.5 million dollars.",
                        ]
                    ),
                    "application/pdf",
                )
            },
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        document_id = upload.json()["document_id"]

        chat = self.client.post(
            "/api/chat",
            json={
                "document_id": document_id,
                "query": "When does Project Aurora launch?",
            },
        )
        self.assertEqual(chat.status_code, 200, chat.text)
        payload = chat.json()
        self.assertIn("2028", payload["answer"])
        self.assertTrue(payload["citations"])
        self.assertIn(1, [citation["page_number"] for citation in payload["citations"]])

        self.assertEqual(
            self.client.delete(f"/api/documents/{document_id}").status_code,
            204,
        )


if __name__ == "__main__":
    unittest.main()
