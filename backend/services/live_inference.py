"""Run the frozen sentiment and risk checkpoints on freshly fetched data."""

import argparse
import json
import math
import re
from urllib.parse import parse_qs, urlparse

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from backend.services.history import STOCKS
from backend.services.live_sources import fetch_live_sources
from data_pipeline.samples.market_indicators import indicators_at, market_window
from data_pipeline.samples.text_stats import aggregate_sentiment, extra_text_features
from data_pipeline.text.build_sentiment_features import LABELS, MODEL_DIR as SENTIMENT_DIR, model_input
from data_pipeline.text.extract_announcement_texts import extract_one
from training.risk.train_risk import MODEL_CLASSES, MODEL_DIR as RISK_DIR, MODES


def announcement_vector(stock, rows, device, encoder=None):
    if not rows:
        return np.zeros(772, dtype=np.float32), [], aggregate_sentiment([])

    documents = []
    for row in rows:
        link = str(row["公告链接"])
        ids = parse_qs(urlparse(link).query).get("announcementId")
        if not ids:
            raise ValueError(f"Announcement ID missing: {link}")
        document = extract_one(ids[0], stock, row)
        if document["status"] == "error":
            raise RuntimeError(f"公告正文获取失败: {ids[0]}: {document['error']}")
        documents.append(document)

    if encoder is None:
        tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_DIR)
        model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_DIR).to(device)
        model.eval()
    else:
        tokenizer, model = encoder
    if model.config.label2id != {label: index for index, label in enumerate(LABELS)}:
        raise ValueError(f"Unexpected sentiment labels: {model.config.label2id}")

    vectors = []
    scores = []
    with torch.inference_mode():
        for document in documents:
            inputs = tokenizer(
                model_input(document, body_chars=512, text_view="title_body"),
                truncation=True,
                max_length=128,
                return_tensors="pt",
            )
            output = model(**{name: value.to(device) for name, value in inputs.items()},
                           output_hidden_states=True)
            scores.append(torch.softmax(output.logits, dim=-1)[0].cpu().numpy())
            vectors.append(output.hidden_states[-1][0, 0].float().cpu().numpy())

    features = np.concatenate((
        np.mean(vectors, axis=0),
        np.mean(scores, axis=0),
        [math.log1p(len(documents))],
    )).astype(np.float32)
    stats = aggregate_sentiment(scores)
    summary = [{
        "title": document["title"],
        "published_at": document["published_at"],
        "status": document["status"],
        "url": document["detail_url"],
        "sentiment": {
            "negative": float(probabilities[0]),
            "neutral": float(probabilities[1]),
            "positive": float(probabilities[2]),
            "score": float(probabilities[2] - probabilities[0]),
            "label": LABELS[int(np.argmax(probabilities))],
        },
    } for document, probabilities in zip(documents, scores)]
    return features, summary, stats


