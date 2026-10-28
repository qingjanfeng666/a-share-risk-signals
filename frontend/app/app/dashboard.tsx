"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

type Stock = { code: string; name: string };
type ModelName = "fusion" | "price" | "text";
type ModelResult = { score: number; validation_threshold: number; alert: boolean; probability?: number };
type Observation = {
  as_of: string;
  status: "ready" | "missing";
  price_score: number | null;
  fusion_score: number | null;
  price_alert: number | null;
  fusion_alert: number | null;
  error: string | null;
};
type TrendHistory = {
  stock: string;
  feature_set?: string;
  total: number;
  items: Observation[];
};
type RefreshEvent =
  | { type: "loading"; message: string }
  | { type: "start"; total: number }
  | { type: "progress"; done: number; total: number; date: string; status: "ready" | "missing" | "kept" }
  | { type: "complete"; latest: Latest | null; trend: TrendHistory }
  | { type: "error"; message: string };
type Latest = {
  stock: Stock;
  backtest_covered?: boolean;
  as_of: string;
  fetched_at: string;
  price_source: string;
  price_window: { start: string; end: string; last_close: number };
  price_history?: { date: string; close: number }[];
  market_indicators?: { return_5: number; volatility_5: number; volatility_10: number; volatility_20: number; max_drawdown_20: number; volume_change_20: number };
  announcement_stats?: { news_count: number; positive_count: number; negative_count: number; negative_ratio: number; avg_sentiment: number; min_sentiment: number };
  feature_set?: string;
  announcements: { title: string; published_at: string; status: string; url: string; sentiment?: { negative: number; neutral: number; positive: number; score: number; label: string } }[];
  news_fetched: number;
  recent_news: { title: string; published_at: string; source: string; url: string }[];
  models: Record<ModelName, ModelResult>;
};
type SavedRun = Latest & { id: number };
type RunHistory = { total: number; items: SavedRun[] };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const modelNames: Record<ModelName, string> = {
  fusion: "综合判断",
  price: "行情信号",
  text: "公告信号",
};
const modelDescriptions: Record<ModelName, string> = {
  fusion: "结合行情与公司公告",
  price: "观察近 20 个交易日的价格与成交量",
  text: "分析观察日前可获得的公司公告",
};
const modelOrder: ModelName[] = ["fusion", "price", "text"];
const score = (value: number) => value.toFixed(3);
const percentage = (value: number) => `${(value * 100).toFixed(1)}%`;
const sentimentName: Record<string, string> = { negative: "负面", neutral: "中性", positive: "正面" };
const dateLabel = (value: string) => {
  const [year, month, day] = value.slice(0, 10).split("-");
  return `${year} 年 ${Number(month)} 月 ${Number(day)} 日`;
};
const timeLabel = (value: string) => value.slice(0, 16).replace("T", " ");

function SignalArtwork({ state }: { state: "pending" | "calm" | "alert" }) {
  return (
    <div className={`signal-artwork ${state === "alert" ? "is-alert" : ""}`} aria-hidden="true">
      <div className="art-halo" />
      <div className="art-plane art-plane-back"><span /><span /><span /></div>
      <div className="art-plane art-plane-middle"><i /><i /><i /><i /><i /></div>
      <div className="art-plane art-plane-front">
        <svg viewBox="0 0 120 120" fill="none">
          <path d="M60 12 99 29v29c0 27-16 45-39 53C37 103 21 85 21 58V29L60 12Z" stroke="currentColor" strokeWidth="5" />
          {state === "alert" ? <path d="M60 39v29m0 14v2" stroke="currentColor" strokeWidth="7" strokeLinecap="round" />
            : state === "calm" ? <path d="m39 62 14 14 29-32" stroke="currentColor" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
              : <path d="M44 61h32" stroke="currentColor" strokeWidth="7" strokeLinecap="round" />}
        </svg>
      </div>
      <div className="art-floor" />
    </div>
  );
}

