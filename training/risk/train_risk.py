"""Train price, announcement, and fused risk models without using test labels."""

import argparse
import copy
import json
import random
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data" / "processed" / "risk_inputs_pdf.npz"
MODEL_DIR = ROOT / "models" / "risk_pdf"
SEED = 42
MODES = ("price", "text", "fusion")


class PriceRiskModel(nn.Module):
    """Encode the 20-day price sequence with an LSTM."""

    def __init__(self, price_dim=10, text_dim=777):
        super().__init__()
        self.price_encoder = nn.LSTM(input_size=price_dim, hidden_size=32, batch_first=True)
        self.classifier = nn.Sequential(
            nn.Linear(32, 32), nn.ReLU(), nn.Dropout(0.2), nn.Linear(32, 1)
        )

    def forward(self, price, news):
        _, (hidden, _) = self.price_encoder(price)
        return self.classifier(hidden[-1]).squeeze(1)


class TextRiskModel(nn.Module):
    """Classify the prediction day's announcement features."""

    def __init__(self, price_dim=10, text_dim=777):
        super().__init__()
        self.text_encoder = nn.Sequential(nn.Linear(text_dim, 32), nn.ReLU(), nn.Dropout(0.2))
        self.classifier = nn.Sequential(
            nn.Linear(32, 32), nn.ReLU(), nn.Dropout(0.2), nn.Linear(32, 1)
        )

    def forward(self, price, news):
        return self.classifier(self.text_encoder(news)).squeeze(1)


class FusionRiskModel(nn.Module):
    """Concatenate price and announcement representations before classification."""

    def __init__(self, price_dim=10, text_dim=777):
        super().__init__()
        self.price_encoder = nn.LSTM(input_size=price_dim, hidden_size=32, batch_first=True)
        self.text_encoder = nn.Sequential(nn.Linear(text_dim, 32), nn.ReLU(), nn.Dropout(0.2))
        self.classifier = nn.Sequential(
            nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.2), nn.Linear(32, 1)
        )

    def forward(self, price, news):
        _, (hidden, _) = self.price_encoder(price)
        features = torch.cat((hidden[-1], self.text_encoder(news)), dim=1)
        return self.classifier(features).squeeze(1)


MODEL_CLASSES = {"price": PriceRiskModel, "text": TextRiskModel, "fusion": FusionRiskModel}


def load_data(input_path=INPUT):
    with np.load(input_path, allow_pickle=False) as saved:
        price = saved["price"].astype(np.float32)
        news = saved["news"].astype(np.float32)
        label = saved["label"].astype(np.float32)
        split = saved["split"].astype(str)
    if price.ndim != 3 or price.shape[1:] != (20, 10) or news.shape[1] != 777 or news.shape[0] != len(price):
        raise ValueError("Unexpected risk input shape")
    if len(label) != len(price) or len(split) != len(price):
        raise ValueError("Risk input arrays have different lengths")
    if not np.isfinite(price).all() or not np.isfinite(news).all():
        raise ValueError("Risk inputs contain non-finite values")
    if not set(np.unique(label)).issubset({0.0, 1.0}):
        raise ValueError("Risk labels must be binary")
    if set(np.unique(split)) != {"train", "validation", "test"}:
        raise ValueError("Unexpected time split")
    train = split == "train"
    mean = price[train].mean(axis=(0, 1))
    std = np.maximum(price[train].std(axis=(0, 1)), 1e-6)
    price = (price - mean) / std
    return price, news, label, split, mean, std


def average_precision(labels, scores):
    positives = int(labels.sum())
    if not positives:
        return None
    order = np.argsort(-scores, kind="stable")
    sorted_scores = scores[order]
    cumulative_positives = np.cumsum(labels[order])
    # Evaluate tied scores as one threshold, particularly the many no-news days.
    ends = np.r_[np.flatnonzero(np.diff(sorted_scores) != 0), len(labels) - 1]
    positives_at_threshold = cumulative_positives[ends]
    new_positives = np.diff(np.r_[0, positives_at_threshold])
    precision = positives_at_threshold / (ends + 1)
    return float(np.sum(precision * new_positives) / positives)


def roc_auc(labels, scores):
    positive = scores[labels == 1]
    negative = scores[labels == 0]
    if not len(positive) or not len(negative):
        return None
    return float(((positive[:, None] > negative).sum() +
                  0.5 * (positive[:, None] == negative).sum()) /
                 (len(positive) * len(negative)))


