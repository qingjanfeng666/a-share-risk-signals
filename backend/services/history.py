"""Prepare a stock's historical risk results for the API."""

from backend.storage.predictions import read_predictions


STOCKS = {
    "300750": "宁德时代",
    "002594": "比亚迪",
    "300059": "东方财富",
    "600519": "贵州茅台",
    "000001": "平安银行",
}


def stock_list():
    return [{"code": code, "name": name} for code, name in STOCKS.items()]


def risk_history(stock, limit):
    if stock not in STOCKS:
        raise ValueError("该股票未纳入 2025 年下半年的独立测试集，暂无历史回测记录。")
    rows = read_predictions(stock)
    if not rows:
        raise ValueError(f"No historical predictions for {stock}")
    items = []
    for row in rows[-limit:]:
        items.append({
            "date": row["date"],
            "actual_high_risk": bool(int(row["label"])),
            "price_score": float(row["price_score"]),
            "price_alert": bool(int(row["price_alert"])),
            "text_score": float(row["text_score"]),
            "text_alert": bool(int(row["text_alert"])),
            "fusion_score": float(row["fusion_score"]),
            "fusion_alert": bool(int(row["fusion_alert"])),
        })
    return {
        "stock": {"code": stock, "name": STOCKS[stock]},
        "dataset": "2025年下半年独立测试集",
        "period": {"start": rows[0]["date"], "end": rows[-1]["date"]},
        "total": len(rows),
        "items": items,
    }
