"""Checks for the per-stock saved live result."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.storage import latest_predictions


class LatestPredictionStorageTests(unittest.TestCase):
    def test_save_and_replace_one_stock_without_touching_another(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "app.db"
            with patch.object(latest_predictions, "DB_PATH", database):
                self.assertIsNone(latest_predictions.read_latest_prediction("300750"))
                first = self.result("300750", "2026-10-16", "未触发预警")
                other = self.result("002594", "2026-10-16", "触发预警")
                latest_predictions.save_latest_prediction(first)
                latest_predictions.save_latest_prediction(other)
                updated = self.result("300750", "2026-10-19", "触发预警")
                latest_predictions.save_latest_prediction(updated)
                latest_predictions.save_latest_prediction(updated)

                self.assertEqual(latest_predictions.read_latest_prediction("300750"), updated)
                self.assertEqual(latest_predictions.read_latest_prediction("002594"), other)
                self.assertIsNone(latest_predictions.read_latest_prediction("600519"))
                runs = latest_predictions.read_prediction_runs()
                self.assertEqual(runs["total"], 4)
                self.assertEqual([item["as_of"] for item in runs["items"]],
                                 ["2026-10-19", "2026-10-19", "2026-10-16", "2026-10-16"])
                self.assertEqual([item["stock"]["code"] for item in runs["items"]],
                                 ["300750", "300750", "002594", "300750"])

    def test_existing_saved_result_is_included_before_new_run(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "app.db"
            old = self.result("300750", "2026-10-16", "未触发预警")
            with patch.object(latest_predictions, "DB_PATH", database):
                with sqlite3.connect(database) as connection:
                    connection.execute("""
                        CREATE TABLE latest_predictions (
                            stock TEXT PRIMARY KEY, as_of TEXT NOT NULL,
                            fetched_at TEXT NOT NULL, payload TEXT NOT NULL
                        )
                    """)
                    connection.execute(
                        "INSERT INTO latest_predictions VALUES (?, ?, ?, ?)",
                        ("300750", old["as_of"], old["fetched_at"], json.dumps(old)),
                    )
                self.assertEqual(latest_predictions.read_prediction_runs()["total"], 1)
                new = self.result("300750", "2026-10-19", "触发预警")
                latest_predictions.save_latest_prediction(new)
                self.assertEqual(
                    [item["as_of"] for item in latest_predictions.read_prediction_runs()["items"]],
                    ["2026-10-19", "2026-10-16"],
                )

    @staticmethod
    def result(stock, as_of, status):
        return {
            "stock": {"code": stock, "name": "测试股票"},
            "as_of": as_of,
            "fetched_at": "2026-10-19T18:00:00+08:00",
            "status": status,
        }


if __name__ == "__main__":
    unittest.main()
