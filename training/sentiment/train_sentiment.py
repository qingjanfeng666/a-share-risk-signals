"""Fine-tune Chinese MacBERT for three-class financial sentiment."""

import argparse
import csv
import json
import random
from pathlib import Path

import torch
from torch.utils.data import DataLoader, TensorDataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed"
OUTPUT = ROOT / "models" / "sentiment_macbert"
LABELS = ("negative", "neutral", "positive")
LABEL_TO_ID = {label: index for index, label in enumerate(LABELS)}
SEED = 42


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"No sentiment samples in {path}")
    if any(row["label"] not in LABEL_TO_ID or not row["sentence"].strip() for row in rows):
        raise ValueError(f"Unexpected label or empty sentence in {path}")
    return rows


def make_loader(rows, tokenizer, batch_size, shuffle, max_length):
    encoded = tokenizer(
        [row["sentence"] for row in rows],
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors="pt",
    )
    labels = torch.tensor([LABEL_TO_ID[row["label"]] for row in rows], dtype=torch.long)
    dataset = TensorDataset(encoded["input_ids"], encoded["attention_mask"], labels)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)


def move_batch(batch, device):
    input_ids, attention_mask, labels = (item.to(device) for item in batch)
    return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


def train_one_epoch(model, loader, optimizer, scaler, device, epoch):
    model.train()
    total_loss = 0.0
    seen = 0
    for step, batch in enumerate(loader, start=1):
        inputs = move_batch(batch, device)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast("cuda", enabled=device.type == "cuda"):
            loss = model(**inputs).loss
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        batch_size = inputs["labels"].size(0)
        total_loss += loss.item() * batch_size
        seen += batch_size
        if step % 100 == 0 or step == len(loader):
            print(f"epoch {epoch} step {step}/{len(loader)} train_loss={total_loss / seen:.4f}", flush=True)
    return total_loss / len(loader.dataset)


def score(true_labels, predictions):
    by_label = {}
    for label_id, name in enumerate(LABELS):
        true_positive = sum(y == label_id and p == label_id for y, p in zip(true_labels, predictions))
        false_positive = sum(y != label_id and p == label_id for y, p in zip(true_labels, predictions))
        false_negative = sum(y == label_id and p != label_id for y, p in zip(true_labels, predictions))
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        by_label[name] = {"precision": precision, "recall": recall, "f1": f1}
    return {
        "accuracy": sum(y == p for y, p in zip(true_labels, predictions)) / len(true_labels),
        "macro_f1": sum(item["f1"] for item in by_label.values()) / len(LABELS),
        "by_label": by_label,
    }


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    total_loss = 0.0
    true_labels, predictions = [], []
    for batch in loader:
        inputs = move_batch(batch, device)
        with torch.autocast("cuda", enabled=device.type == "cuda"):
            output = model(**inputs)
        total_loss += output.loss.item() * inputs["labels"].size(0)
        true_labels.extend(inputs["labels"].cpu().tolist())
        predictions.extend(output.logits.argmax(dim=1).cpu().tolist())
    return {"loss": total_loss / len(loader.dataset), **score(true_labels, predictions)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="hfl/chinese-macbert-base", help="Hub model ID or local model directory")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    args = parser.parse_args()
    if min(args.epochs, args.batch_size, args.max_length) < 1:
        parser.error("epochs, batch-size and max-length must be positive")
    if args.device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA is unavailable in this WSL environment; check the PyTorch installation")
    device = torch.device(args.device)
    random.seed(SEED)
    torch.manual_seed(SEED)

    train_rows = read_rows(DATA / "sentiment_train.csv")
    validation_rows = read_rows(DATA / "sentiment_validation.csv")
    if {row["sentence"] for row in train_rows} & {row["sentence"] for row in validation_rows}:
        raise ValueError("A sentence appears in both training and validation data")
    print(f"device={device}, train={len(train_rows)}, validation={len(validation_rows)}, model={args.model}", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    train_loader = make_loader(train_rows, tokenizer, args.batch_size, True, args.max_length)
    validation_loader = make_loader(validation_rows, tokenizer, args.batch_size, False, args.max_length)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model,
        num_labels=len(LABELS),
        id2label={index: label for index, label in enumerate(LABELS)},
        label2id=LABEL_TO_ID,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    history = []
    best_f1 = -1.0
    for epoch in range(1, args.epochs + 1):
        train_loss = train_one_epoch(model, train_loader, optimizer, scaler, device, epoch)
        validation = evaluate(model, validation_loader, device)
        record = {"epoch": epoch, "train_loss": train_loss, "validation": validation}
        history.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        if validation["macro_f1"] > best_f1:
            best_f1 = validation["macro_f1"]
            model.save_pretrained(OUTPUT)
            tokenizer.save_pretrained(OUTPUT)
            best_epoch = epoch
        (OUTPUT / "training_metrics.json").write_text(
            json.dumps(
                {"pretrained_model": args.model, "labels": LABELS, "seed": SEED,
                 "max_length": args.max_length, "batch_size": args.batch_size,
                 "best_epoch": best_epoch, "best_macro_f1": best_f1, "history": history},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
    print(f"Best epoch={best_epoch}, macro_f1={best_f1:.4f}, saved_to={OUTPUT.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