function ModelCard({ mode, result, noAnnouncement }: { mode: ModelName; result?: ModelResult; noAnnouncement?: boolean }) {
  const emptyTextInput = mode === "text" && !!result && noAnnouncement;
  return (
    <article className={`model-card ${mode === "fusion" ? "model-card-primary" : ""} ${mode === "fusion" ? !result ? "is-pending" : result.alert ? "is-alert" : "" : ""}`}>
      <div className="model-card-head"><h3>{modelNames[mode]}</h3><span className={`model-state ${!result ? "is-pending" : !emptyTextInput && result.alert ? "is-alert" : ""}`}>{emptyTextInput ? "无公告可分析" : result ? result.alert ? "触发预警" : "未触发预警" : "等待结果"}</span></div>
      <p>{emptyTextInput ? "该日没有可用公告；分数来自空文本输入，不代表公告发出风险信号。" : modelDescriptions[mode]}</p>
      <div className="model-reading"><span>{emptyTextInput ? "空输入分数" : "模型分数"}</span><strong>{result ? score(result.score) : "—"}</strong></div>
      {result?.probability !== undefined && !emptyTextInput && <div className="model-probability">估计风险概率 {percentage(result.probability)}</div>}
      <div className="model-threshold">判断线 {result ? score(result.validation_threshold) : "—"}</div>
    </article>
  );
}

function PriceTrend({ prices }: { prices: { date: string; close: number }[] }) {
  if (prices.length < 2) return null;
  const values = prices.map((item) => item.close);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = high - low || 1;
  const points = values.map((value, index) => `${(index / (values.length - 1)) * 300},${75 - ((value - low) / span) * 60}`).join(" ");
  return <div className="price-trend"><span>最近 20 个交易日收盘价走势</span><svg viewBox="0 0 300 90" role="img" aria-label={`收盘价从 ${values[0].toFixed(2)} 元变化至 ${values[values.length - 1].toFixed(2)} 元`} preserveAspectRatio="none"><polyline points={points} /></svg><small>{prices[0].date} 至 {prices[prices.length - 1].date}</small></div>;
}

function Trend({ items }: { items: Observation[] }) {
  if (!items.length) return <p className="muted-copy">首次成功刷新后，这里会出现第一个分数点。</p>;
  const width = 720;
  const height = 220;
  const left = 32;
  const right = 10;
  const top = 16;
  const bottom = 27;
  const x = (index: number) => items.length === 1 ? (left + width - right) / 2 : left + (index / (items.length - 1)) * (width - left - right);
  const y = (value: number) => top + (1 - value) * (height - top - bottom);
  const path = (key: "fusion_score" | "price_score") => {
    let drawing = false;
    return items.map((item, index) => {
      const value = item[key];
      if (item.status !== "ready" || value === null) {
        drawing = false;
        return "";
      }
      const command = drawing ? "L" : "M";
      drawing = true;
      return `${command}${x(index)},${y(value)}`;
    }).join(" ");
  };

  return (
    <svg className="trend" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="近期交易日综合判断与行情信号的分数走势；缺失日期不连线">
      {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
        <g key={tick}>
          <line x1={left} y1={y(tick)} x2={width - right} y2={y(tick)} className="grid-line" />
          <text x={left - 7} y={y(tick) + 4} textAnchor="end" className="axis-label">{tick.toFixed(2)}</text>
        </g>
      ))}
      <path d={path("price_score")} className="price-line" />
      <path d={path("fusion_score")} className="fusion-line" />
      {items.map((item, index) => item.status === "ready" && item.price_score !== null && item.fusion_score !== null
        ? <g key={item.as_of}><circle cx={x(index)} cy={y(item.price_score)} r="3" className="price-point" /><circle cx={x(index)} cy={y(item.fusion_score)} r="3" className="fusion-point" /></g>
        : null)}
      {items.length === 1 ? <text x={x(0)} y={height - 5} textAnchor="middle" className="axis-label">{items[0].as_of}</text> : <>
        <text x={left} y={height - 5} className="axis-label">{items[0].as_of}</text>
        <text x={width - right} y={height - 5} textAnchor="end" className="axis-label">{items[items.length - 1].as_of}</text>
      </>}
    </svg>
  );
}

async function readRefreshStream(response: Response, onEvent: (event: RefreshEvent) => void) {
  if (!response.body) throw new Error("服务器没有返回刷新进度。");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const completed: Extract<RefreshEvent, { type: "complete" }>[] = [];
  const consume = (line: string) => {
    if (!line.trim()) return;
    const event = JSON.parse(line) as RefreshEvent;
    if (event.type === "error") throw new Error(event.message);
    if (event.type === "complete") completed.push(event);
    onEvent(event);
  };
  while (true) {
    const { value, done } = await reader.read();
    buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) consume(line);
    if (done) break;
  }
  consume(buffer);
  if (!completed.length) throw new Error("刷新中断，未收到最终结果。");
  return completed[0];
}

