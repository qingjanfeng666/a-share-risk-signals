"""Evaluate the three frozen risk checkpoints on the held-out test split."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from .train_risk import (INPUT, MODEL_CLASSES, MODEL_DIR, MODES, ROOT,
                         average_precision, predict, roc_auc, threshold_metrics)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    parser.add_argument("--output-stem", default="risk_pdf_test")
    args = parser.parse_args()
    args.input = args.input.resolve()
    args.model_dir = args.model_dir.resolve()
    if args.batch_size < 1:
        parser.error("batch-size must be positive")
    if args.device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA is unavailable; use --device cpu or check the WSL GPU setup")
    device = torch.device(args.device)

    with np.load(args.input, allow_pickle=False) as saved:
        test = saved["split"].astype(str) == "test"
        price = saved["price"][test].astype(np.float32)
        news = saved["news"][test].astype(np.float32)
        labels = saved["label"][test].astype(np.int64)
        stocks = saved["stock"][test].astype(str)
        dates = saved["date"][test].astype(str)
    if not len(labels) or len(price) != len(news) or not 0 < labels.sum() < len(labels):
        raise ValueError("Test inputs are empty, misaligned, or missing a risk class")

    predictions = {}
    probabilities = {}
    results = {}
    for mode in MODES:
        checkpoint = torch.load(args.model_dir / f"{mode}.pt", map_location="cpu", weights_only=True)
        if checkpoint["mode"] != mode:
            raise ValueError(f"Wrong checkpoint mode: {mode}")
        mean = checkpoint["price_mean"].numpy()
        std = checkpoint["price_std"].numpy()
        if (mean.shape != (price.shape[2],) or std.shape != (price.shape[2],)
                or checkpoint.get("price_dim") != price.shape[2]
                or checkpoint.get("text_dim") != news.shape[1] or np.any(std <= 0)):
            raise ValueError(f"Invalid price normalizer: {mode}")
        normalized_price = (price - mean) / std
        loader = DataLoader(
            TensorDataset(torch.from_numpy(normalized_price), torch.from_numpy(news),
                          torch.from_numpy(labels.astype(np.float32))),
            batch_size=args.batch_size,
        )
        model = MODEL_CLASSES[mode](price.shape[2], news.shape[1]).to(device)
        model.load_state_dict(checkpoint["state_dict"])
        scores = predict(model, loader, device)
        if not np.isfinite(scores).all():
            raise ValueError(f"Non-finite model scores: {mode}")
        threshold = float(checkpoint["threshold"])
        predictions[mode] = scores
        calibration = checkpoint.get("calibration")
        if calibration:
            logits = np.log(np.clip(scores, 1e-6, 1 - 1e-6) / (1 - np.clip(scores, 1e-6, 1 - 1e-6)))
            probability = 1 / (1 + np.exp(-(calibration["slope"] * logits + calibration["intercept"])))
            probabilities[mode] = probability
        results[mode] = {
            "average_precision": average_precision(labels, scores),
            "roc_auc": roc_auc(labels, scores),
            "validation_threshold": threshold,
            "at_validation_threshold": threshold_metrics(labels, scores, threshold),
            "at_0.5": threshold_metrics(labels, scores, 0.5),
        }
        if calibration:
            results[mode]["brier_score"] = float(np.mean((probability - labels) ** 2))

    processed = ROOT / "data" / "processed"
    csv_path = processed / f"{args.output_stem}_predictions.csv"
    fields = ["stock", "date", "label"] + [
        f"{mode}_{kind}" for mode in MODES for kind in ("score", "alert", "probability")
    ]
    with csv_path.with_suffix(".csv.tmp").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for index in range(len(labels)):
            row = {"stock": stocks[index], "date": dates[index], "label": int(labels[index])}
            for mode in MODES:
                score = float(predictions[mode][index])
                row[f"{mode}_score"] = score
                row[f"{mode}_alert"] = int(score >= results[mode]["validation_threshold"])
                row[f"{mode}_probability"] = float(probabilities[mode][index]) if mode in probabilities else ""
            writer.writerow(row)
    csv_path.with_suffix(".csv.tmp").replace(csv_path)

    summary = {"test_samples": len(labels), "test_high_risk": int(labels.sum()),
               "base_rate": float(labels.mean()), "models": results,
               "predictions": str(csv_path.relative_to(ROOT))}
    (processed / f"{args.output_stem}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
