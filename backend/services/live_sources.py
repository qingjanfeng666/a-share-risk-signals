"""Fetch the latest closed A-share price day and its available text sources."""

from datetime import datetime, time, timedelta
from time import sleep
from zoneinfo import ZoneInfo

from requests.exceptions import RequestException

from data_pipeline.samples.build_daily_samples import assigned_day


SHANGHAI = ZoneInfo("Asia/Shanghai")
PRICE_COLUMNS = {"日期", "开盘", "收盘", "最高", "最低", "成交量"}
TENCENT_COLUMNS = {"date", "open", "close", "high", "low", "volume"}
ANNOUNCEMENT_COLUMNS = {"公告标题", "公告时间", "公告链接"}
NEWS_COLUMNS = {"新闻标题", "新闻内容", "发布时间", "文章来源", "新闻链接"}


def fetch_with_retry(source, function, **kwargs):
    for attempt in range(1, 4):
        try:
            return function(**kwargs)
        except RequestException as error:
            if attempt == 3:
                raise RuntimeError(f"{source}连续 3 次连接失败") from error
            wait = (2, 5)[attempt - 1]
            print(f"{source}请求失败（{attempt}/3）：{type(error).__name__}，{wait} 秒后重试", flush=True)
            sleep(wait)


def fetch_prices(ak, stock, start, end):
    frame = fetch_with_retry(
        "腾讯行情", ak.stock_zh_a_hist_tx,
        symbol=stock, start_date=start, end_date=end,
        adjust="qfq", timeout=15,
    )
    if frame.empty or not TENCENT_COLUMNS.issubset(frame.columns):
        raise ValueError(f"腾讯行情为空或字段不完整: {frame.columns.tolist()}")
    frame = frame.rename(columns={
        "date": "日期", "open": "开盘", "close": "收盘",
        "high": "最高", "low": "最低", "volume": "成交量",
    })
    return frame, "Tencent qfq via AKShare"


def fetch_live_sources(stock, now=None, include_history=False):
    import akshare as ak

    now = now or datetime.now(SHANGHAI)
    latest_closed = now.date() if now.time() >= time(15, 30) else now.date() - timedelta(days=1)
    prices_frame, price_source = fetch_prices(
        ak, stock,
        (latest_closed - timedelta(days=120)).strftime("%Y%m%d"),
        latest_closed.strftime("%Y%m%d"),
    )
    if not PRICE_COLUMNS.issubset(prices_frame.columns):
        raise ValueError(f"Unexpected price columns: {prices_frame.columns.tolist()}")
    prices = sorted(
        (row for row in prices_frame.to_dict("records") if str(row["日期"])[:10] <= latest_closed.isoformat()),
        key=lambda row: str(row["日期"]),
    )
    if len(prices) < 21:
        raise ValueError(f"Need at least 21 closed price days; got {len(prices)}")
    trading_days = [datetime.fromisoformat(str(row["日期"])).date() for row in prices]
    if len(trading_days) != len(set(trading_days)):
        raise ValueError("Duplicate price date")
    as_of = trading_days[-1]

    announcement_start = (trading_days[max(0, len(trading_days) - 30)] if include_history else as_of) - timedelta(days=30)
    announcements_frame = fetch_with_retry(
        "公告", ak.stock_zh_a_disclosure_report_cninfo,
        symbol=stock,
        market="沪深京",
        start_date=announcement_start.strftime("%Y%m%d"),
        end_date=as_of.strftime("%Y%m%d"),
    )
    if not announcements_frame.empty and not ANNOUNCEMENT_COLUMNS.issubset(announcements_frame.columns):
        raise ValueError(f"Unexpected announcement columns: {announcements_frame.columns.tolist()}")
    stock_name = stock
    if not announcements_frame.empty and "简称" in announcements_frame.columns:
        names = announcements_frame["简称"].dropna().astype(str).str.strip()
        names = names[names.ne("")]
        if not names.empty:
            stock_name = names.iloc[0]
    announcements = announcements_frame.to_dict("records") if not announcements_frame.empty else []
    announcements_by_day = {}
    seen_links = set()
    for row in announcements:
        row["公告时间"] = str(row["公告时间"])
        row["公告标题"] = str(row["公告标题"])
        row["公告链接"] = str(row["公告链接"])
        published = datetime.fromisoformat(str(row["公告时间"]))
        link = str(row["公告链接"])
        target = assigned_day(published, trading_days)
        if link not in seen_links and target is not None:
            announcements_by_day.setdefault(target.isoformat(), []).append(row)
            seen_links.add(link)

    news_frame = fetch_with_retry("新闻", ak.stock_news_em, symbol=stock)
    if not news_frame.empty and not NEWS_COLUMNS.issubset(news_frame.columns):
        raise ValueError(f"Unexpected news columns: {news_frame.columns.tolist()}")
    if stock_name == stock and not news_frame.empty and "关键词" in news_frame.columns:
        names = news_frame["关键词"].dropna().astype(str).str.strip()
        names = names[names.ne("") & names.ne(stock)]
        if not names.empty:
            stock_name = names.iloc[0]
    news = news_frame.to_dict("records") if not news_frame.empty else []

    return {
        "stock_name": stock_name,
        "as_of": as_of.isoformat(),
        "fetched_at": now.isoformat(timespec="seconds"),
        "price_source": price_source,
        "prices": prices,
        "announcements_fetched": len(announcements),
        "announcements": announcements_by_day.get(as_of.isoformat(), []),
        "announcements_by_day": announcements_by_day,
        "news": news,
    }
