# 预测接口约定

历史接口展示 **2025 年下半年独立测试集**；最新接口在请求时抓取最新已收盘日的数据并运行模型。前端通过同源 `/api` 转发到后端；如需更改后端地址，可在 Next.js 的 `.env.local` 中设置 `BACKEND_INTERNAL_URL`。除健康检查外，接口需先注册或登录。

| 方法与路径 | 返回内容 |
| --- | --- |
| `GET /api/health` | `{"status":"ok"}` |
| `POST /api/auth/register` | 创建账户并登录 |
| `POST /api/auth/login` | 登录 |
| `GET /api/auth/me` | 读取当前账户 |
| `POST /api/auth/logout` | 撤销当前会话 |
| `GET /api/stocks` | 五只试点股票的 `code`、`name` |
| `GET /api/stocks/{stock}/risk-history?limit=30` | 仅试点股票：最近 `limit` 条历史测试记录，按日期升序 |
| `GET /api/stocks/{stock}/risk-latest-saved` | 读取该股票上次成功完成的最新推理结果；没有记录时返回 404 |
| `POST /api/stocks/{stock}/risk-latest` | 输入六位 A 股代码后，触发最新已收盘日的数据抓取、特征提取和三组模型推理；成功时保存当前账户的结果并追加查询历史 |
| `GET /api/stocks/{stock}/risk-trend` | 读取该股票最近最多 30 个交易日的逐日分数，不触发抓取或推理 |
| `POST /api/stocks/{stock}/risk-refresh` | 手动刷新最新交易日并补算漏掉的交易日；以 NDJSON 逐行返回进度，最后返回最新结果与完整趋势 |
| `GET /api/risk-runs` | 当前账户最近最多 100 条成功查询，按获取顺序从新到旧排列 |

`risk-history` 返回 `stock`、`dataset`、完整测试期的 `period`、该股票记录总数 `total`，以及 `items`。每条记录包含 `date`、`actual_high_risk`，并分别提供 `price`、`text`、`fusion` 三个模型的 `_score` 和 `_alert`。`_alert` 使用训练时在验证集固定的阈值；`actual_high_risk` 是未来三交易日真实结果，只适用于历史回放。`_score` 未校准为实际下跌概率。

`risk-latest` 返回 `as_of`（预测基准交易日）、`fetched_at`（抓取时间）、`price_source`（实际行情来源）、20 日收盘行情窗口、进入模型的公告、仅供展示的近期新闻、`backtest_covered`（是否在五只试点股票之中），以及 `price`、`text`、`fusion` 三组分数、验证集阈值和预警标记。成功后以账户和股票代码为键将完整结果保存在 `backend/data/app.db` 的 `user_latest_predictions` 表，同时向 `user_prediction_runs` 追加一条记录；同一天重复查询也分别保留。旧版无账户记录保留在旧表，不自动分配给新账户。失败不会覆盖上次结果，也不会生成历史记录。`risk-latest-saved` 原样读出上次结果；`risk-runs` 返回当前账户的查询历史，不重新抓取或推理。两个接口都不读取未来三日真实标签，也不修改历史测试表；新闻不参与当前模型推理。行情直接取腾讯前复权数据。

最新推理接受六位 A 股代码，但仍依赖数据源能提供足够行情和公告；无数据或抓取失败返回 503，代码格式错误返回 422。模型只在五只试点股票的独立测试集上做过回测，其他股票的推理分数尚未单独验证。历史回测接口仍只包含这五只；其他股票返回 404。历史回测由 `data/processed/risk_pdf_test_predictions.csv` 导入，不会因用户查询而改变。

`risk-trend` 读取新表 `user_daily_observations`，与 2025 年测试集和逐次查询的 `user_prediction_runs` 分开。每条 `items` 含交易日 `as_of`、`status`（`ready`/`missing`）、行情与综合分数及预警状态；`missing` 的分数为 `null`，前端断开对应线段。首次刷新只计算最近已收盘日，后续刷新补算该股票首次成功刷新日至今、最近 30 个可取到的交易日；已成功的旧日不重复计算，最新日始终重新计算，同日只保留最后一组趋势分数。每个点只使用截至该日收盘可获得的行情与公告，预测目标仍是后续 3 个交易日的 5% 收盘跌幅；不包含未来实测结果。

`risk-latest` 和刷新结果使用 `feature_set: "pdf"`，返回最近 20 日的 `price_history`、`market_indicators`（5 日收益、5/10/20 日波动率、20 日最大回撤、成交量变化）、`announcement_stats`（正负面公告数、负面占比、平均及最低情绪分），并在每条公告的 `sentiment` 中返回三类分数、标签和正减负情绪分。三组 `models` 除原始 `score` 外还返回验证集校准的 `probability`。`probability` 是模型估计值，不保证真实未来跌幅；旧版保存结果不具备上述字段。`risk-trend` 返回 `feature_set`，数据库以股票、交易日和特征版本共同标识一条逐日观察，避免新旧模型分数混合。

`risk-refresh` 返回 `application/x-ndjson`，事件依次为 `loading`、`start`、每个待处理日期一条 `progress`、`complete`；若整轮失败则返回 `error`。`progress` 含 `done`、`total`、`date`、`status`。`complete` 含 `latest` 和 `trend`，页面收到它后才更新最新判断与趋势。历史日期抓取或提取失败时记录为 `missing`，下次手动刷新会重试；若最新日期失败，`latest` 为 `null`，已保存的上次判断不会被覆盖。`risk-latest` 接受 POST 请求，成功时也会把最新交易日写入新趋势。
