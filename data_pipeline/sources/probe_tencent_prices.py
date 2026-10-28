"""Check Tencent qfq prices and compare their model features with the saved Eastmoney snapshot."""

import argparse
import csv
import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import akshare as ak
import numpy as np

from data_pipeline.samples.build_risk_inputs import price_window
from data_pipeline.samples.build_daily_samples import RAW, STOCKS


def saved_prices(stock):
    path = RAW / f"{stock}_prices_probe.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", choices=STOCKS, default="300750")
    args = parser.parse_args()
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    latest_closed = now.date() if now.time() >= time(15, 30) else now.date() - timedelta(days=1)
    frame = ak.stock_zh_a_hist_tx(
        symbol=args.stock,
        start_date=(latest_closed - timedelta(days=120)).strftime("%Y%m%d"),
        end_date=latest_closed.strftime("%Y%m%d"),
        adjust="qfq",
        timeout=15,
    )
    required = {"date", "open", "close", "high", "low", "volume"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Unexpected Tencent columns: {frame.columns.tolist()}")
    rows = [{
        "日期": str(row["date"]),
        "开盘": float(row["open"]),
        "收盘": float(row["close"]),
        "最高": float(row["high"]),
        "最低": float(row["low"]),
        "成交量": float(row["volume"]),
    } for row in frame.to_dict("records") if str(row["date"]) <= latest_closed.isoformat()]
    if len(rows) < 21:
        raise ValueError(f"Tencent returned only {len(rows)} closed trading days")
    rows.sort(key=lambda row: row["日期"])

    old = saved_prices(args.stock)
    old_dates = {row["日期"]: index for index, row in enumerate(old)}
    common = [row["日期"] for row in rows if row["日期"] in old_dates]
    comparison = None
    if len(common) >= 21:
        day = common[-1]
        old_window = price_window(old, old_dates[day])
        new_window = price_window(rows, next(index for index, row in enumerate(rows) if row["日期"] == day))
        difference = np.abs(old_window - new_window)
        comparison = {
            "date": day,
            "feature_mean_absolute_difference": float(difference.mean()),
            "feature_max_absolute_difference": float(difference.max()),
        }
    print(json.dumps({
        "stock": args.stock,
        "source": "Tencent qfq via AKShare",
        "rows": len(rows),
        "date_range": [rows[0]["日期"], rows[-1]["日期"]],
        "latest_close": rows[-1]["收盘"],
        "overlap_with_saved_eastmoney": len(common),
        "model_feature_comparison": comparison,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
