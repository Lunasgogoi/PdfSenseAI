"""API tests for Module 11 authentication and persisted account behavior."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.dependencies import get_repository
from app.main import app
from tests.fakes import FakeAccountRepository


class AuthenticationAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_jwt_secret_key = settings.jwt_secret_key
        self.previous_auth_cookie_secure = settings.auth_cookie_secure
        settings.jwt_secret_key = "test-secret-key-that-is-at-least-32-characters"
        settings.auth_cookie_secure = False
        self.repository = FakeAccountRepository()
        app.dependency_overrides[get_repository] = lambda: self.repository
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.pop(get_repository, None)
        settings.jwt_secret_key = self.previous_jwt_secret_key
        settings.auth_cookie_secure = self.previous_auth_cookie_secure

    def test_register_cookie_session_logout_and_login(self) -> None:
        credentials = {"email": "New.Reader@Example.com", "password": "good-password"}

        registered = self.client.post("/api/auth/register", json=credentials)
        self.assertEqual(registered.status_code, 201, registered.text)
        self.assertEqual(registered.json()["user"]["email"], "new.reader@example.com")
        self.assertEqual(registered.json()["token_type"], "bearer")
        self.assertTrue(registered.json()["access_token"])
        self.assertIn("HttpOnly", registered.headers["set-cookie"])

        current = self.client.get("/api/auth/me")
        self.assertEqual(current.status_code, 200, current.text)
        self.assertEqual(current.json()["quota"]["documents_used"], 0)

        duplicate = self.client.post("/api/auth/register", json=credentials)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["code"], "user_already_exists")

        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        unauthenticated = self.client.get("/api/auth/me")
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(unauthenticated.json()["code"], "authentication_required")
        self.assertEqual(unauthenticated.headers["www-authenticate"], "Bearer")

        wrong_password = self.client.post(
            "/api/auth/login",
            json={**credentials, "password": "wrong-password"},
        )
        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(wrong_password.json()["code"], "invalid_credentials")

        logged_in = self.client.post("/api/auth/login", json=credentials)
        self.assertEqual(logged_in.status_code, 200, logged_in.text)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)

    def test_protected_routes_reject_missing_sessions(self) -> None:
        response = self.client.get("/api/documents")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "authentication_required")


if __name__ == "__main__":
    unittest.main()
