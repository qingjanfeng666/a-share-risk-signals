"""Join saved announcement text results to daily risk samples by split."""

import argparse
import csv
import json
from collections import Counter
from datetime import date, datetime

from .build_daily_samples import PROCESSED, RAW, ROOT, assigned_day, read_csv


SAMPLES = PROCESSED / "daily_samples_2023_2025.csv"
TEXT_DIR = PROCESSED / "announcement_texts"


def trading_days_for(stock):
    return sorted(date.fromisoformat(row["日期"]) for row in read_csv(RAW / f"{stock}_prices_probe.csv"))


def build_row(sample, results, trading_days):
    ids = sample["announcement_ids"].split("|") if sample["announcement_ids"] else []
    if len(ids) != int(sample["announcement_count"]):
        raise ValueError(f"Announcement count differs from IDs: {sample['stock']} {sample['date']}")
    usable = []
    nonusable = []
    characters = 0
    for announcement_id in ids:
        result = results[announcement_id]
        if result["stock"] != sample["stock"]:
            raise ValueError(f"Stock mismatch for announcement {announcement_id}")
        target = assigned_day(datetime.fromisoformat(result["published_at"]), trading_days)
        if target != date.fromisoformat(sample["date"]):
            raise ValueError(f"Announcement {announcement_id} belongs to {target}, not {sample['date']}")
        if result["status"] == "usable_chinese":
            usable.append(announcement_id)
            characters += result["extracted_characters"]
        else:
            nonusable.append(announcement_id)
    return {
        "stock": sample["stock"],
        "date": sample["date"],
        "announcement_count": len(ids),
        "usable_text_count": len(usable),
        "nonusable_text_count": len(nonusable),
        "has_usable_text": int(bool(usable)),
        "usable_text_characters": characters,
        "usable_announcement_ids": "|".join(usable),
        "nonusable_announcement_ids": "|".join(nonusable),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("train", "validation", "test"), default="train")
    args = parser.parse_args()
    output = PROCESSED / f"daily_text_index_{args.split}.csv"
    summary_path = PROCESSED / f"daily_text_index_{args.split}_summary.json"
    samples = [row for row in read_csv(SAMPLES) if row["split"] == args.split]
    referenced = {item for row in samples for item in row["announcement_ids"].split("|") if item}
    results = {}
    for announcement_id in referenced:
        path = TEXT_DIR / f"{announcement_id}.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        if result["announcement_id"] != announcement_id:
            raise ValueError(f"Wrong announcement ID in {path}")
        results[announcement_id] = result
    trading_days = {stock: trading_days_for(stock) for stock in {row["stock"] for row in samples}}
    rows = [build_row(row, results, trading_days[row["stock"]]) for row in samples]
    used_ids = []
    for row in rows:
        for field in ("usable_announcement_ids", "nonusable_announcement_ids"):
            used_ids.extend(item for item in row[field].split("|") if item)
    if len(used_ids) != len(set(used_ids)) or set(used_ids) != referenced:
        raise ValueError("Announcement IDs are duplicated or missing from the daily index")

    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "samples": len(rows),
        "announcement_days": sum(row["announcement_count"] > 0 for row in rows),
        "days_with_usable_text": sum(row["has_usable_text"] for row in rows),
        "days_with_only_nonusable_text": sum(
            row["announcement_count"] > 0 and not row["has_usable_text"] for row in rows
        ),
        "status_counts": dict(Counter(result["status"] for result in results.values())),
        "announcement_ids": len(referenced),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"csv": str(output.relative_to(ROOT)), "summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
