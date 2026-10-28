# 本地 FastAPI 服务

当前接口提供 2025 年下半年测试集的**历史实验回放**，读取 `backend/data/app.db`；另提供手动触发的**最新已收盘日推理**。成功的最新结果按股票保存到同一数据库，下次打开页面可直接读取。PDF 完整特征版实验结果保留在 `data/processed/risk_pdf_test_predictions.csv`。历史接口不重新训练或推理，最新接口只运行已有模型权重。

## 最新收盘日推理试跑

可从 `pbl/` 根目录单独运行完整推理链：

```bash
backend/.fastapienv/bin/python -u -m backend.services.live_inference --stock 300750
```

此命令请求最新已收盘日的行情、公告和新闻，提取归属于该日的公告正文，沿用训练时的 MacBERT 与三组风险模型输出分数。行情直接取腾讯前复权数据，并在 `price_source` 中标明来源。新闻随结果展示，但不进入当前仅用公告训练的文本特征。`model_input_shape` 应为价格 `[20, 10]`、公告 `[777]`；估计风险概率经验证集校准。结果打印到终端。网页上的“刷新最新结果”会额外把本次分数存入逐日趋势，并补算此前漏掉的交易日。

后端只加载 `models/risk_pdf/` 的三份权重，使用 PDF 完整特征版：行情输入 `[20,10]`、公告输入 `[777]`。返回 20 日收盘价、波动率、最大回撤、成交量变化、公告逐条情绪和日级统计；同时显示验证集校准的模型估计风险概率。缺少新版权重时推理会明确报错。已保存的旧查询记录仍可在数据库历史中读取，但不参与新版逐日趋势。

## 历史回放接口

首次启动前，在项目根目录 `pbl/` 用已有的测试结果建立本地数据库：

```bash
backend/.fastapienv/bin/python -m backend.storage.import_predictions
```

命令会打印导入条数；重新运行会用当前 CSV 重新写入历史预测表。

从项目根目录 `pbl/` 在 WSL 启动：

```bash
backend/.fastapienv/bin/python -m backend.run
```

监听地址、端口及允许访问的前端地址统一放在 `backend/.env.local`。修改后重启后端服务；前端的 API 地址也要与后端端口一致。`.env.local` 是本机配置，不提交 Git。

```dotenv
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
FRONTEND_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

服务运行时在另一个 WSL 终端检查：

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/stocks
curl 'http://127.0.0.1:8000/api/stocks/300750/risk-history?limit=3'
curl 'http://127.0.0.1:8000/api/stocks/300750/risk-latest'
curl 'http://127.0.0.1:8000/api/stocks/300750/risk-latest-saved'
curl 'http://127.0.0.1:8000/api/stocks/300750/risk-trend'
curl -N -X POST 'http://127.0.0.1:8000/api/stocks/300750/risk-refresh'
curl 'http://127.0.0.1:8000/api/risk-runs'
```

接口格式与字段说明见 [`docs/api-contract.md`](../docs/api-contract.md)。`backend/api/` 接收和校验 HTTP 请求，`backend/services/` 抓取数据并完成推理，`backend/storage/` 读写 SQLite。网页输入六位 A 股代码查询，成功后更新 `latest_predictions` 并向 `live_prediction_runs` 追加一条完整记录；逐日趋势另存于 `daily_observations`。旧版本已保存的最新结果会在第一次新查询成功时迁入查询历史。历史回测仍只覆盖原来的五只试点股票，其他代码虽可做最新推理，但模型效果尚未经过独立回测验证。缺少原始预测 CSV 时先运行 `training/risk/evaluate_risk.py`；缺少历史数据库时运行上面的导入命令。
