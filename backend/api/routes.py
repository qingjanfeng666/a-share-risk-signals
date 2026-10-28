"""API for historical results and on-demand latest inference."""

import json
import re

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from requests.exceptions import RequestException

from backend.services.history import risk_history, stock_list
from backend.storage.daily_observations import read_trend, save_observation
from backend.storage.latest_predictions import (
    read_latest_prediction, read_prediction_runs, save_latest_prediction,
)


router = APIRouter(prefix="/api")


def check_stock_code(stock):
    if not re.fullmatch(r"[0-9]{6}", stock):
        raise HTTPException(status_code=422, detail="请输入六位 A 股股票代码。")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/stocks")
def stocks():
    return {"stocks": stock_list()}


@router.get("/stocks/{stock}/risk-history")
def stock_risk_history(stock: str, limit: int = Query(default=30, ge=1, le=123)):
    try:
        return risk_history(stock, limit)
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail="缺少数据库，请先导入历史预测结果。") from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/stocks/{stock}/risk-latest")
def stock_risk_latest(stock: str):
    check_stock_code(stock)
    from backend.services.live_inference import predict_latest

    try:
        result = predict_latest(stock)
        save_latest_prediction(result)
        save_observation(stock, result["as_of"], result["models"], feature_set=result.get("feature_set", "pdf"))
        return result
    except (FileNotFoundError, RequestException, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=f"最新数据推理失败：{error}") from error


@router.get("/stocks/{stock}/risk-latest-saved")
def stock_risk_latest_saved(stock: str):
    check_stock_code(stock)
    result = read_latest_prediction(stock)
    if result is None:
        raise HTTPException(status_code=404, detail="这只股票还没有保存的最新观察。")
    return result


@router.get("/stocks/{stock}/risk-trend")
def stock_risk_trend(stock: str):
    check_stock_code(stock)
    return read_trend(stock)


@router.post("/stocks/{stock}/risk-refresh")
def stock_risk_refresh(stock: str):
    check_stock_code(stock)
    from backend.services.daily_refresh import refresh_observations

    def stream():
        try:
            for event in refresh_observations(stock):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as error:
            yield json.dumps({"type": "error", "message": f"刷新失败：{error}"}, ensure_ascii=False) + "\n"

    return StreamingResponse(
        stream(), media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/risk-runs")
def risk_runs():
    return read_prediction_runs()
