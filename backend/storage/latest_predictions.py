"""Store the most recent completed live prediction for each stock."""

import json
import sqlite3
from contextlib import closing

from backend.storage.predictions import DB_PATH


def save_latest_prediction(result):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        had_run_history = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'live_prediction_runs'"
        ).fetchone() is not None
        connection.execute("""
            CREATE TABLE IF NOT EXISTS latest_predictions (
                stock TEXT PRIMARY KEY,
                as_of TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS live_prediction_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock TEXT NOT NULL,
                as_of TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS live_prediction_runs_stock_id
            ON live_prediction_runs (stock, id DESC)
        """)
        if not had_run_history:
            connection.execute("""
                INSERT INTO live_prediction_runs (stock, as_of, fetched_at, payload)
                SELECT stock, as_of, fetched_at, payload FROM latest_predictions
            """)
        connection.execute(
            """INSERT INTO latest_predictions (stock, as_of, fetched_at, payload)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(stock) DO UPDATE SET
                   as_of = excluded.as_of,
                   fetched_at = excluded.fetched_at,
                   payload = excluded.payload""",
            (
                result["stock"]["code"],
                result["as_of"],
                result["fetched_at"],
                json.dumps(result, ensure_ascii=False),
            ),
        )
        connection.execute(
            "INSERT INTO live_prediction_runs (stock, as_of, fetched_at, payload) VALUES (?, ?, ?, ?)",
            (
                result["stock"]["code"],
                result["as_of"],
                result["fetched_at"],
                json.dumps(result, ensure_ascii=False),
            ),
        )


def read_latest_prediction(stock):
    if not DB_PATH.is_file():
        return None
    with closing(sqlite3.connect(DB_PATH)) as connection:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'latest_predictions'"
        ).fetchone()
        if table is None:
            return None
        row = connection.execute(
            "SELECT payload FROM latest_predictions WHERE stock = ?", (stock,)
        ).fetchone()
    return json.loads(row[0]) if row else None


def read_prediction_runs():
    if not DB_PATH.is_file():
        return {"total": 0, "items": []}
    with closing(sqlite3.connect(DB_PATH)) as connection:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'live_prediction_runs'"
        ).fetchone()
        if table is None:
            latest_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'latest_predictions'"
            ).fetchone()
            rows = connection.execute(
                "SELECT payload FROM latest_predictions ORDER BY fetched_at DESC"
            ).fetchall() if latest_table else []
            return {"total": len(rows), "items": [{"id": -index, **json.loads(row[0])} for index, row in enumerate(rows)]}
        total = connection.execute("SELECT COUNT(*) FROM live_prediction_runs").fetchone()[0]
        rows = connection.execute(
            "SELECT id, payload FROM live_prediction_runs ORDER BY id DESC"
        ).fetchall()
    return {"total": total, "items": [{"id": row[0], **json.loads(row[1])} for row in rows]}
