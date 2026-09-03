"""Offline and opt-in live tests for the hosted embedding engine."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import numpy as np

from app.core.config import settings
from app.services import embedding_service


class FakeInferenceClient:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def feature_extraction(self, texts, **options):
        batch = list(texts)
        self.calls.append((batch, options))
        base = np.arange(1, settings.embedding_dimension + 1, dtype=np.float32)
        return np.stack([base * (index + 1) for index in range(len(batch))])


class EmbeddingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_model_name = settings.embedding_model_name
        self.previous_provider = settings.embedding_provider
        self.previous_dimension = settings.embedding_dimension
        self.previous_batch_size = settings.embedding_batch_size
        self.previous_timeout = settings.embedding_timeout_seconds
        self.previous_token = settings.hf_token
        settings.embedding_model_name = "mixedbread-ai/mxbai-embed-large-v1"
        settings.embedding_provider = "hf-inference"
        settings.embedding_dimension = 1024
        settings.embedding_batch_size = 2
        settings.embedding_timeout_seconds = 30
        settings.hf_token = "test-token"
        embedding_service.clear_embedding_client_cache()

    def tearDown(self) -> None:
        embedding_service.clear_embedding_client_cache()
        settings.embedding_model_name = self.previous_model_name
        settings.embedding_provider = self.previous_provider
        settings.embedding_dimension = self.previous_dimension
        settings.embedding_batch_size = self.previous_batch_size
        settings.embedding_timeout_seconds = self.previous_timeout
        settings.hf_token = self.previous_token

    def test_document_embeddings_are_batched_normalized_and_float32(self) -> None:
        fake_client = FakeInferenceClient()
        with patch.object(
            embedding_service,
            "_create_embedding_client",
            return_value=fake_client,
        ) as create_client:
            vectors = embedding_service.embed_documents(
                ["First chunk", "Second chunk", "Third chunk"]
            )
            embedding_service.embed_documents(["Fourth chunk"])

        self.assertEqual(vectors.shape, (3, 1024))
        self.assertEqual(vectors.dtype, np.float32)
        np.testing.assert_allclose(
            np.linalg.norm(vectors, axis=1),
            np.ones(3),
            rtol=1e-5,
        )
        create_client.assert_called_once_with("hf-inference", "test-token", 30)
        self.assertEqual([len(call[0]) for call in fake_client.calls], [2, 1, 1])
        self.assertTrue(fake_client.calls[0][1]["normalize"])
        self.assertEqual(fake_client.calls[0][1]["dimensions"], 1024)
        self.assertEqual(
            fake_client.calls[0][1]["model"],
            "mixedbread-ai/mxbai-embed-large-v1",
        )
        self.assertNotIn("prompt_name", fake_client.calls[0][1])

    def test_query_embedding_uses_mixedbread_query_prompt(self) -> None:
        fake_client = FakeInferenceClient()
        with patch.object(
            embedding_service,
            "_create_embedding_client",
            return_value=fake_client,
        ):
            vector = embedding_service.embed_query("What is the revenue?")

        self.assertEqual(vector.shape, (1024,))
        self.assertAlmostEqual(float(np.linalg.norm(vector)), 1.0, places=5)
        self.assertEqual(fake_client.calls[0][1]["prompt_name"], "query")

    def test_missing_token_is_rejected_before_client_creation(self) -> None:
        settings.hf_token = None
        with patch.object(
            embedding_service,
            "_create_embedding_client",
        ) as create_client:
            with self.assertRaises(
                embedding_service.EmbeddingConfigurationError
            ):
                embedding_service.embed_documents(["Document text"])

        create_client.assert_not_called()

    def test_invalid_input_is_rejected_before_client_creation(self) -> None:
        with patch.object(
            embedding_service,
            "_create_embedding_client",
        ) as create_client:
            for invalid_documents in ([], [""], ["   "]):
                with self.assertRaises(
                    embedding_service.InvalidEmbeddingInputError
                ):
                    embedding_service.embed_documents(invalid_documents)

            with self.assertRaises(embedding_service.InvalidEmbeddingInputError):
                embedding_service.embed_query("  ")

        create_client.assert_not_called()

    def test_client_creation_failure_is_wrapped(self) -> None:
        with patch.object(
            embedding_service,
            "_create_embedding_client",
            side_effect=OSError("client unavailable"),
        ):
            with self.assertRaises(
                embedding_service.EmbeddingConfigurationError
            ):
                embedding_service.embed_documents(["Document text"])

    def test_api_failure_is_wrapped(self) -> None:
        client = FakeInferenceClient()
        client.feature_extraction = lambda texts, **options: (_ for _ in ()).throw(
            TimeoutError("request timed out")
        )
        with patch.object(
            embedding_service,
            "_create_embedding_client",
            return_value=client,
        ):
            with self.assertRaises(embedding_service.EmbeddingGenerationError):
                embedding_service.embed_documents(["Document text"])

    def test_invalid_api_output_is_rejected(self) -> None:
        client = FakeInferenceClient()
        client.feature_extraction = lambda texts, **options: np.ones((len(texts), 10))
        with patch.object(
            embedding_service,
            "_create_embedding_client",
            return_value=client,
        ):
            with self.assertRaises(embedding_service.EmbeddingGenerationError):
                embedding_service.embed_documents(["Document text"])


@unittest.skipUnless(
    os.getenv("RUN_LIVE_EMBEDDING_API_TEST") == "1" and os.getenv("HF_TOKEN"),
    "Set HF_TOKEN and RUN_LIVE_EMBEDDING_API_TEST=1 for a live API test.",
)
class LiveEmbeddingAPITests(unittest.TestCase):
    def test_mixedbread_api_dimensions_and_normalization(self) -> None:
        embedding_service.clear_embedding_client_cache()
        document_vectors = embedding_service.embed_documents(
            ["The capital of Assam is Dispur."]
        )
        query_vector = embedding_service.embed_query("What is Assam's capital?")

        self.assertEqual(document_vectors.shape, (1, 1024))
        self.assertEqual(query_vector.shape, (1024,))
        self.assertAlmostEqual(
            float(np.linalg.norm(document_vectors[0])),
            1.0,
            places=5,
        )
        self.assertAlmostEqual(float(np.linalg.norm(query_vector)), 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