class ObservationPredictor:
    """Keep model weights loaded while scoring several closed trading days."""

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.sentiment_encoder = None
        self.risk_models = {}
        self.feature_set = "pdf"
        for mode in MODES:
            checkpoint = torch.load(RISK_DIR / f"{mode}.pt", map_location="cpu", weights_only=True)
            if checkpoint["mode"] != mode:
                raise ValueError(f"Wrong risk checkpoint: {mode}")
            mean = checkpoint["price_mean"].numpy()
            std = checkpoint["price_std"].numpy()
            if (mean.shape != (10,) or std.shape != (10,)
                    or checkpoint.get("price_dim") != 10
                    or checkpoint.get("text_dim") != 777 or np.any(std <= 0)):
                raise ValueError(f"Invalid price normalizer: {mode}")
            model = MODEL_CLASSES[mode](10, 777).to(self.device)
            model.load_state_dict(checkpoint["state_dict"])
            model.eval()
            self.risk_models[mode] = (model, mean, std, float(checkpoint["threshold"]), checkpoint.get("calibration"))

    def predict_day(self, stock, snapshot, index):
        day = str(snapshot["prices"][index]["日期"])[:10]
        rows_by_day = snapshot.get("announcements_by_day", {snapshot["as_of"]: snapshot["announcements"]})
        rows = rows_by_day.get(day, [])
        if rows and self.sentiment_encoder is None:
            tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_DIR)
            model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_DIR).to(self.device)
            model.eval()
            self.sentiment_encoder = (tokenizer, model)
        price = market_window(snapshot["prices"], index)
        text_features, announcements, stats = announcement_vector(
            stock, rows, self.device, self.sentiment_encoder,
        )
        text_features = np.concatenate((text_features, extra_text_features(stats)))
        predictions = {}
        with torch.inference_mode():
            for mode, (model, mean, std, threshold, calibration) in self.risk_models.items():
                normalized = ((price - mean) / std).astype(np.float32)
                logit = model(
                    torch.from_numpy(normalized[None]).to(self.device),
                    torch.from_numpy(text_features[None]).to(self.device),
                )
                score = float(torch.sigmoid(logit).item())
                if not math.isfinite(score):
                    raise ValueError(f"Non-finite {mode} score")
                predictions[mode] = {
                    "score": score,
                    "validation_threshold": threshold,
                    "alert": score >= threshold,
                }
                if calibration:
                    predictions[mode]["probability"] = 1 / (1 + math.exp(-(
                        calibration["slope"] * math.log(max(1e-6, score) / max(1e-6, 1 - score))
                        + calibration["intercept"]
                    )))
        return predictions, announcements, stats


def latest_result(stock, snapshot, predictions, announcements, stats, feature_set="pdf"):
    current_indicators = indicators_at(snapshot["prices"], len(snapshot["prices"]) - 1)
    recent_closes = snapshot["prices"][-20:]
    return {
        "stock": {"code": stock, "name": snapshot.get("stock_name") if snapshot.get("stock_name") not in (None, stock) else STOCKS.get(stock, stock)},
        "backtest_covered": stock in STOCKS,
        "as_of": snapshot["as_of"],
        "fetched_at": snapshot["fetched_at"],
        "price_source": snapshot["price_source"],
        "price_window": {
            "start": str(snapshot["prices"][-20]["日期"]),
            "end": snapshot["as_of"],
            "last_close": float(snapshot["prices"][-1]["收盘"]),
        },
        "price_history": [{"date": str(row["日期"])[:10], "close": float(row["收盘"])}
                          for row in recent_closes],
        "market_indicators": {
            "return_5": float(snapshot["prices"][-1]["收盘"]) / float(snapshot["prices"][-6]["收盘"]) - 1,
            "volatility_5": float(current_indicators[0]),
            "volatility_10": float(current_indicators[1]),
            "volatility_20": float(current_indicators[2]),
            "max_drawdown_20": float(current_indicators[3]),
            "volume_change_20": float(current_indicators[4]),
        },
        "announcements": announcements,
        "announcement_stats": stats,
        "feature_set": feature_set,
        "model_input_shape": {"price": [20, 10], "announcement": [777]},
        "news_fetched": len(snapshot["news"]),
        "recent_news": [{
            "title": str(row["新闻标题"]),
            "published_at": str(row["发布时间"]),
            "source": str(row["文章来源"]),
            "url": str(row["新闻链接"]),
        } for row in snapshot["news"]],
        "news_note": "新闻仅供展示；当前风险模型的文本输入来自公司公告。",
        "models": predictions,
        "score_note": "模型分数用于验证阈值判断；概率经验证集校准，仅是模型估计，不保证实际跌幅。",
    }


def predict_latest(stock):
    if not re.fullmatch(r"[0-9]{6}", stock):
        raise ValueError("请输入六位 A 股股票代码。")
    snapshot = fetch_live_sources(stock)
    predictor = ObservationPredictor()
    predictions, announcements, stats = predictor.predict_day(
        stock, snapshot, len(snapshot["prices"]) - 1,
    )
    return latest_result(stock, snapshot, predictions, announcements, stats, predictor.feature_set)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", default="300750", help="Six-digit A-share stock code")
    args = parser.parse_args()
    print(json.dumps(predict_latest(args.stock), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
