"""Tests for the production frontend mount and container configuration."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import mount_frontend


class StaticFrontendTests(unittest.TestCase):
    def test_built_frontend_is_served_without_shadowing_api_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            static_dir = Path(temporary_directory)
            (static_dir / "index.html").write_text(
                "<!doctype html><title>PdfSense production</title>",
                encoding="utf-8",
            )
            (static_dir / "app.js").write_text("window.pdfSense = true", encoding="utf-8")
            application = FastAPI()

            @application.get("/api/ping")
            def ping() -> dict[str, str]:
                return {"status": "ok"}

            self.assertTrue(mount_frontend(application, static_dir))
            with TestClient(application) as client:
                self.assertEqual(client.get("/api/ping").json(), {"status": "ok"})
                self.assertIn("PdfSense production", client.get("/").text)
                self.assertIn("pdfSense", client.get("/app.js").text)

    def test_missing_bundle_is_not_mounted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            application = FastAPI()
            self.assertFalse(mount_frontend(application, Path(temporary_directory)))


class RuntimeConfigurationTests(unittest.TestCase):
    def test_host_and_port_are_runtime_configurable(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "HOST": "127.0.0.1",
                "PORT": "9000",
                "UPLOAD_DIR": "runtime-uploads",
                "VECTOR_STORE_DIR": "runtime-vectors",
            },
        ):
            runtime_settings = Settings()

        self.assertEqual(runtime_settings.app_host, "127.0.0.1")
        self.assertEqual(runtime_settings.app_port, 9000)
        self.assertEqual(runtime_settings.upload_dir.name, "runtime-uploads")
        self.assertEqual(runtime_settings.vector_store_dir.name, "runtime-vectors")


if __name__ == "__main__":
    unittest.main()