def threshold_metrics(labels, scores, threshold):
    predicted = scores >= threshold
    tp = int(np.sum((labels == 1) & predicted))
    fp = int(np.sum((labels == 0) & predicted))
    fn = int(np.sum((labels == 1) & ~predicted))
    tn = int(np.sum((labels == 0) & ~predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"accuracy": (tp + tn) / len(labels), "precision": precision, "recall": recall, "f1": f1,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def validation_report(labels, scores):
    return {"average_precision": average_precision(labels, scores),
            "roc_auc": roc_auc(labels, scores),
            "at_0.5": threshold_metrics(labels, scores, 0.5)}


def fit_calibration(labels, scores):
    """Fit a monotone sigmoid mapping on validation scores only."""
    if not 0 < labels.sum() < len(labels):
        raise ValueError("Calibration needs both risk classes")
    logits = torch.logit(torch.as_tensor(scores, dtype=torch.float32).clamp(1e-6, 1 - 1e-6))
    targets = torch.as_tensor(labels, dtype=torch.float32)
    raw_slope = torch.nn.Parameter(torch.tensor(0.0))
    intercept = torch.nn.Parameter(torch.logit(targets.mean()))
    optimizer = torch.optim.Adam([raw_slope, intercept], lr=0.05)
    for _ in range(400):
        optimizer.zero_grad()
        slope = torch.nn.functional.softplus(raw_slope)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(slope * logits + intercept, targets)
        loss = loss + 0.01 * (slope - 1).square()
        loss.backward()
        optimizer.step()
    with torch.no_grad():
        slope = float(torch.nn.functional.softplus(raw_slope))
        bias = float(intercept)
        calibrated = torch.sigmoid(slope * logits + intercept).numpy()
    return {"slope": slope, "intercept": bias,
            "validation_brier": float(np.mean((calibrated - labels) ** 2))}


@torch.no_grad()
def predict(model, loader, device):
    model.eval()
    probabilities = []
    for price, news, _ in loader:
        logits = model(price.to(device), news.to(device))
        probabilities.extend(torch.sigmoid(logits).cpu().numpy())
    return np.asarray(probabilities, dtype=np.float64)


def train_mode(mode, data, args, device):
    price, news, label, split, mean, std = data
    train = split == "train"
    validation = split == "validation"
    positives = int(label[train].sum())
    negatives = int(train.sum()) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("Training split needs both risk classes")
    train_set = TensorDataset(torch.from_numpy(price[train]), torch.from_numpy(news[train]),
                              torch.from_numpy(label[train]))
    validation_set = TensorDataset(torch.from_numpy(price[validation]),
                                   torch.from_numpy(news[validation]),
                                   torch.from_numpy(label[validation]))
    generator = torch.Generator().manual_seed(SEED)
    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True,
                              generator=generator)
    validation_loader = DataLoader(validation_set, batch_size=args.batch_size)

    model = MODEL_CLASSES[mode](price.shape[2], news.shape[1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    pos_weight = negatives / positives
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight, device=device))
    true_validation = label[validation].astype(np.int64)
    best_ap = -1.0
    best_state = None
    best_epoch = 0
    stale_epochs = 0
    history = []
    print(f"mode={mode}, train={len(train_set)}, validation={len(validation_set)}, "
          f"train_positive={positives}, pos_weight={pos_weight:.4f}, device={device}", flush=True)
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        for price_batch, news_batch, label_batch in train_loader:
            price_batch = price_batch.to(device)
            news_batch = news_batch.to(device)
            label_batch = label_batch.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(price_batch, news_batch), label_batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item() * len(label_batch)
        scores = predict(model, validation_loader, device)
        report = validation_report(true_validation, scores)
        record = {"mode": mode, "epoch": epoch, "train_loss": total_loss / len(train_set),
                  "validation": report}
        history.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        if report["average_precision"] > best_ap:
            best_ap = report["average_precision"]
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= args.patience:
                break

    model.load_state_dict(best_state)
    scores = predict(model, validation_loader, device)
    # The threshold is selected only on validation; the test split is untouched here.
    thresholds = np.unique(scores)
    chosen = max(thresholds, key=lambda value: (threshold_metrics(true_validation, scores, value)["f1"],
                                                float(value)))
    threshold = float(chosen)
    report = {**validation_report(true_validation, scores),
              "base_rate": float(true_validation.mean()), "selected_threshold": threshold,
              "at_selected_threshold": threshold_metrics(true_validation, scores, threshold)}
    calibration = fit_calibration(true_validation, scores)
    report["calibration"] = calibration
    args.output_dir.mkdir(parents=True, exist_ok=True)
    torch.save({"mode": mode, "state_dict": model.state_dict(),
                "price_mean": torch.from_numpy(mean), "price_std": torch.from_numpy(std),
                "price_dim": price.shape[2], "text_dim": news.shape[1],
                "threshold": threshold, "calibration": calibration}, args.output_dir / f"{mode}.pt")
    metrics = {"mode": mode, "seed": SEED, "input": str(args.input.relative_to(ROOT)),
               "train_positive": positives, "train_negative": negatives,
               "pos_weight": pos_weight, "best_epoch": best_epoch,
               "validation": report, "history": history}
    (args.output_dir / f"{mode}_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"mode": mode, "best_epoch": best_epoch, "validation": report,
                      "checkpoint": str((args.output_dir / f'{mode}.pt').relative_to(ROOT))},
                     ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=(*MODES, "all"), default="all")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output-dir", type=Path, default=MODEL_DIR)
    args = parser.parse_args()
    args.input = args.input.resolve()
    args.output_dir = args.output_dir.resolve()
    if min(args.epochs, args.patience, args.batch_size) < 1 or args.learning_rate <= 0:
        parser.error("epochs, patience, batch-size and learning-rate must be positive")
    if args.device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA is unavailable; use --device cpu or check the WSL GPU setup")
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    if args.device == "cuda":
        torch.cuda.manual_seed_all(SEED)
    data = load_data(args.input)
    print(f"input={args.input.relative_to(ROOT)}, modes={MODES if args.mode == 'all' else (args.mode,)}",
          flush=True)
    for mode in MODES if args.mode == "all" else (args.mode,):
        train_mode(mode, data, args, torch.device(args.device))


if __name__ == "__main__":
    main()
