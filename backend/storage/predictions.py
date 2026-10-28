"""Read historical predictions from the local SQLite database."""

import sqlite3
from contextlib import closing
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "app.db"


def read_predictions(stock):
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM historical_predictions WHERE stock = ? ORDER BY date",
            (stock,),
        ).fetchall()
    return [dict(row) for row in rows]
