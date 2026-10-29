"""Keep saved live observations separate for each account."""

import json
import sqlite3
from contextlib import closing

from backend.storage.predictions import DB_PATH


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_latest_predictions (
            user_id INTEGER NOT NULL,
            stock TEXT NOT NULL,
            as_of TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (user_id, stock)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_prediction_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            stock TEXT NOT NULL,
            as_of TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            payload TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS user_prediction_runs_user_id
        ON user_prediction_runs (user_id, id DESC)
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_daily_observations (
            user_id INTEGER NOT NULL,
            stock TEXT NOT NULL,
            as_of TEXT NOT NULL,
            feature_set TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('ready', 'missing')),
            price_score REAL,
            fusion_score REAL,
            price_alert INTEGER,
            fusion_alert INTEGER,
            error TEXT,
            PRIMARY KEY (user_id, stock, as_of, feature_set)
        )
    """)
    return connection


def save_latest_prediction(user_id, result):
    stock = result["stock"]["code"]
    payload = json.dumps(result, ensure_ascii=False)
    with closing(_connect()) as connection, connection:
        connection.execute("""
            INSERT INTO user_latest_predictions (user_id, stock, as_of, fetched_at, payload)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, stock) DO UPDATE SET
                as_of = excluded.as_of,
                fetched_at = excluded.fetched_at,
                payload = excluded.payload
        """, (user_id, stock, result["as_of"], result["fetched_at"], payload))
        connection.execute("""
            INSERT INTO user_prediction_runs (user_id, stock, as_of, fetched_at, payload)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, stock, result["as_of"], result["fetched_at"], payload))


def read_latest_prediction(user_id, stock):
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT payload FROM user_latest_predictions WHERE user_id = ? AND stock = ?",
            (user_id, stock),
        ).fetchone()
    return json.loads(row["payload"]) if row else None


def read_prediction_runs(user_id, limit=100):
    with closing(_connect()) as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM user_prediction_runs WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        rows = connection.execute("""
            SELECT id, payload FROM user_prediction_runs
            WHERE user_id = ? ORDER BY id DESC LIMIT ?
        """, (user_id, limit)).fetchall()
    return {"total": total, "items": [{"id": row["id"], **json.loads(row["payload"])} for row in rows]}


def save_observation(user_id, stock, as_of, predictions=None, error=None, feature_set="pdf"):
    ready = predictions is not None
    with closing(_connect()) as connection, connection:
        connection.execute("""
            INSERT INTO user_daily_observations
                (user_id, stock, as_of, feature_set, status, price_score, fusion_score,
                 price_alert, fusion_alert, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, stock, as_of, feature_set) DO UPDATE SET
                status = excluded.status,
                price_score = excluded.price_score,
                fusion_score = excluded.fusion_score,
                price_alert = excluded.price_alert,
                fusion_alert = excluded.fusion_alert,
                error = excluded.error
        """, (
            user_id, stock, as_of, feature_set, "ready" if ready else "missing",
            predictions["price"]["score"] if ready else None,
            predictions["fusion"]["score"] if ready else None,
            int(predictions["price"]["alert"]) if ready else None,
            int(predictions["fusion"]["alert"]) if ready else None,
            None if ready else str(error),
        ))


def read_observations(user_id, stock, limit=30, feature_set="pdf"):
    with closing(_connect()) as connection:
        rows = connection.execute("""
            SELECT as_of, status, price_score, fusion_score,
                   price_alert, fusion_alert, error
            FROM user_daily_observations
            WHERE user_id = ? AND stock = ? AND feature_set = ?
            ORDER BY as_of DESC LIMIT ?
        """, (user_id, stock, feature_set, limit)).fetchall()
    return [dict(row) for row in reversed(rows)]


def read_trend(user_id, stock, feature_set="pdf"):
    rows = read_observations(user_id, stock, feature_set=feature_set)
    return {"stock": stock, "feature_set": feature_set, "total": len(rows), "items": rows}


def first_observation_date(user_id, stock, feature_set="pdf"):
    with closing(_connect()) as connection:
        row = connection.execute("""
            SELECT MIN(as_of) FROM user_daily_observations
            WHERE user_id = ? AND stock = ? AND feature_set = ?
        """, (user_id, stock, feature_set)).fetchone()
    return row[0]
