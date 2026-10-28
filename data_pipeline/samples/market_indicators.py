"""Risk indicators available at each trading-day close."""

import math
import statistics

import numpy as np

from .build_daily_samples import LOOKBACK
from .build_risk_inputs import price_window


MARKET_FEATURES = (
    "close_log_return", "open_log_ratio", "high_log_ratio", "low_log_ratio",
    "volume_log_ratio", "volatility_5", "volatility_10", "volatility_20",
    "max_drawdown_20", "volume_change_20",
)


def indicators_at(rows, index):
    """Use only rows through index; 20 returns need 21 closing prices."""
    if index < 20:
        raise ValueError("20-day indicators need 21 closed trading days")
    closes = [float(row["收盘"]) for row in rows[index - 20:index + 1]]
    volumes = [float(row["成交量"]) for row in rows[index - 20:index + 1]]
    if min(closes + volumes) <= 0:
        raise ValueError("Risk indicators need positive close and volume")
    returns = [math.log(closes[offset] / closes[offset - 1]) for offset in range(1, 21)]
    volatilities = [statistics.stdev(returns[-days:]) for days in (5, 10, 20)]
    peak = closes[1]
    drawdown = 0.0
    for close in closes[1:]:
        peak = max(peak, close)
        drawdown = max(drawdown, (peak - close) / peak)
    typical_volume = statistics.mean(volumes[:-1])
    volume_change = (volumes[-1] - typical_volume) / typical_volume
    return np.asarray([*volatilities, drawdown, volume_change], dtype=np.float32)


def market_window(rows, end):
    """Twenty daily OHLCV rows plus indicators computed separately at each day."""
    if end < LOOKBACK + 19:
        raise ValueError("A 20-day market window with 20-day volatility needs 40 price days")
    base = price_window(rows, end)
    indicators = np.stack([
        indicators_at(rows, index)
        for index in range(end - LOOKBACK + 1, end + 1)
    ])
    return np.concatenate((base, indicators), axis=1)
