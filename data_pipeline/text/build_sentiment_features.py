"""Run the frozen sentiment model once per referenced announcement."""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
MODEL_DIR = ROOT / "models" / "sentiment_macbert"
SPLITS = ("train", "validation", "test")
LABELS = ("negative", "neutral", "positive")


def load_announcements():
    entries = []
    seen = set()
    for split in SPLITS:
        path = PROCESSED / f"announcement_text_manifest_{split}.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for item in manifest["results"]:
            announcement_id = item["announcement_id"]
            if announcement_id in seen:
                raise ValueError(f"Duplicate announcement ID: {announcement_id}")
            seen.add(announcement_id)
            text_path = PROCESSED / "announcement_texts" / f"{announcement_id}.json"
            document = json.loads(text_path.read_text(encoding="utf-8"))
            if any(document[key] != item[key] for key in ("announcement_id", "stock", "status")):
                raise ValueError(f"Manifest and text disagree: {announcement_id}")
            entries.append((split, document))
    return entries


def model_input(document, body_chars, text_view):
    title = document["title"].strip()
    body = (
        document["text"].strip()[:body_chars]
        if text_view == "title_body" and document["status"] == "usable_chinese"
        else ""
    )
    result = f"{title}\n{body}" if body else title
    if not result:
        raise ValueError(f"Empty title and body: {document['announcement_id']}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--body-chars", type=int, default=512)
    parser.add_argument("--text-view", choices=("title_body", "title_only"), default="title_body")
    args = parser.parse_args()
    if min(args.batch_size, args.max_length, args.body_chars) < 1:
        parser.error("batch-size, max-length and body-chars must be positive")
    if args.device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA is unavailable; use --device cpu or check the WSL GPU setup")

    entries = load_announcements()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR).to(args.device)
    model.eval()
    if model.config.label2id != {label: index for index, label in enumerate(LABELS)}:
        raise ValueError(f"Unexpected model labels: {model.config.label2id}")

    rows = []
    embeddings = []
    with torch.inference_mode():
        for start in range(0, len(entries), args.batch_size):
            batch = entries[start : start + args.batch_size]
            inputs = tokenizer(
                [model_input(document, args.body_chars, args.text_view) for _, document in batch],
                padding=True,
                truncation=True,
                max_length=args.max_length,
                return_tensors="pt",
            )
            inputs = {name: value.to(args.device) for name, value in inputs.items()}
            output = model(**inputs, output_hidden_states=True)
            scores = torch.softmax(output.logits, dim=-1).cpu().numpy()
            vectors = output.hidden_states[-1][:, 0, :].float().cpu().numpy()
            for (split, document), score, vector in zip(batch, scores, vectors):
                rows.append({
                    "announcement_id": document["announcement_id"],
                    "stock": document["stock"],
                    "published_at": document["published_at"],
                    "split": split,
                    "has_usable_body": int(document["status"] == "usable_chinese"),
                    **{f"sentiment_{label}": float(score[index]) for index, label in enumerate(LABELS)},
                })
                embeddings.append(vector.astype(np.float16))
            if len(rows) % 100 < len(batch) or len(rows) == len(entries):
                print(f"processed={len(rows)}/{len(entries)}", flush=True)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.text_view == "title_body" else "_title_only"
    csv_path = PROCESSED / f"announcement_sentiment_features{suffix}.csv"
    csv_temp = csv_path.with_suffix(".csv.tmp")
    with csv_temp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    csv_temp.replace(csv_path)

    embedding_path = PROCESSED / f"announcement_embeddings{suffix}.npz"
    embedding_temp = embedding_path.with_suffix(".npz.tmp")
    with embedding_temp.open("wb") as stream:
        np.savez_compressed(
            stream,
            announcement_ids=np.array([row["announcement_id"] for row in rows]),
            embeddings=np.stack(embeddings),
        )
    embedding_temp.replace(embedding_path)

    summary = {
        "announcements": len(rows),
        "by_split": dict(Counter(row["split"] for row in rows)),
        "with_usable_body": sum(row["has_usable_body"] for row in rows),
        "embedding_shape": [len(rows), len(embeddings[0])],
        "predicted_labels": dict(Counter(
            max(LABELS, key=lambda label: row[f"sentiment_{label}"]) for row in rows
        )),
        "input": {"text_view": args.text_view, "body_characters": args.body_chars if suffix == "" else 0,
                  "max_tokens": args.max_length},
        "model": str(MODEL_DIR.relative_to(ROOT)),
        "csv": str(csv_path.relative_to(ROOT)),
        "embeddings": str(embedding_path.relative_to(ROOT)),
    }
    summary_path = PROCESSED / f"announcement_sentiment_features{suffix}_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
