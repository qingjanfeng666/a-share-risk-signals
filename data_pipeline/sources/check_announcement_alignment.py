"""Measure announcement coverage against saved daily-price data."""

import argparse
import csv
import json
from bisect import bisect_left, bisect_right
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path


RAW = Path(__file__).resolve().parents[2] / "data" / "raw"


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", default="300750")
    parser.add_argument("--start", default="20250101")
    parser.add_argument("--end", default="20250331")
    args = parser.parse_args()

    announcements = read_rows(
        RAW / f"{args.stock}_announcements_{args.start}_{args.end}.csv"
    )
    prices = read_rows(RAW / f"{args.stock}_prices_probe.csv")
    trading_days = sorted(date.fromisoformat(row["日期"]) for row in prices)
    start_day = datetime.strptime(args.start, "%Y%m%d").date()
    end_day = datetime.strptime(args.end, "%Y%m%d").date()

    counts = Counter()
    assigned_days = Counter()
    for row in announcements:
        published_at = datetime.fromisoformat(row["公告时间"])
        day = published_at.date()
        after_close = published_at.time() >= time(15, 0)
        date_only = published_at.time() == time(0, 0)
        position = (
            bisect_right(trading_days, day)
            if after_close or date_only
            else bisect_left(trading_days, day)
        )
        if after_close:
            counts["published_after_close"] += 1
        if date_only:
            counts["date_only_timestamp"] += 1
        if position == len(trading_days):
            counts["without_following_trading_day"] += 1
            continue
        assigned = trading_days[position]
        assigned_days[assigned] += 1
        counts["aligned"] += 1
        if assigned != day:
            counts["shifted_to_later_trading_day"] += 1

    period_days = [day for day in trading_days if start_day <= day <= end_day]
    print(
        json.dumps(
            {
                "stock": args.stock,
                "announcements": len(announcements),
                "aligned": counts["aligned"],
                "published_after_close": counts["published_after_close"],
                "date_only_timestamp": counts["date_only_timestamp"],
                "shifted_to_later_trading_day": counts[
                    "shifted_to_later_trading_day"
                ],
                "without_following_trading_day": counts[
                    "without_following_trading_day"
                ],
                "trading_days_in_period": len(period_days),
                "trading_days_with_announcements": sum(
                    day in assigned_days for day in period_days
                ),
                "max_announcements_on_one_trading_day": max(
                    assigned_days.values(), default=0
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
