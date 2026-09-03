"""Tests for Module 9 health, centralized errors, and structured logging."""

from __future__ import annotations

import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.logging import JsonFormatter
from app.main import app
from app.services.document_service import DocumentNotFoundError
from tests.fakes import install_test_auth, remove_test_auth


class QualityAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.previous_upload_dir = settings.upload_dir
        self.previous_vector_store_dir = settings.vector_store_dir
        self.previous_hf_token = settings.hf_token
        self.previous_groq_api_key = settings.groq_api_key
        self.previous_mongodb_uri = settings.mongodb_uri
        self.previous_jwt_secret_key = settings.jwt_secret_key
        settings.upload_dir = root / "uploads"
        settings.vector_store_dir = root / "vector_store"
        settings.hf_token = "test-hf-token"
        settings.groq_api_key = "test-groq-key"
        settings.mongodb_uri = "mongodb://test.invalid"
        settings.jwt_secret_key = "test-secret-key-that-is-at-least-32-characters"
        self.account_repository = install_test_auth(app)
        self.repository_patcher = patch(
            "app.routes.health.get_account_repository",
            return_value=self.account_repository,
        )
        self.repository_patcher.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.repository_patcher.stop()
        remove_test_auth(app)
        settings.upload_dir = self.previous_upload_dir
        settings.vector_store_dir = self.previous_vector_store_dir
        settings.hf_token = self.previous_hf_token
        settings.groq_api_key = self.previous_groq_api_key
        settings.mongodb_uri = self.previous_mongodb_uri
        settings.jwt_secret_key = self.previous_jwt_secret_key
        self.temporary_directory.cleanup()

    def test_liveness_and_readiness_are_safe_and_machine_readable(self) -> None:
        liveness = self.client.get("/api/health")
        readiness = self.client.get("/api/health/ready")

        self.assertEqual(liveness.status_code, 200)
        self.assertEqual(liveness.json(), {"status": "ok"})
        self.assertIn("X-Request-ID", liveness.headers)
        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(readiness.json()["status"], "ready")
        self.assertEqual(
            readiness.json()["checks"],
            {
                "storage": "ready",
                "hugging_face": "configured",
                "groq": "configured",
                "mongodb": "ready",
                "authentication": "configured",
            },
        )

    def test_readiness_reports_missing_configuration_without_exposing_secrets(self) -> None:
        settings.hf_token = None
        response = self.client.get("/api/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "not_ready")
        self.assertEqual(response.json()["checks"]["hugging_face"], "missing")
        self.assertNotIn("test-groq-key", response.text)

    def test_service_errors_use_the_central_error_envelope(self) -> None:
        with (
            patch.object(self.account_repository, "assert_document_owner"),
            patch(
                "app.routes.documents.get_document",
                side_effect=DocumentNotFoundError("Document not found."),
            ),
        ):
            response = self.client.get(f"/api/documents/{uuid4()}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"detail": "Document not found.", "code": "document_not_found"},
        )


class StructuredLoggingTests(unittest.TestCase):
    def test_json_formatter_emits_context_as_valid_json(self) -> None:
        record = logging.makeLogRecord(
            {
                "name": "pdfsense.requests",
                "levelno": logging.INFO,
                "levelname": "INFO",
                "msg": "request_completed",
                "request_id": "request-123",
                "status_code": 200,
            }
        )

        payload = json.loads(JsonFormatter().format(record))

        self.assertEqual(payload["message"], "request_completed")
        self.assertEqual(payload["request_id"], "request-123")
        self.assertEqual(payload["status_code"], 200)
        self.assertIn("timestamp", payload)


if __name__ == "__main__":
    unittest.main()
