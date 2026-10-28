"""Align 20-day price windows and same-day announcement features for risk training."""

import argparse
import csv
import json
import math
from collections import Counter

import numpy as np

from .build_daily_samples import LOOKBACK, PROCESSED, RAW, ROOT, read_csv
from .text_stats import aggregate_sentiment, extra_text_features


def announcement_features(view):
    suffix = "" if view == "title_body" else "_title_only"
    rows = read_csv(PROCESSED / f"announcement_sentiment_features{suffix}.csv")
    with np.load(PROCESSED / f"announcement_embeddings{suffix}.npz", allow_pickle=False) as saved:
        ids = saved["announcement_ids"].astype(str).tolist()
        vectors = saved["embeddings"].astype(np.float32)
    if len(ids) != len(rows) or vectors.shape != (len(rows), 768):
        raise ValueError("Announcement CSV and embedding shapes disagree")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate announcement embedding ID")
    by_id = {}
    for row, announcement_id, vector in zip(rows, ids, vectors):
        if row["announcement_id"] != announcement_id:
            raise ValueError(f"Announcement CSV and embedding order disagree: {announcement_id}")
        by_id[announcement_id] = (row, vector)
    return by_id


def prices_by_stock(stocks):
    result = {}
    for stock in stocks:
        rows = read_csv(RAW / f"{stock}_prices_probe.csv")
        dates = [row["日期"] for row in rows]
        if len(dates) != len(set(dates)) or dates != sorted(dates):
            raise ValueError(f"Price dates are duplicated or out of order: {stock}")
        result[stock] = (rows, {day: index for index, day in enumerate(dates)})
    return result


def price_window(rows, end):
    window = rows[end - LOOKBACK + 1 : end + 1]
    if len(window) != LOOKBACK:
        raise ValueError("Incomplete 20-day price window")
    volumes = [float(row["成交量"]) for row in window]
    typical_volume = float(np.median(volumes))
    if typical_volume <= 0:
        raise ValueError("Invalid price-window volume")
    features = []
    for offset, row in enumerate(window):
        index = end - LOOKBACK + 1 + offset
        previous_close = float(rows[index - 1]["收盘"]) if index else float(row["收盘"])
        values = [float(row[column]) for column in ("收盘", "开盘", "最高", "最低")]
        volume = float(row["成交量"])
        if previous_close <= 0 or min(values + [volume]) <= 0:
            raise ValueError(f"Invalid price or volume on {row['日期']}")
        features.append([*(math.log(value / previous_close) for value in values),
                         math.log(volume / typical_volume)])
    return np.asarray(features, dtype=np.float32)


def text_vector(sample, by_id):
    return text_vector_and_stats(sample, by_id)[0]


def text_vector_and_stats(sample, by_id):
    ids = sample["announcement_ids"].split("|") if sample["announcement_ids"] else []
    if len(ids) != int(sample["announcement_count"]):
        raise ValueError(f"Announcement count differs from IDs: {sample['stock']} {sample['date']}")
    if not ids:
        return np.zeros(772, dtype=np.float32), aggregate_sentiment([])
    vectors = []
    scores = []
    for announcement_id in ids:
        row, vector = by_id[announcement_id]
        if row["stock"] != sample["stock"] or row["split"] != sample["split"]:
            raise ValueError(f"Announcement stock/split mismatch: {announcement_id}")
        vectors.append(vector)
        scores.append([float(row[f"sentiment_{label}"])
                       for label in ("negative", "neutral", "positive")])
    vector = np.concatenate((np.mean(vectors, axis=0), np.mean(scores, axis=0),
                             [math.log1p(len(ids))])).astype(np.float32)
    return vector, aggregate_sentiment(scores)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-view", choices=("title_body", "title_only"), default="title_body")
    args = parser.parse_args()

    from .market_indicators import MARKET_FEATURES, market_window

    samples = read_csv(PROCESSED / "daily_samples_2023_2025.csv")
    by_id = announcement_features(args.text_view)
    prices = prices_by_stock({sample["stock"] for sample in samples})
    sequences = []
    news = []
    stats_rows = []
    selected_samples = []
    counts = Counter()
    for sample in samples:
        stock = sample["stock"]
        rows, dates = prices[stock]
        end = dates[sample["date"]]
        if end < LOOKBACK + 19:
            continue
        if rows[end - LOOKBACK + 1]["日期"] != sample["lookback_start"]:
            raise ValueError(f"Price lookback differs from sample: {stock} {sample['date']}")
        if not math.isclose(float(rows[end]["收盘"]), float(sample["close"]), rel_tol=1e-8):
            raise ValueError(f"Prediction-day close differs from sample: {stock} {sample['date']}")
        sequences.append(market_window(rows, end))
        text, stats = text_vector_and_stats(sample, by_id)
        news.append(np.concatenate((text, extra_text_features(stats))))
        selected_samples.append(sample)
        stats_rows.append({"stock": stock, "date": sample["date"], "split": sample["split"], **stats})
        split = sample["split"]
        counts[(split, "samples")] += 1
        counts[(split, "high_risk")] += int(sample["risk_label"])
        if int(sample["announcement_count"]):
            counts[(split, "days_with_announcements")] += 1
            counts[(split, "high_risk_days_with_announcements")] += int(sample["risk_label"])

    suffix = "_pdf" if args.text_view == "title_body" else "_title_only_pdf"
    path = PROCESSED / f"risk_inputs{suffix}.npz"
    with path.with_suffix(".npz.tmp").open("wb") as stream:
        np.savez_compressed(
            stream,
            price=np.stack(sequences),
            news=np.stack(news),
            label=np.asarray([int(sample["risk_label"]) for sample in selected_samples], dtype=np.int64),
            split=np.asarray([sample["split"] for sample in selected_samples]),
            stock=np.asarray([sample["stock"] for sample in selected_samples]),
            date=np.asarray([sample["date"] for sample in selected_samples]),
        )
    path.with_suffix(".npz.tmp").replace(path)
    stats_path = PROCESSED / f"daily_text_stats{suffix}.csv"
    with stats_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=stats_rows[0].keys())
        writer.writeheader()
        writer.writerows(stats_rows)
    summary = {
        "text_view": args.text_view,
        "feature_set": "pdf",
        "samples": len(selected_samples),
        "price_shape": list(np.stack(sequences).shape),
        "news_shape": list(np.stack(news).shape),
        "market_features": MARKET_FEATURES,
        "news_features": "mean 768D CLS, mean three sentiment probabilities, log1p(count), positive/negative counts, negative ratio, average/minimum sentiment",
        "by_split": {split: {key: counts[(split, key)] for key in
                             ("samples", "high_risk", "days_with_announcements",
                              "high_risk_days_with_announcements")}
                     for split in ("train", "validation", "test")},
        "output": str(path.relative_to(ROOT)),
    }
    summary["daily_text_stats"] = str(stats_path.relative_to(ROOT))
    (PROCESSED / f"risk_inputs{suffix}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
