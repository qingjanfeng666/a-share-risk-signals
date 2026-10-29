"""API for historical results and on-demand latest inference."""

import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from requests.exceptions import RequestException

from backend.api.auth import require_trusted_origin, require_user
from backend.services.history import risk_history, stock_list
from backend.storage.user_results import read_trend, save_observation
from backend.storage.user_results import (
    read_latest_prediction, read_prediction_runs, save_latest_prediction,
)


router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def check_stock_code(stock):
    if not re.fullmatch(r"[0-9]{6}", stock):
        raise HTTPException(status_code=422, detail="请输入六位 A 股股票代码。")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/stocks")
def stocks(user=Depends(require_user)):
    return {"stocks": stock_list()}


@router.get("/stocks/{stock}/risk-history")
def stock_risk_history(stock: str, limit: int = Query(default=30, ge=1, le=123), user=Depends(require_user)):
    try:
        return risk_history(stock, limit)
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail="缺少数据库，请先导入历史预测结果。") from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/stocks/{stock}/risk-latest", dependencies=[Depends(require_trusted_origin)])
def stock_risk_latest(stock: str, user=Depends(require_user)):
    check_stock_code(stock)
    from backend.services.live_inference import predict_latest

    try:
        result = predict_latest(stock)
        save_latest_prediction(user["id"], result)
        save_observation(user["id"], stock, result["as_of"], result["models"], feature_set=result.get("feature_set", "pdf"))
        return result
    except (FileNotFoundError, RequestException, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=f"最新数据推理失败：{error}") from error


@router.get("/stocks/{stock}/risk-latest-saved")
def stock_risk_latest_saved(stock: str, user=Depends(require_user)):
    check_stock_code(stock)
    result = read_latest_prediction(user["id"], stock)
    if result is None:
        raise HTTPException(status_code=404, detail="这只股票还没有保存的最新观察。")
    return result


@router.get("/stocks/{stock}/risk-trend")
def stock_risk_trend(stock: str, user=Depends(require_user)):
    check_stock_code(stock)
    return read_trend(user["id"], stock)


@router.post("/stocks/{stock}/risk-refresh", dependencies=[Depends(require_trusted_origin)])
def stock_risk_refresh(stock: str, user=Depends(require_user)):
    check_stock_code(stock)
    from backend.services.daily_refresh import refresh_observations

    def stream():
        try:
            for event in refresh_observations(stock, user["id"]):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception:
            logger.exception("Risk refresh failed for stock %s", stock)
            yield json.dumps({"type": "error", "message": "刷新失败，请稍后重试。"}, ensure_ascii=False) + "\n"

    return StreamingResponse(
        stream(), media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/risk-runs")
def risk_runs(user=Depends(require_user)):
    return read_prediction_runs(user["id"])
