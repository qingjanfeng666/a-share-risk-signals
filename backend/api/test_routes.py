"""Checks for stock-code validation and saved result listing."""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import email_delivery
from backend.storage import accounts, user_results


class RiskRouteTests(unittest.TestCase):
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
        sent_codes = []
        configured = patch.object(email_delivery, "is_configured", return_value=True)
        sender = patch.object(email_delivery, "send_verification_code", side_effect=lambda email, code: sent_codes.append(code))
        configured.start()
        sender.start()
        self.addCleanup(configured.stop)
        self.addCleanup(sender.stop)
        self.assertEqual(self.client.post("/api/auth/register", json={"email": "routes@example.com", "password": "a long test password"}).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/verify", json={"email": "routes@example.com", "code": sent_codes[0]}).status_code, 200)

    def test_invalid_code_is_rejected_before_live_fetch(self):
        response = self.client.post("/api/stocks/abc/risk-latest")
        self.assertEqual(response.status_code, 422)

        response = self.client.post("/api/stocks/abc/risk-refresh")
        self.assertEqual(response.status_code, 422)

    def test_run_history_endpoint_returns_a_list(self):
        response = self.client.get("/api/risk-runs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("total", response.json())
        self.assertIn("items", response.json())

    def test_browser_can_post_refresh(self):
        response = self.client.options(
            "/api/stocks/300750/risk-refresh",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("POST", response.headers["access-control-allow-methods"])


if __name__ == "__main__":
    unittest.main()
