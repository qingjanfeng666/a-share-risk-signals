"""Check the live data needed for one on-demand prediction without saving it."""

import argparse
import json
import re

from backend.services.live_sources import fetch_live_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", default="300750", help="Six-digit A-share stock code")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]{6}", args.stock):
        parser.error("--stock must be a six-digit A-share code")
    snapshot = fetch_live_sources(args.stock)
    news_times = sorted(str(row["发布时间"]) for row in snapshot["news"] if row.get("发布时间"))
    print(json.dumps({
        "stock": args.stock,
        "as_of": snapshot["as_of"],
        "fetched_at": snapshot["fetched_at"],
        "price_source": snapshot["price_source"],
        "price_rows": len(snapshot["prices"]),
        "price_range": [str(snapshot["prices"][0]["日期"]), str(snapshot["prices"][-1]["日期"])],
        "announcements_fetched": snapshot["announcements_fetched"],
        "announcements_for_prediction_day": len(snapshot["announcements"]),
        "news_rows": len(snapshot["news"]),
        "news_time_range": [news_times[0], news_times[-1]] if news_times else [None, None],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
