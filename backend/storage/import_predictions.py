"""Import the frozen test predictions into the runtime SQLite database."""

import csv
import sqlite3
from contextlib import closing
from pathlib import Path

from backend.storage.predictions import DB_PATH


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "processed" / "risk_pdf_test_predictions.csv"
COLUMNS = ("stock", "date", "label", "price_score", "price_alert",
           "text_score", "text_alert", "fusion_score", "fusion_alert")


def main():
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(COLUMNS).issubset(reader.fieldnames or []):
            raise ValueError(f"Unexpected prediction columns: {reader.fieldnames}")
        rows = [(
            row["stock"], row["date"], int(row["label"]),
            float(row["price_score"]), int(row["price_alert"]),
            float(row["text_score"]), int(row["text_alert"]),
            float(row["fusion_score"]), int(row["fusion_alert"]),
        ) for row in reader]
    if not rows:
        raise ValueError(f"No predictions in {SOURCE}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS historical_predictions (
                stock TEXT NOT NULL,
                date TEXT NOT NULL,
                label INTEGER NOT NULL,
                price_score REAL NOT NULL,
                price_alert INTEGER NOT NULL,
                text_score REAL NOT NULL,
                text_alert INTEGER NOT NULL,
                fusion_score REAL NOT NULL,
                fusion_alert INTEGER NOT NULL,
                PRIMARY KEY (stock, date)
            )
        """)
        connection.execute("DELETE FROM historical_predictions")
        connection.executemany(
            "INSERT INTO historical_predictions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    print(f"Imported {len(rows)} historical predictions into {DB_PATH}")


if __name__ == "__main__":
    main()
