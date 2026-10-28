"""Collect CNINFO announcement metadata in restartable quarterly snapshots."""

import argparse
import csv
import json
import time
from datetime import date, timedelta
from pathlib import Path

import akshare as ak
import requests


RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
STOCKS = ("300750", "002594", "300059", "600519", "000001")
COLUMNS = ("代码", "简称", "公告标题", "公告时间", "公告链接")


def quarters(start, end):
    year, quarter = start.year, (start.month - 1) // 3
    while True:
        month = quarter * 3 + 1
        first = date(year, month, 1)
        next_first = date(year + (month == 10), 1 if month == 10 else month + 3, 1)
        last = next_first - timedelta(days=1)
        if first > end:
            break
        yield max(first, start), min(last, end)
        quarter += 1
        if quarter == 4:
            year, quarter = year + 1, 0


def read_count(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return sum(1 for _ in csv.DictReader(stream))


def fetch(stock, period):
    for attempt in range(4):
        try:
            return ak.stock_zh_a_disclosure_report_cninfo(
                symbol=stock,
                market="沪深京",
                start_date=period[0],
                end_date=period[1],
            )
        except (requests.RequestException, ValueError) as error:
            if attempt == 3:
                raise
            wait = (10, 30, 60)[attempt]
            print(
                f"{stock} {period[0]}–{period[1]}: {type(error).__name__}; "
                f"retrying in {wait}s",
                flush=True,
            )
            time.sleep(wait)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stocks", nargs="+", default=STOCKS, choices=STOCKS)
    parser.add_argument("--start", default="20230101")
    parser.add_argument("--end", default="20251231")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    start = date.fromisoformat(f"{args.start[:4]}-{args.start[4:6]}-{args.start[6:]}")
    end = date.fromisoformat(f"{args.end[:4]}-{args.end[4:6]}-{args.end[6:]}")
    if start > end or args.delay < 0:
        parser.error("Invalid date range or delay")

    RAW.mkdir(parents=True, exist_ok=True)
    for stock in args.stocks:
        for first, last in quarters(start, end):
            period = (first.strftime("%Y%m%d"), last.strftime("%Y%m%d"))
            path = RAW / f"{stock}_announcements_{period[0]}_{period[1]}.csv"
            if path.exists() and not args.refresh:
                count, source = read_count(path), "cached"
            else:
                frame = fetch(stock, period)
                if not frame.empty and not set(COLUMNS).issubset(frame.columns):
                    raise ValueError(f"Unexpected columns for {stock}: {frame.columns.tolist()}")
                rows = frame.reindex(columns=COLUMNS).fillna("")
                count, source = len(rows), "downloaded"
                temporary = path.with_suffix(".csv.tmp")
                rows.to_csv(temporary, index=False, encoding="utf-8-sig")
                temporary.replace(path)
                time.sleep(args.delay)
            print(
                json.dumps(
                    {"stock": stock, "period": period, "rows": count, "source": source},
                    ensure_ascii=False,
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