export default function Dashboard() {
  const [selected, setSelected] = useState("300750");
  const [stockInput, setStockInput] = useState("300750");
  const [inputError, setInputError] = useState("");
  const [history, setHistory] = useState<TrendHistory | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [historyRequest, setHistoryRequest] = useState(0);
  const [live, setLive] = useState<Latest | null>(null);
  const [liveOrigin, setLiveOrigin] = useState<"saved" | "fresh" | null>(null);
  const [savedLoading, setSavedLoading] = useState(true);
  const [liveLoading, setLiveLoading] = useState(false);
  const [refreshProgress, setRefreshProgress] = useState<{ done: number; total: number; date: string } | null>(null);
  const [liveError, setLiveError] = useState("");
  const [runHistoryOpen, setRunHistoryOpen] = useState(false);
  const [runHistory, setRunHistory] = useState<RunHistory | null>(null);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState("");
  const [runsRequest, setRunsRequest] = useState(0);
  const savedRequest = useRef<AbortController | null>(null);
  const liveRequest = useRef<AbortController | null>(null);
  const skipSavedLoad = useRef<string | null>(null);

  useEffect(() => {
    if (skipSavedLoad.current === selected) {
      skipSavedLoad.current = null;
      return;
    }
    const controller = new AbortController();
    savedRequest.current = controller;
    fetch(`${API_BASE}/api/stocks/${selected}/risk-latest-saved`, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (response.status === 404) return null;
        if (!response.ok) throw new Error("无法读取上次保存的结果");
        return response.json();
      })
      .then((result: Latest | null) => {
        if (!controller.signal.aborted && result) {
          setLive(result);
          setLiveOrigin("saved");
        }
      })
      .catch((reason: Error) => {
        if (reason.name !== "AbortError") setLiveError("无法读取上次结果。可以点击按钮重新获取。");
      })
      .finally(() => {
        if (!controller.signal.aborted) setSavedLoading(false);
      });
    return () => controller.abort();
  }, [selected]);

  useEffect(() => {
    if (!runHistoryOpen) return;
    const controller = new AbortController();
    fetch(`${API_BASE}/api/risk-runs`, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("无法读取历史结果");
        return response.json();
      })
      .then((result: RunHistory) => {
        if (!controller.signal.aborted) setRunHistory(result);
      })
      .catch((reason: Error) => {
        if (reason.name !== "AbortError") setRunsError("历史结果读取失败，请检查后端服务。");
      })
      .finally(() => {
        if (!controller.signal.aborted) setRunsLoading(false);
      });
    return () => controller.abort();
  }, [selected, runHistoryOpen, runsRequest]);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/api/stocks/${selected}/risk-trend`, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail ?? `接口返回 ${response.status}`);
        }
        return response.json();
      })
      .then((result: TrendHistory) => {
        setHistory(result);
        setHistoryError("");
      })
      .catch((reason: Error) => {
        if (reason.name !== "AbortError") {
          setHistory(null);
          setHistoryError(reason.message === "Failed to fetch" ? "无法连接后端，请启动 FastAPI 服务。" : reason.message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setHistoryLoading(false);
      });
    return () => controller.abort();
  }, [selected, historyRequest]);

  function submitStock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const code = stockInput.trim();
    if (!/^\d{6}$/.test(code)) {
      setInputError("请输入六位 A 股股票代码，例如 300750。");
      return;
    }
    setInputError("");
    void refreshLive(code, code !== selected);
  }

  async function refreshLive(stock = selected, switchStock = false) {
    savedRequest.current?.abort();
    liveRequest.current?.abort();
    const controller = new AbortController();
    liveRequest.current = controller;
    setSavedLoading(false);
    setLiveError("");
    setLiveLoading(true);
    setRefreshProgress(null);
    try {
      const response = await fetch(`${API_BASE}/api/stocks/${stock}/risk-refresh`, { method: "POST", signal: controller.signal, cache: "no-store" });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail ?? `接口返回 ${response.status}`);
      }
      const outcome = await readRefreshStream(response, (event) => {
        if (controller.signal.aborted) return;
        if (event.type === "start") setRefreshProgress({ done: 0, total: event.total, date: "" });
        if (event.type === "progress") setRefreshProgress({ done: event.done, total: event.total, date: event.date });
      });
      if (!outcome.latest) {
        if (!switchStock) setHistory(outcome.trend);
        throw new Error("最近交易日未能完成推理；失败日期已标记，下次刷新会重试。");
      }
      const result = outcome.latest;
      if (!controller.signal.aborted) {
        if (switchStock) {
          skipSavedLoad.current = stock;
          setSelected(stock);
          setRunHistoryOpen(false);
          setRunHistory(null);
        } else if (runHistoryOpen) {
          setRunsLoading(true);
          setRunsRequest((value) => value + 1);
        }
        setLive(result);
        setLiveOrigin("fresh");
        setHistory(outcome.trend);
        setHistoryLoading(false);
        setHistoryError("");
        setStockInput(stock);
        setInputError("");
      }
    } catch (reason) {
      if (!controller.signal.aborted) {
        const message = reason instanceof Error && reason.message !== "Failed to fetch"
          ? reason.message : "无法连接后端。请检查 FastAPI 服务。";
        if (switchStock) setInputError(message);
        else setLiveError(message);
      }
    } finally {
      if (!controller.signal.aborted) {
        setLiveLoading(false);
        setRefreshProgress(null);
      }
    }
  }

  function reloadHistory() {
    setHistoryRequest((value) => value + 1);
    setHistory(null);
    setHistoryLoading(true);
    setHistoryError("");
  }

  const stockName = live?.stock.name ?? selected;
  const recentNews = live ? [...live.recent_news].sort((a, b) => b.published_at.localeCompare(a.published_at)) : [];
  const rows = history ? [...history.items].reverse() : [];
  const missingDays = history?.items.filter((item) => item.status === "missing").length ?? 0;
  const isAlert = live?.models.fusion.alert ?? false;

  return (
    <div className="site-shell">
      <header className="site-header"><div className="header-inner">
        <div className="brand-mark" aria-hidden="true"><span /><span /><span /></div>
        <div className="brand-copy"><strong>股市风险观察</strong><span>短期风险信号</span></div>
        <span className="header-note">课程研究演示</span>
      </div></header>

      <main className="page-container">
        <section className="stock-workspace" aria-labelledby="workspace-title">
          <div className="workspace-heading">
            <div><p className="eyebrow">风险信号舱</p><h1 id="workspace-title">{stockName}{stockName !== selected && <span>{selected}</span>}</h1></div>
            <p>以最近已收盘日为基准，观察未来 3 个交易日内是否可能出现至少 5% 的收盘跌幅。</p>
          </div>
          <form className="stock-search" onSubmit={submitStock}>
            <label htmlFor="stock-code">输入 A 股股票代码</label>
            <div className="stock-search-controls"><input id="stock-code" name="stock-code" type="text" inputMode="numeric" maxLength={6}
              autoComplete="off" placeholder="例如 300750" value={stockInput} onChange={(event) => { setStockInput(event.target.value); setInputError(""); }}
              aria-invalid={Boolean(inputError)} aria-describedby={inputError ? "stock-search-error" : "stock-search-help"} />
              <button type="submit" disabled={liveLoading}>{liveLoading && stockInput.trim() !== selected ? "正在查询…" : "查询股票"}</button></div>
            <p id="stock-search-help">输入六位代码后查询最新已收盘日；成功结果会自动保存。</p>
            {inputError && <p id="stock-search-error" className="stock-search-error" role="alert">{inputError}</p>}
          </form>
          {liveLoading && stockInput.trim() !== selected && <p className="stock-feedback" role="status">正在分析 {stockInput.trim()}，完成前继续显示 {selected} 的结果。</p>}
        </section>

        <section className="signal-section" aria-labelledby="signal-title">
          <div className="section-heading"><div><h2 id="signal-title">最新风险判断</h2><p>先看综合结论，再看两路参考信号。</p></div>
            <div className="signal-tools"><span className="data-origin">{live ? `${liveOrigin === "saved" ? "上次保存" : "本次更新"} · 截至 ${dateLabel(live.as_of)}` : "等待最新结果"}</span>
              <button type="button" className="run-history-button" aria-expanded={runHistoryOpen} aria-controls="run-history-panel"
                onClick={() => { if (!runHistoryOpen) { setRunsLoading(true); setRunsError(""); } setRunHistoryOpen(!runHistoryOpen); }}>历史结果</button></div></div>

          {runHistoryOpen && <section className="run-history-panel" id="run-history-panel" aria-label="已保存的查询结果">
            <div className="run-history-heading"><h3>已保存的查询结果</h3><p>每次成功获取都会保留一条，同一天重复查询也会分别记录。</p></div>
            {runsLoading && <p className="muted-copy" role="status">正在读取历史结果…</p>}
            {runsError && <p className="inline-feedback is-error" role="alert">{runsError}</p>}
            {!runsLoading && !runsError && runHistory && (runHistory.items.length
              ? <><p className="run-count">共 {runHistory.total} 条，按获取顺序排列</p><div className="run-list">{runHistory.items.map((run) => <details className="run-item" key={run.id}>
                <summary><span><strong>{run.stock.name !== run.stock.code ? `${run.stock.name} · ` : ""}{run.stock.code}</strong><small>基准日 {dateLabel(run.as_of)} · 获取于 {timeLabel(run.fetched_at)}</small></span><span className={run.models.fusion.alert ? "run-alert" : "run-calm"}>{run.models.fusion.alert ? "触发预警" : "未触发预警"}</span></summary>
                <div className="run-detail"><p>综合分数 {score(run.models.fusion.score)} · 行情分数 {score(run.models.price.score)} · 公告分数 {score(run.models.text.score)}</p>
                  <p>最近收盘价 {run.price_window.last_close.toFixed(2)} 元 · 行情来源 {run.price_source}</p>
                  <p>纳入公告 {run.announcements.length} 条。{run.announcements.map((item) => item.title).join("；") || "该日无可用公告。"}</p>
                  {run.recent_news.length > 0 && <p>当时抓取的新闻：{run.recent_news.slice(0, 3).map((item) => item.title).join("；")}</p>}
                </div>
              </details>)}</div></>
              : <p className="muted-copy">还没有保存过查询结果。首次查询成功后会出现在这里。</p>)}
          </section>}

          <div className={`signal-stage ${isAlert ? "is-alert" : ""}`} key={`${selected}-${live?.fetched_at ?? "empty"}`}>
            <div className="signal-copy">
              <p className="signal-kicker">{live ? `截至 ${dateLabel(live.as_of)} 收盘` : "未来 3 个交易日"}</p>
              <div className="signal-status"><span className="status-indicator" aria-hidden="true">{live ? isAlert ? "!" : "✓" : "—"}</span>
                <h3>{savedLoading ? "正在读取上次结果" : live ? isAlert ? "出现短期下跌预警" : "暂未触发下跌预警" : "尚无最新风险观察"}</h3></div>
              {live && <p className="risk-level">风险等级：{isAlert ? "高风险" : "一般风险"}{live.models.fusion.probability !== undefined && ` · 模型估计概率 ${percentage(live.models.fusion.probability)}`}</p>}
              <p className="signal-explanation">{live ? isAlert
                ? "综合模型提示关注未来几个交易日的下跌风险；预警不代表一定会下跌。"
                : "综合模型当前未发出预警；没有预警也不代表股价不会下跌。"
                : savedLoading ? "正在从本地记录读取这只股票的上次判断。" : "获取一次最新结果后，下次打开页面就能直接看到它。"}</p>
              <div className="signal-actions"><button type="button" className="refresh-button" onClick={() => void refreshLive()} disabled={liveLoading}>
                {liveLoading ? "正在抓取并计算…" : live ? "刷新最新结果" : "获取最新结果"}
                <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M16.6 8A6.8 6.8 0 1 0 17 10M16.6 8V3.8M16.6 8h-4.2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </button><span>{live ? `结果抓取于 ${timeLabel(live.fetched_at)}` : "按需抓取最近已收盘行情"}</span></div>
            </div>
            <SignalArtwork state={live ? isAlert ? "alert" : "calm" : "pending"} />
          </div>
          {liveLoading && <div className="refresh-feedback" role="status"><p>{refreshProgress?.total
            ? `正在逐日计算：已处理 ${refreshProgress.done}/${refreshProgress.total} 日${refreshProgress.date ? `，最近处理 ${refreshProgress.date}` : ""}。全部尝试完成后更新页面。`
            : "正在获取行情和公告，准备逐日计算。当前结果会保留到本轮完成。"}</p>
            {refreshProgress && refreshProgress.total > 0 && <progress value={refreshProgress.done} max={refreshProgress.total} />}</div>}
          {liveError && <p className="inline-feedback is-error" role="alert">{liveError}</p>}
          {live && history?.feature_set === "pdf" && live.feature_set !== "pdf" && <p className="inline-feedback">当前显示的是旧版保存结果。请点击“刷新最新结果”，查看包含完整风险指标的新版模型判断。</p>}
          {live && live.backtest_covered === false && <p className="inline-feedback">这只股票不在五只试点股票的独立回测范围内，模型分数尚未针对它验证，请谨慎参考。</p>}

          <div className="models-heading"><h2>三路模型信号</h2><p>模型分数用于预警判断；估计风险概率只在新版模型完成验证集校准后显示。</p></div>
          <div className="models-grid">{modelOrder.map((mode) => <ModelCard key={mode} mode={mode} result={live?.models[mode]} noAnnouncement={live?.announcements.length === 0} />)}</div>
          <details className="method-details"><summary>模型分数和判断线是什么意思？</summary><p>每个模型将自己的分数与验证集确定的判断线比较，达到判断线才触发预警。最终结论取综合判断。{live?.feature_set === "pdf" ? "估计风险概率用验证集校准，但仍是模型估计，不能保证实际涨跌。" : "当前旧版模型分数未经实际风险概率校准。"}</p></details>
        </section>

        <section className="information-section" aria-labelledby="information-title">
          <div className="section-heading"><div><h2 id="information-title">本次观察的信息</h2><p>行情与公告参与判断；市场新闻供你了解背景。</p></div></div>
          <div className="information-grid">
            <article className="information-card" aria-labelledby="price-information-title">
              <div className="information-card-head"><h3 id="price-information-title">行情</h3><span className="information-use">用于本次判断</span></div>
              <div className="information-metric"><p className="information-label">最近收盘价</p><div className="information-value">{live ? live.price_window.last_close.toFixed(2) : "—"}{live && <span>元</span>}</div></div>
              {live?.price_history && <PriceTrend prices={live.price_history} />}
              {live?.feature_set === "pdf" && live.market_indicators && <div className="indicator-summary" aria-label="行情风险指标">
                <span>5 日收益率 <strong>{percentage(live.market_indicators.return_5)}</strong></span>
                <span>5 / 10 / 20 日波动率 <strong>{[live.market_indicators.volatility_5, live.market_indicators.volatility_10, live.market_indicators.volatility_20].map(percentage).join(" / ")}</strong></span>
                <span>20 日最大回撤 <strong>{percentage(live.market_indicators.max_drawdown_20)}</strong></span>
                <span>成交量变化率 <strong>{percentage(live.market_indicators.volume_change_20)}</strong></span>
              </div>}
              <div className="information-card-bottom">
                <span className="information-range-label">观察区间 · 过去 20 个交易日</span>
                <strong className="information-range">{live ? <><span>{dateLabel(live.price_window.start)}</span><span aria-hidden="true">→</span><span>{dateLabel(live.price_window.end)}</span></> : "获取结果后显示观察区间"}</strong>
                <small>{live?.feature_set === "pdf" ? "收盘对数收益率、波动率、回撤及成交量变化等进入行情模型。" : "这段时间的价格与成交量进入行情模型；刷新新版模型后会显示完整风险指标。"}</small>
              </div>
            </article>

            <article className="information-card" aria-labelledby="announcement-information-title">
              <div className="information-card-head"><h3 id="announcement-information-title">公司公告</h3><span className="information-use">用于本次判断</span></div>
              <div className="information-metric"><p className="information-label">纳入本次分析</p><div className="information-value">{live ? live.announcements.length : "—"}{live && <span>条</span>}</div></div>
              {live?.announcement_stats && <div className="sentiment-summary"><span>正面 {live.announcement_stats.positive_count}</span><span>负面 {live.announcement_stats.negative_count}</span><span>平均情绪分 {score(live.announcement_stats.avg_sentiment)}</span></div>}
              {live ? live.announcements.length ? <>
                <ul className="information-list">{live.announcements.slice(0, 2).map((item) => <li key={item.url}><a href={item.url} target="_blank" rel="noreferrer">{item.title}</a><small>{timeLabel(item.published_at)}{item.sentiment && ` · ${sentimentName[item.sentiment.label] ?? item.sentiment.label} · 情绪分 ${score(item.sentiment.score)}`}</small></li>)}</ul>
                {live.announcements.length > 2 && <details className="information-more"><summary>查看其余 {live.announcements.length - 2} 条公告</summary><ul className="information-list">{live.announcements.slice(2).map((item) => <li key={item.url}><a href={item.url} target="_blank" rel="noreferrer">{item.title}</a><small>{timeLabel(item.published_at)}{item.sentiment && ` · ${sentimentName[item.sentiment.label] ?? item.sentiment.label} · 情绪分 ${score(item.sentiment.score)}`}</small></li>)}</ul></details>}
              </> : <div className="information-empty"><strong>本次未纳入公告</strong><p>该观察日没有可用公告，文本输入为空。</p></div>
                : <p className="information-placeholder">获取结果后显示进入模型的公告。</p>}
            </article>

            <article className="information-card" aria-labelledby="news-information-title">
              <div className="information-card-head"><h3 id="news-information-title">近期市场信息</h3><span className="information-use information-use-reference">仅供阅读</span></div>
              <div className="information-metric"><p className="information-label">最近抓取</p><div className="information-value">{live ? recentNews.length : "—"}{live && <span>条</span>}</div></div>
              {live ? recentNews.length ? <>
                <ul className="information-list">{recentNews.slice(0, 2).map((item) => <li key={item.url}><a href={item.url} target="_blank" rel="noreferrer">{item.title}</a><small>{item.source} · {timeLabel(item.published_at)}</small></li>)}</ul>
                {recentNews.length > 2 && <details className="information-more"><summary>查看其余 {recentNews.length - 2} 条信息</summary><ul className="information-list">{recentNews.slice(2).map((item) => <li key={item.url}><a href={item.url} target="_blank" rel="noreferrer">{item.title}</a><small>{item.source} · {timeLabel(item.published_at)}</small></li>)}</ul></details>}
              </> : <p className="information-placeholder">暂无可展示的市场信息。</p>
                : <p className="information-placeholder">获取结果后显示近期市场信息。</p>}
              <p className="information-disclaimer">新闻未进入当前风险模型，发布时间可能晚于观察基准日。</p>
            </article>
          </div>
        </section>

        <section className="history-section" aria-labelledby="trend-title">
          <div className="trend-section-head"><span><small>从首次成功刷新起 · 按交易日积累</small><strong id="trend-title">近 30 个交易日的风险信号</strong><em>每一天都以当日收盘为基准，判断随后 3 个交易日的短期风险。</em></span><span className="history-count">{history ? `${history.total}/30 日` : "逐日积累"}</span></div>
          <div className="history-content">
            <button type="button" className="text-button" onClick={reloadHistory}>重新读取趋势记录</button>
            {historyError && <p className="inline-feedback is-error" role="alert">{historyError}</p>}
            {historyLoading && <p className="muted-copy" role="status">正在读取趋势记录…</p>}
            {!historyLoading && history && !history.items.length && <p className="muted-copy">首次成功刷新后，这里会出现第一个分数点。之后每次刷新会补算漏掉的交易日。</p>}
            {!historyLoading && history && history.items.length > 0 && <>
              <p className="trend-summary">已记录 {history.total} 个交易日{missingDays > 0 ? `；其中 ${missingDays} 日数据缺失，下次刷新会重试` : ""}。没有未来日期的分数。</p>
              <div className="chart-heading"><div><h3>逐日模型分数</h3><p>纵轴是模型分数，不是实际下跌概率；缺失日期的线段会断开。</p></div><div className="legend"><span className="fusion-key">综合判断</span><span className="price-key">行情信号</span></div></div>
              <Trend items={history.items} />
              <details className="history-table-details"><summary>查看最近 {history.items.length} 日的逐日记录</summary><div className="table-scroll"><table><thead><tr><th>交易日</th><th>行情分数</th><th>综合分数</th><th>综合判断</th></tr></thead><tbody>
                {rows.map((item) => <tr key={item.as_of}><td>{item.as_of}</td><td>{item.price_score === null ? "—" : score(item.price_score)}</td><td>{item.fusion_score === null ? "—" : score(item.fusion_score)}</td><td>{item.status === "missing" ? "数据缺失，待重试" : item.fusion_alert ? "触发预警" : "未触发预警"}</td></tr>)}
              </tbody></table></div></details>
            </>}
          </div>
        </section>
      </main>
      <footer className="site-footer"><span>股市风险观察 · 课程研究演示</span><p>模型结果用于课程实验，不构成投资建议。没有预警也不代表没有风险。</p></footer>
    </div>
  );
}
