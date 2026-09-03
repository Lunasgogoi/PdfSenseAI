"""Tests for Module 3 per-document FAISS persistence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import numpy as np

from app.core.config import settings
from app.services import vector_service


def make_chunks(document_id: str, texts: list[str]) -> list[dict[str, object]]:
    return [
        {
            "chunk_id": f"{document_id}:{index}",
            "text": text,
            "metadata": {
                "source": "fixture.pdf",
                "page_number": index + 1,
                "page_chunk_index": 0,
                "chunk_index": index,
            },
        }
        for index, text in enumerate(texts)
    ]


class VectorServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temporary_root = Path(self.temporary_directory.name)
        self.previous_vector_store_dir = settings.vector_store_dir
        self.previous_dimension = settings.embedding_dimension
        self.previous_model_name = settings.embedding_model_name
        settings.vector_store_dir = self.temporary_root / "vector_store"
        settings.embedding_dimension = 4
        settings.embedding_model_name = "test/mxbai"

    def tearDown(self) -> None:
        settings.vector_store_dir = self.previous_vector_store_dir
        settings.embedding_dimension = self.previous_dimension
        settings.embedding_model_name = self.previous_model_name
        self.temporary_directory.cleanup()

    def test_index_persists_and_reloads_without_embedding_api(self) -> None:
        document_id = str(uuid4())
        chunks = make_chunks(document_id, ["alpha", "beta"])
        vectors = np.array(
            [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
            dtype=np.float32,
        )

        with patch.object(vector_service, "embed_documents", return_value=vectors):
            metadata = vector_service.build_document_index(document_id, chunks)

        workspace = settings.vector_store_dir / document_id
        self.assertTrue((workspace / "index.faiss").is_file())
        self.assertTrue((workspace / "metadata.json").is_file())
        self.assertEqual(metadata.number_of_vectors, 2)
        self.assertEqual(metadata.index_type, "IndexFlatIP")

        with patch.object(
            vector_service,
            "embed_documents",
            side_effect=AssertionError("Reload must not call the embedding API."),
        ):
            loaded = vector_service.load_document_index(document_id)

        self.assertEqual(loaded.index.d, 4)
        self.assertEqual(loaded.index.ntotal, 2)
        scores, row_ids = loaded.index.search(
            np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
            2,
        )
        self.assertEqual(row_ids[0, 0], 0)
        self.assertAlmostEqual(float(scores[0, 0]), 1.0)
        self.assertEqual(loaded.metadata.rows[0].chunk_id, f"{document_id}:0")
        self.assertEqual(loaded.metadata.rows[0].metadata["page_number"], 1)

    def test_document_indexes_are_strictly_isolated(self) -> None:
        first_id = str(uuid4())
        second_id = str(uuid4())
        first_vectors = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
        second_vectors = np.array([[0.0, 1.0, 0.0, 0.0]], dtype=np.float32)

        with patch.object(
            vector_service,
            "embed_documents",
            side_effect=[first_vectors, second_vectors],
        ):
            vector_service.build_document_index(
                first_id,
                make_chunks(first_id, ["first document only"]),
            )
            vector_service.build_document_index(
                second_id,
                make_chunks(second_id, ["second document only"]),
            )

        first = vector_service.load_document_index(first_id)
        second = vector_service.load_document_index(second_id)
        self.assertEqual(
            [row.chunk_id for row in first.metadata.rows],
            [f"{first_id}:0"],
        )
        self.assertEqual(
            [row.chunk_id for row in second.metadata.rows],
            [f"{second_id}:0"],
        )
        self.assertNotEqual(
            first.metadata.rows[0].text,
            second.metadata.rows[0].text,
        )

    def test_rejects_invalid_chunks_and_non_normalized_vectors(self) -> None:
        document_id = str(uuid4())
        with self.assertRaises(vector_service.InvalidVectorDataError):
            vector_service.build_document_index(document_id, [])

        with patch.object(
            vector_service,
            "embed_documents",
            return_value=np.ones((1, 4), dtype=np.float32),
        ):
            with self.assertRaises(vector_service.InvalidVectorDataError):
                vector_service.build_document_index(
                    document_id,
                    make_chunks(document_id, ["not normalized"]),
                )
        self.assertFalse((settings.vector_store_dir / document_id).exists())

    def test_detects_metadata_from_another_document(self) -> None:
        document_id = str(uuid4())
        vectors = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
        with patch.object(vector_service, "embed_documents", return_value=vectors):
            vector_service.build_document_index(
                document_id,
                make_chunks(document_id, ["document text"]),
            )

        metadata_path = settings.vector_store_dir / document_id / "metadata.json"
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        payload["document_id"] = str(uuid4())
        metadata_path.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaises(vector_service.InvalidVectorDataError):
            vector_service.load_document_index(document_id)

    def test_missing_index_is_reported(self) -> None:
        with self.assertRaises(vector_service.VectorIndexNotFoundError):
            vector_service.load_document_index(str(uuid4()))


if __name__ == "__main__":
    unittest.main()
