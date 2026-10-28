"""Prepare deduplicated Chinese financial sentiment train/validation CSVs."""

import csv
import hashlib
import json
import random
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "raw" / "all_languages_clean.csv"
OUTPUT_DIR = ROOT / "data" / "processed"
LABELS = ("negative", "neutral", "positive")
VALIDATION_RATIO = 0.2
SEED = 42


def normalize(sentence):
    """Use one stable key for identical sentences with spacing/width differences."""
    return " ".join(unicodedata.normalize("NFKC", sentence).split())


def read_chinese_rows():
    rows = []
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"sentence", "label", "source", "language"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"CSV must contain {sorted(required)}")
        for row in reader:
            if row["language"].strip().lower() != "zh":
                continue
            label = row["label"].strip().lower()
            if label not in LABELS:
                raise ValueError(f"Unexpected Chinese sentiment label: {label!r}")
            sentence = normalize(row["sentence"])
            if sentence:
                rows.append({"sentence": sentence, "label": label, "source": row["source"].strip()})
    return rows


def deduplicate(rows):
    by_sentence = defaultdict(list)
    for row in rows:
        by_sentence[row["sentence"]].append(row)
    clean = []
    duplicate_rows = 0
    conflicting_sentences = 0
    conflicting_rows = 0
    for copies in by_sentence.values():
        if len({row["label"] for row in copies}) != 1:
            conflicting_sentences += 1
            conflicting_rows += len(copies)
            continue
        duplicate_rows += len(copies) - 1
        clean.append(copies[0])
    return clean, duplicate_rows, conflicting_sentences, conflicting_rows


def split_by_label(rows):
    rng = random.Random(SEED)
    groups = {label: [] for label in LABELS}
    for row in rows:
        groups[row["label"]].append(row)
    train, validation = [], []
    for label in LABELS:
        group = sorted(groups[label], key=lambda row: row["sentence"])
        if len(group) < 2:
            raise ValueError(f"Not enough {label} examples for both splits")
        rng.shuffle(group)
        validation_count = round(len(group) * VALIDATION_RATIO)
        validation.extend(group[:validation_count])
        train.extend(group[validation_count:])
    rng.shuffle(train)
    rng.shuffle(validation)
    if {row["sentence"] for row in train} & {row["sentence"] for row in validation}:
        raise ValueError("The same sentence appears in both splits")
    return train, validation


def save_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("sentence", "label", "source"))
        writer.writeheader()
        writer.writerows(rows)


def describe(rows):
    return {"rows": len(rows), "labels": dict(Counter(row["label"] for row in rows))}


def main():
    source_rows = read_chinese_rows()
    clean_rows, duplicate_rows, conflicting_sentences, conflicting_rows = deduplicate(source_rows)
    train, validation = split_by_label(clean_rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_csv(OUTPUT_DIR / "sentiment_train.csv", train)
    save_csv(OUTPUT_DIR / "sentiment_validation.csv", validation)
    with SOURCE.open("rb") as stream:
        source_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    summary = {
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": source_sha256,
        "language": "zh",
        "seed": SEED,
        "validation_ratio": VALIDATION_RATIO,
        "chinese_rows": len(source_rows),
        "duplicate_rows_removed": duplicate_rows,
        "conflicting_sentences_removed": conflicting_sentences,
        "conflicting_rows_removed": conflicting_rows,
        "train": describe(train),
        "validation": describe(validation),
    }
    summary_path = OUTPUT_DIR / "sentiment_split_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved to {OUTPUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
