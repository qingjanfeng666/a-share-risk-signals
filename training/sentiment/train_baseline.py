"""TF-IDF + linear SVM baseline on the same Chinese sentiment split as MacBERT."""

import csv
import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed"
LABELS = ("negative", "neutral", "positive")


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    train = read_rows(DATA / "sentiment_train.csv")
    validation = read_rows(DATA / "sentiment_validation.csv")
    if {row["sentence"] for row in train} & {row["sentence"] for row in validation}:
        raise ValueError("Sentiment train and validation sentences overlap")
    model = make_pipeline(
        TfidfVectorizer(analyzer="char", ngram_range=(2, 4), min_df=2, sublinear_tf=True),
        LinearSVC(class_weight="balanced", random_state=42),
    )
    model.fit([row["sentence"] for row in train], [row["label"] for row in train])
    true = [row["label"] for row in validation]
    predicted = model.predict([row["sentence"] for row in validation])
    precision, recall, f1, support = precision_recall_fscore_support(
        true, predicted, labels=LABELS, zero_division=0,
    )
    result = {
        "model": "character TF-IDF (2-4 grams) + balanced LinearSVC",
        "train": len(train), "validation": len(validation),
        "accuracy": float(accuracy_score(true, predicted)),
        "macro_precision": float(precision.mean()),
        "macro_recall": float(recall.mean()),
        "macro_f1": float(f1.mean()),
        "by_label": {name: {"precision": float(precision[index]), "recall": float(recall[index]),
                            "f1": float(f1[index]), "support": int(support[index])}
                     for index, name in enumerate(LABELS)},
    }
    output = ROOT / "models" / "sentiment_baseline_metrics.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
