"""Checks for stock-code validation and saved result listing."""

import unittest

from fastapi.testclient import TestClient

from backend.main import app


class RiskRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_invalid_code_is_rejected_before_live_fetch(self):
        response = self.client.get("/api/stocks/abc/risk-latest")
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
