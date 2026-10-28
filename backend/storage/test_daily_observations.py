"""The live trend must not mix stocks or duplicate one trading day."""

import tempfile
import sqlite3
from contextlib import closing
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.storage import daily_observations


class DailyObservationTests(unittest.TestCase):
    def test_one_day_is_replaced_and_missing_day_can_recover(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            with patch.object(daily_observations, "DB_PATH", Path(directory) / "app.db"):
                self.assertIsNone(daily_observations.first_observation_date("300750"))
                daily_observations.save_observation("300750", "2026-10-19", self.predictions(0.4))
                daily_observations.save_observation("300750", "2026-10-20", error="公告抓取失败")
                daily_observations.save_observation("002594", "2026-10-20", self.predictions(0.8))
                daily_observations.save_observation("300750", "2026-10-19", self.predictions(0.5))
                rows = daily_observations.read_observations("300750")
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]["price_score"], 0.5)
                self.assertEqual(rows[1]["status"], "missing")
                self.assertIsNone(rows[1]["fusion_score"])
                self.assertEqual(daily_observations.first_observation_date("300750"), "2026-10-19")
                daily_observations.save_observation("300750", "2026-10-20", self.predictions(0.6))
                self.assertEqual(daily_observations.read_observations("300750")[1]["status"], "ready")
                self.assertEqual(len(daily_observations.read_observations("002594")), 1)
                daily_observations.save_observation("300750", "2026-10-20", self.predictions(0.7), feature_set="legacy")
                self.assertEqual(len(daily_observations.read_observations("300750", feature_set="legacy")), 1)
                self.assertEqual(daily_observations.first_observation_date("300750"), "2026-10-19")
                self.assertEqual(len(daily_observations.read_observations("300750")), 2)

    def test_old_table_migrates_without_losing_rows(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            database = Path(directory) / "app.db"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute("""CREATE TABLE daily_observations (
                    stock TEXT NOT NULL, as_of TEXT NOT NULL, status TEXT NOT NULL,
                    price_score REAL, fusion_score REAL, price_alert INTEGER,
                    fusion_alert INTEGER, error TEXT, PRIMARY KEY (stock, as_of))""")
                connection.execute("INSERT INTO daily_observations (stock, as_of, status) VALUES (?, ?, ?)",
                                   ("300750", "2026-10-19", "missing"))
            with patch.object(daily_observations, "DB_PATH", database):
                daily_observations.save_observation("300750", "2026-10-19", self.predictions(0.8), feature_set="pdf")
                self.assertEqual(daily_observations.read_observations("300750", feature_set="legacy")[0]["status"], "missing")
                self.assertEqual(daily_observations.read_observations("300750", feature_set="pdf")[0]["price_score"], 0.8)

    @staticmethod
    def predictions(score):
        return {
            "price": {"score": score, "alert": False},
            "fusion": {"score": score, "alert": True},
        }


if __name__ == "__main__":
    unittest.main()
