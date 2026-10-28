"""Build one leakage-safe risk sample per stock and trading day."""

import calendar
import csv
import json
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import date, datetime, time
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
STOCKS = ("300750", "002594", "300059", "600519", "000001")
START = date(2023, 1, 1)
END = date(2025, 12, 31)
SPLITS = (
    ("train", date(2024, 12, 31)),
    ("validation", date(2025, 6, 30)),
    ("test", END),
)
LOOKBACK = 20
HORIZON = 3
RISK_RATIO = 0.95


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def announcement_paths(stock):
    for year in range(START.year, END.year + 1):
        for quarter in range(4):
            first_month = quarter * 3 + 1
            last_month = first_month + 2
            last_day = calendar.monthrange(year, last_month)[1]
            yield RAW / (
                f"{stock}_announcements_{year}{first_month:02d}01_"
                f"{year}{last_month:02d}{last_day:02d}.csv"
            )


def split_for(day):
    return next((name, last) for name, last in SPLITS if day <= last)


def assigned_day(published, trading_days):
    """Use the next trading day when the time is unknown or after close."""
    position = (
        bisect_right(trading_days, published.date())
        if published.time() == time.min or published.time() >= time(15)
        else bisect_left(trading_days, published.date())
    )
    return trading_days[position] if position < len(trading_days) else None


def announcements_by_day(stock, trading_days):
    by_day = defaultdict(list)
    seen = set()
    for path in announcement_paths(stock):
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}; run collect_announcements.py first")
        for row in read_csv(path):
            published = datetime.fromisoformat(row["公告时间"])
            if not START <= published.date() <= END:
                continue
            ids = parse_qs(urlparse(row["公告链接"]).query).get("announcementId")
            if not ids:
                raise ValueError(f"Announcement ID missing: {row['公告链接']}")
            announcement_id = ids[0]
            if announcement_id in seen:
                continue
            seen.add(announcement_id)
            target = assigned_day(published, trading_days)
            if target is not None and START <= target <= END:
                by_day[target].append(announcement_id)
    return by_day


def samples_for(stock):
    prices = sorted(
        (
            row for row in read_csv(RAW / f"{stock}_prices_probe.csv")
            if START <= date.fromisoformat(row["日期"]) <= END
        ),
        key=lambda row: row["日期"],
    )
    trading_days = [date.fromisoformat(row["日期"]) for row in prices]
    if len(trading_days) != len(set(trading_days)):
        raise ValueError(f"Duplicate price date for {stock}")
    announcements = announcements_by_day(stock, trading_days)
    rows = []
    for index in range(LOOKBACK - 1, len(prices) - HORIZON):
        day = trading_days[index]
        future_end = trading_days[index + HORIZON]
        split, split_end = split_for(day)
        if future_end > split_end:
            continue
        close = float(prices[index]["收盘"])
        future_closes = [float(row["收盘"]) for row in prices[index + 1 : index + 1 + HORIZON]]
        if close <= 0 or any(value <= 0 for value in future_closes):
            raise ValueError(f"Invalid close price for {stock} on {day}")
        ids = announcements.get(day, [])
        rows.append(
            {
                "stock": stock,
                "date": day.isoformat(),
                "split": split,
                "lookback_start": trading_days[index - LOOKBACK + 1].isoformat(),
                "future_end": future_end.isoformat(),
                "close": close,
                "announcement_count": len(ids),
                "has_announcement": int(bool(ids)),
                "announcement_ids": "|".join(ids),
                "risk_label": int(min(future_closes) / close <= RISK_RATIO),
            }
        )
    return rows


def summarize(rows):
    result = {}
    for key in (*STOCKS, *(name for name, _ in SPLITS), "all"):
        selected = [
            row for row in rows
            if key == "all" or row["stock"] == key or row["split"] == key
        ]
        counts = Counter(
            (row["risk_label"], row["has_announcement"]) for row in selected
        )
        result[key] = {
            "samples": len(selected),
            "high_risk": counts[(1, 0)] + counts[(1, 1)],
            "with_announcement": counts[(0, 1)] + counts[(1, 1)],
            "high_risk_with_announcement": counts[(1, 1)],
        }
    return result


def main():
    rows = sorted(
        (row for stock in STOCKS for row in samples_for(stock)),
        key=lambda row: (row["date"], row["stock"]),
    )
    PROCESSED.mkdir(parents=True, exist_ok=True)
    output = PROCESSED / "daily_samples_2023_2025.csv"
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "label": "min(next 3 trading-day closes) / current close <= 0.95",
        "lookback_trading_days": LOOKBACK,
        "by_stock_and_split": summarize(rows),
    }
    report = PROCESSED / "daily_samples_summary_2023_2025.json"
    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"csv": str(output.relative_to(ROOT)), "summary": str(report.relative_to(ROOT)), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
