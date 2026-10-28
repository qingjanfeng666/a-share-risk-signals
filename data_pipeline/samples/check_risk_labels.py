"""Preview the agreed three-trading-day, five-percent risk label."""

import csv
import json
from datetime import date
from pathlib import Path


RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
STOCKS = ("300750", "002594", "300059", "600519", "000001")


def summarize(stock):
    path = RAW / f"{stock}_prices_probe.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = sorted(csv.DictReader(stream), key=lambda row: row["日期"])

    result = {}
    for period, start, end in (
        ("2023_2025", date(2023, 1, 1), date(2025, 12, 31)),
        ("2025_q1", date(2025, 1, 1), date(2025, 3, 31)),
    ):
        total = 0
        high_risk = 0
        for index in range(19, len(rows) - 3):
            day = date.fromisoformat(rows[index]["日期"])
            if not start <= day <= end:
                continue
            close = float(rows[index]["收盘"])
            future_closes = [float(row["收盘"]) for row in rows[index + 1 : index + 4]]
            if close <= 0 or any(value <= 0 for value in future_closes):
                continue
            total += 1
            high_risk += min(future_closes) / close <= 0.95
        result[period] = {
            "samples": total,
            "high_risk": high_risk,
            "high_risk_percent": round(100 * high_risk / total, 2) if total else None,
        }
    return result


def main():
    print(
        json.dumps(
            {
                "definition": "min(close[t+1:t+3]) / close[t] <= 0.95",
                "stocks": {stock: summarize(stock) for stock in STOCKS},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
