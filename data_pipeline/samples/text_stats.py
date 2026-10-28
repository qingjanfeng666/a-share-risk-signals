"""Daily sentiment statistics from negative/neutral/positive probabilities."""

import math

import numpy as np


EXTRA_TEXT_FEATURES = (
    "log_positive_count", "log_negative_count", "negative_ratio",
    "avg_sentiment", "min_sentiment",
)


def aggregate_sentiment(probabilities):
    scores = np.asarray(probabilities, dtype=np.float32)
    if scores.size == 0:
        scores = scores.reshape(0, 3)
    if scores.ndim != 2 or scores.shape[1] != 3 or not np.isfinite(scores).all():
        raise ValueError("Expected finite negative/neutral/positive scores")
    labels = scores.argmax(axis=1) if len(scores) else []
    positive = int(np.sum(labels == 2))
    negative = int(np.sum(labels == 0))
    sentiment = scores[:, 2] - scores[:, 0]
    return {
        "news_count": len(scores),
        "positive_count": positive,
        "negative_count": negative,
        "negative_ratio": negative / len(scores) if len(scores) else 0.0,
        "avg_sentiment": float(sentiment.mean()) if len(scores) else 0.0,
        "min_sentiment": float(sentiment.min()) if len(scores) else 0.0,
    }


def extra_text_features(stats):
    return np.asarray([
        math.log1p(stats["positive_count"]),
        math.log1p(stats["negative_count"]),
        stats["negative_ratio"], stats["avg_sentiment"], stats["min_sentiment"],
    ], dtype=np.float32)
