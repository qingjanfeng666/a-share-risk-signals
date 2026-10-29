"""Account session and per-user storage checks."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.storage import accounts, user_results


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        database = Path(self.directory.name) / "test.db"
        self.account_path = patch.object(accounts, "DB_PATH", database)
        self.result_path = patch.object(user_results, "DB_PATH", database)
        self.account_path.start()
        self.result_path.start()
        self.addCleanup(self.account_path.stop)
        self.addCleanup(self.result_path.stop)
        self.addCleanup(self.directory.cleanup)
        self.client = TestClient(app)

    def register(self, email="person@example.com"):
        return self.client.post("/api/auth/register", json={"email": email, "password": "a long test password"})

    def test_register_session_logout_and_login(self):
        self.assertEqual(self.client.get("/api/risk-runs").status_code, 401)
        response = self.register()
        self.assertEqual(response.status_code, 200)
        self.assertIn("httponly", response.headers["set-cookie"].lower())
        self.assertIn("samesite=lax", response.headers["set-cookie"].lower())
        self.assertEqual(self.client.get("/api/auth/me").json()["email"], "person@example.com")
        second_client = TestClient(app)
        second_client.cookies.update(self.client.cookies)
        self.assertEqual(second_client.get("/api/auth/me").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(second_client.get("/api/auth/me").status_code, 401)
        response = self.client.post("/api/auth/login", json={"email": "person@example.com", "password": "a long test password"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/risk-runs").status_code, 200)

    def test_invalid_credentials_and_origin(self):
        self.assertEqual(self.register().status_code, 200)
        self.assertEqual(self.register().status_code, 409)
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "person@example.com", "password": "incorrect"}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/logout", headers={"Origin": "https://other.example"}).status_code, 403)

    def test_login_rate_limit(self):
        self.register()
        self.client.post("/api/auth/logout")
        payload = {"email": "person@example.com", "password": "incorrect"}
        for _ in range(5):
            self.assertEqual(self.client.post("/api/auth/login", json=payload).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json=payload).status_code, 429)
        unknown = {"email": "unknown@example.com", "password": "a password that no account uses"}
        for _ in range(5):
            self.assertEqual(self.client.post("/api/auth/login", json=unknown).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json=unknown).status_code, 429)

    def test_results_are_account_scoped(self):
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.register()
        user_a = self.client.get("/api/auth/me").json()
        user_results.save_latest_prediction(user_a["id"], {"stock": {"code": "300750"}, "as_of": "2026-10-20", "fetched_at": "now"})
        self.assertEqual(self.client.get("/api/stocks/300750/risk-latest-saved").status_code, 200)
        self.client.post("/api/auth/logout")
        self.register("other@example.com")
        self.assertEqual(self.client.get("/api/stocks/300750/risk-latest-saved").status_code, 404)
        self.assertEqual(self.client.get("/api/risk-runs").json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
