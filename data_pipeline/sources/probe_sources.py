"""Check the assignment's sentiment, news, and daily-price sources in WSL."""

import argparse
import csv
import hashlib
import io
import json
from bisect import bisect_left, bisect_right
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
SENTIMENT_URL = (
    "https://huggingface.co/datasets/Kenpache/"
    "multilingual-financial-sentiment/resolve/main/all_languages_clean.csv"
)


def probe_sentiment():
    snapshot = RAW / "all_languages_clean.csv"
    if snapshot.exists():
        content = snapshot.read_bytes()
        source = "local snapshot"
    else:
        with urlopen(SENTIMENT_URL, timeout=60) as response:
            content = response.read()
        source = "Hugging Face download"
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    required = {"sentence", "label", "source", "language"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError(f"Unexpected sentiment columns: {reader.fieldnames}")
    chinese = [row for row in reader if row["language"] == "zh"]
    RAW.mkdir(parents=True, exist_ok=True)
    if not snapshot.exists():
        snapshot.write_bytes(content)
    return {
        "source": source,
        "chinese_rows": len(chinese),
        "label_counts": dict(Counter(row["label"] for row in chinese)),
        "empty_chinese_sentences": sum(not row["sentence"].strip() for row in chinese),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def parse_date(value):
    return date.fromisoformat(str(value)[:10])


def probe_stock(stock, start, end):
    import akshare as ak

    news = ak.stock_news_em(symbol=stock)
    prices = ak.stock_zh_a_hist(
        symbol=stock, period="daily", start_date=start, end_date=end, adjust="qfq"
    )
    news_required = {"新闻标题", "新闻内容", "发布时间"}
    price_required = {"日期", "收盘", "成交量"}
    if not news_required.issubset(news.columns):
        raise ValueError(f"Unexpected news columns: {news.columns.tolist()}")
    if not price_required.issubset(prices.columns):
        raise ValueError(f"Unexpected price columns: {prices.columns.tolist()}")

    RAW.mkdir(parents=True, exist_ok=True)
    news.to_csv(RAW / f"{stock}_news_probe.csv", index=False, encoding="utf-8-sig")
    prices.to_csv(RAW / f"{stock}_prices_probe.csv", index=False, encoding="utf-8-sig")

    timestamps = []
    for value in news["发布时间"].dropna():
        try:
            timestamps.append(datetime.fromisoformat(str(value)))
        except ValueError:
            pass
    trading_days = sorted(parse_date(value) for value in prices["日期"].dropna())
    aligned = 0
    in_training_period = 0
    training_aligned = 0
    for published_at in timestamps:
        day = published_at.date()
        is_training_period = date(2023, 1, 1) <= day <= date(2025, 12, 31)
        if is_training_period:
            in_training_period += 1
        position = (
            bisect_right(trading_days, day)
            if published_at.time() >= time(15, 0)
            else bisect_left(trading_days, day)
        )
        if trading_days and trading_days[0] <= day and position < len(trading_days):
            aligned += 1
            if is_training_period:
                training_aligned += 1

    return {
        "akshare_version": ak.__version__,
        "news_rows": len(news),
        "news_columns": news.columns.tolist(),
        "news_time_range": [
            min(timestamps).isoformat() if timestamps else None,
            max(timestamps).isoformat() if timestamps else None,
        ],
        "news_with_nonempty_content": sum(
            bool(str(value).strip()) for value in news["新闻内容"].dropna()
        ),
        "news_in_2023_2025": in_training_period,
        "news_in_2023_2025_aligned": training_aligned,
        "news_aligned_to_available_trading_day": aligned,
        "price_rows": len(prices),
        "price_date_range": [
            trading_days[0].isoformat() if trading_days else None,
            trading_days[-1].isoformat() if trading_days else None,
        ],
        "price_columns": prices.columns.tolist(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", default="300750", help="Six-digit A-share stock code")
    parser.add_argument("--start", default="20230101")
    parser.add_argument("--end", default=date.today().strftime("%Y%m%d"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--skip-sentiment", action="store_true")
    mode.add_argument("--sentiment-only", action="store_true")
    args = parser.parse_args()

    result = {"stock": args.stock, "start": args.start, "end": args.end}
    errors = 0
    probes = []
    if not args.skip_sentiment:
        probes.append(("sentiment", probe_sentiment))
    if not args.sentiment_only:
        probes.append(("stock", lambda: probe_stock(args.stock, args.start, args.end)))
    for name, run in probes:
        try:
            result[name] = run()
        except Exception as exc:
            result[name] = {"error": f"{type(exc).__name__}: {exc}"}
            errors += 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
