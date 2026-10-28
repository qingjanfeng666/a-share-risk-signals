"""Fill current-era daily scores without borrowing data from later trading days."""

import re

from backend.services.live_inference import ObservationPredictor, latest_result
from backend.services.live_sources import fetch_live_sources
from backend.services.daily_plan import dates_to_score
from backend.storage.daily_observations import (
    first_observation_date, read_observations, read_trend, save_observation,
)
from backend.storage.latest_predictions import save_latest_prediction


def refresh_observations(stock):
    if not re.fullmatch(r"[0-9]{6}", stock):
        raise ValueError("请输入六位 A 股股票代码。")
    yield {"type": "loading", "message": "正在获取最近已收盘的行情、公告和市场信息"}
    predictor = ObservationPredictor()
    first_date = first_observation_date(stock, predictor.feature_set)
    snapshot = fetch_live_sources(stock, include_history=first_date is not None)
    existing = {row["as_of"]: row["status"] for row in read_observations(stock, feature_set=predictor.feature_set)}
    targets = dates_to_score(snapshot["prices"], first_date, existing)
    yield {"type": "start", "total": len(targets)}
    latest = None
    for done, (index, day) in enumerate(targets, 1):
        try:
            predictions, announcements, stats = predictor.predict_day(stock, snapshot, index)
        except Exception as error:
            if first_date is not None and existing.get(day) != "ready":
                save_observation(stock, day, error=f"{type(error).__name__}: {error}", feature_set=predictor.feature_set)
            status = "missing" if existing.get(day) != "ready" else "kept"
        else:
            save_observation(stock, day, predictions, feature_set=predictor.feature_set)
            if day == snapshot["as_of"]:
                latest = latest_result(stock, snapshot, predictions, announcements, stats, predictor.feature_set)
                save_latest_prediction(latest)
            status = "ready"
        yield {"type": "progress", "done": done, "total": len(targets), "date": day, "status": status}
    yield {"type": "complete", "latest": latest, "trend": read_trend(stock, predictor.feature_set)}
