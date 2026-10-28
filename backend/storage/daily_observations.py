"""One current-era model observation per stock and closed trading day."""

import sqlite3
from contextlib import closing

from backend.storage.predictions import DB_PATH


def _create_table(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS daily_observations (
            stock TEXT NOT NULL,
            as_of TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('ready', 'missing')),
            price_score REAL,
            fusion_score REAL,
            price_alert INTEGER,
            fusion_alert INTEGER,
            error TEXT,
            feature_set TEXT NOT NULL DEFAULT 'pdf',
            PRIMARY KEY (stock, as_of, feature_set)
        )
    """)
    schema = list(connection.execute("PRAGMA table_info(daily_observations)"))
    primary_key = [row[1] for row in sorted(schema, key=lambda row: row[5]) if row[5]]
    if primary_key != ["stock", "as_of", "feature_set"]:
        source_feature = "feature_set" if any(row[1] == "feature_set" for row in schema) else "'legacy'"
        connection.execute("""
            CREATE TABLE daily_observations_v2 (
                stock TEXT NOT NULL, as_of TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('ready', 'missing')),
                price_score REAL, fusion_score REAL, price_alert INTEGER,
                fusion_alert INTEGER, error TEXT,
                feature_set TEXT NOT NULL DEFAULT 'pdf',
                PRIMARY KEY (stock, as_of, feature_set)
            )
        """)
        connection.execute(f"""
            INSERT INTO daily_observations_v2
            (stock, as_of, status, price_score, fusion_score, price_alert, fusion_alert, error, feature_set)
            SELECT stock, as_of, status, price_score, fusion_score, price_alert, fusion_alert, error,
                   {source_feature} FROM daily_observations
        """)
        connection.execute("DROP TABLE daily_observations")
        connection.execute("ALTER TABLE daily_observations_v2 RENAME TO daily_observations")


def save_observation(stock, as_of, predictions=None, error=None, feature_set="pdf"):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    ready = predictions is not None
    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        _create_table(connection)
        connection.execute("""
            INSERT INTO daily_observations
                (stock, as_of, status, price_score, fusion_score,
                 price_alert, fusion_alert, error, feature_set)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stock, as_of, feature_set) DO UPDATE SET
                status = excluded.status,
                price_score = excluded.price_score,
                fusion_score = excluded.fusion_score,
                price_alert = excluded.price_alert,
                fusion_alert = excluded.fusion_alert,
                error = excluded.error,
                feature_set = excluded.feature_set
        """, (
            stock, as_of, "ready" if ready else "missing",
            predictions["price"]["score"] if ready else None,
            predictions["fusion"]["score"] if ready else None,
            int(predictions["price"]["alert"]) if ready else None,
            int(predictions["fusion"]["alert"]) if ready else None,
            None if ready else str(error),
            feature_set,
        ))


def read_observations(stock, limit=30, feature_set="pdf"):
    if not DB_PATH.is_file():
        return []
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'daily_observations'"
        ).fetchone():
            return []
        columns = {row[1] for row in connection.execute("PRAGMA table_info(daily_observations)")}
        if "feature_set" not in columns and feature_set != "legacy":
            return []
        filter_sql = "AND feature_set = ?" if "feature_set" in columns else ""
        rows = connection.execute(f"""
            SELECT as_of, status, price_score, fusion_score,
                   price_alert, fusion_alert, error
            FROM daily_observations WHERE stock = ? {filter_sql}
            ORDER BY as_of DESC LIMIT ?
        """, (stock, feature_set, limit) if filter_sql else (stock, limit)).fetchall()
    return [dict(row) for row in reversed(rows)]


def read_trend(stock, feature_set=None):
    feature_set = feature_set or "pdf"
    rows = read_observations(stock, feature_set=feature_set)
    return {"stock": stock, "feature_set": feature_set, "total": len(rows), "items": rows}


def first_observation_date(stock, feature_set="pdf"):
    if not DB_PATH.is_file():
        return None
    with closing(sqlite3.connect(DB_PATH)) as connection:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'daily_observations'"
        ).fetchone():
            return None
        columns = {row[1] for row in connection.execute("PRAGMA table_info(daily_observations)")}
        if "feature_set" not in columns and feature_set != "legacy":
            return None
        filter_sql = "AND feature_set = ?" if "feature_set" in columns else ""
        row = connection.execute(
            f"SELECT MIN(as_of) FROM daily_observations WHERE stock = ? {filter_sql}",
            (stock, feature_set) if filter_sql else (stock,),
        ).fetchone()
    return row[0]
