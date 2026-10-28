# 作业 PDF 逐项验收表

依据教师提供的《基于 BERT 与深度学习的金融新闻情绪分析及股票风险预警系统设计与实现》（26 页）逐项检查。训练与独立测试已于 2026-10-20 在用户的 WSL GPU 环境完成；服务联调另行记录。

| PDF 要求 | 当前证据 | 状态 |
| --- | --- | --- |
| 任务 1：文本清洗、去重、代码与交易日对齐、Tokenizer 截断 | `data_pipeline/text/prepare_sentiment_data.py`、`data_pipeline/samples/build_daily_samples.py`、`data_pipeline/text/build_sentiment_features.py`；公告收盘后归次日 | 已实现 |
| 任务 2：BERT 类情绪三分类 | `models/sentiment_macbert/training_metrics.json`；验证 macro-F1 0.8071 | 已训练 |
| 任务 3：逐条情绪概率、正减负情绪分、768 维 CLS | `announcement_sentiment_features.csv`、`announcement_embeddings.npz`；实时接口也返回逐公告情绪 | 已实现 |
| 任务 4：日级 NewsCount、PositiveCount、NegativeCount、NegativeRatio、AvgSentiment、MinSentiment、NewsEmbedding | `data_pipeline/samples/text_stats.py`、`data/processed/daily_text_stats_pdf.csv`、`risk_inputs_pdf.npz`；文本源为 PDF 允许的公司公告 | 已训练和测试 |
| 任务 5：日期、开高低收、成交量、成交额与收益率、5/10/20 日波动率、最大回撤、成交量变化 | 原始 `data/raw/*_prices_probe.csv` 含成交额；`market_indicators.py` 计算滚动指标，`risk_inputs_pdf.npz` 为 20×10 行情输入 | 已训练和测试 |
| 任务 6：LSTM/GRU/Transformer 至少一个市场时序模型 | `training/risk/train_risk.py` 的 `PriceRiskModel` 和 `FusionRiskModel` 使用 LSTM；`models/risk_pdf/` 有新版权重 | 已训练和测试 |
| 任务 7：文本与行情融合 | `FusionRiskModel` 拼接两路编码再分类；`models/risk_pdf/fusion.pt` | 已训练和测试 |
| 任务 8：未来三交易日 5% 跌幅标签 | `build_daily_samples.py`；只用未来价格计算标签，特征不读取未来数据 | 已实现 |
| 任务 9：风险模型与预警 | 三个独立检查点、验证集选阈值和概率校准；`risk_pdf_test_summary.json` 记录独立测试结果 | 已训练和测试 |
| 系统：股票查询、行情走势、新闻列表、情绪、指标、概率、等级、历史趋势 | Next.js 页面、FastAPI 接口、SQLite；2026-10-20 宁德时代在线推理返回新版 20×10、777 维输入及三路模型结果；8 项后端测试和前端 Webpack 生产构建通过；三张新版页面实拍见报告第六章 | 已复验 |
| 实验 1：传统模型与 BERT 对照 | 同一验证集 1,585 条：TF-IDF + LinearSVC 的 Accuracy 0.7533、Macro-F1 0.7515；MacBERT 的 Accuracy 0.8025、Macro-F1 0.8071；原始日志在 `output/sentiment/` | 已完成 |
| 实验 2：深度时序模型 | LSTM 20 日输入；行情模型测试 ROC-AUC 0.7689 | 已完成 |
| 实验 3：行情、文本、融合三组消融 | 独立测试 ROC-AUC 分别为 0.7689、0.4926、0.7490 | 已完成；融合未超过行情单独模型 |
| 实验 4：Accuracy、Precision、Recall、F1、ROC-AUC、漏报 | `risk_pdf_test_summary.json` 包含全部指标、TP/FP/FN/TN、AP 和 Brier | 已完成 |
| 实验 5：按时间划分 | 2023–2024 训练、2025 上半年验证、2025 下半年独立测试，分界附近不跨集借未来标签 | 已实现 |
| 提交：七章 Word 报告、实验结果、混淆矩阵、ROC 曲线、系统截图 | `docs/基于金融文本与行情融合的A股短期风险预警系统项目报告_按PDF要求更新.docx` 已写入新版数据、ROC/PR 图、混淆矩阵与三张新版页面实拍；已导出并检查全部 13 页 | 已完成 |

## 数据边界和重要说明

- PDF 第 14–15 页明确允许使用上市公司公开公告作为真实个股文本来源。历史新闻接口仅返回近期少量新闻，2023–2025 年训练期覆盖为零，因此训练和最新推理使用带代码、发布时间与正文的真实公告。网页的其他市场新闻只作背景展示；报告须明确这项边界。
- 五只股票各有 2023–2025 年真实行情；完整新版样本 3,395 条，训练/验证/测试分别为 2,210/570/615 条，正例分别为 119/28/22。样本少、公告稀疏，概率校准和泛化结论必须谨慎。
- 市场输入采用 20 个交易日序列，每日有 10 维；逐日公告输入 777 维。原始成交额已保存，但并未额外作为模型特征，PDF 对它的要求是获取原始行情字段。
- 后端只使用 `risk_pdf` 权重；缺少模型文件时会明确报错。已保存的旧查询记录不会被伪装成新版；新版逐日趋势按 `feature_set` 独立存储。

## 用户在 WSL 中复验的顺序

从 `pbl/` 根目录运行；`set -o pipefail` 使训练失败时流水线返回失败码，`tee` 保存真实终端日志：

```bash
backend/.fastapienv/bin/python -m pip install -r training/sentiment/requirements-baseline.txt
set -o pipefail
backend/.fastapienv/bin/python -u -m training.sentiment.train_baseline 2>&1 | tee output/sentiment/sentiment-baseline.log
backend/.fastapienv/bin/python -u -m training.risk.train_risk --input data/processed/risk_inputs_pdf.npz --output-dir models/risk_pdf 2>&1 | tee output/risk/risk-pdf-training.log
backend/.fastapienv/bin/python -u -m training.risk.evaluate_risk --input data/processed/risk_inputs_pdf.npz --model-dir models/risk_pdf --output-stem risk_pdf_test 2>&1 | tee output/risk/risk-pdf-test.log
```

2026-10-20，传统情绪基线、三个新版风险模型及 615 条样本的独立测试均在 WSL 完成。首次训练曾发生一次无法复现的原生段错误；单批次 CPU、CUDA、禁用 cuDNN 和完整重跑均成功，随后移除了临时诊断代码。原始训练日志保存在 `output/risk/risk-pdf-training.log`，测试日志保存在 `output/risk/risk-pdf-test.log`。

测试集正例 22/615。按验证集选定阈值，行情模型 TP=15、FP=102、FN=7、TN=491，AP=0.0909；文本模型 TP=18、FP=488、FN=4、TN=105，AP=0.0352；融合模型 TP=14、FP=151、FN=8、TN=442，AP=0.0800。文本模型接近随机，融合模型未超过行情模型；新版报告已如实写明。2026-10-20 在线推理和 8 项后端测试已通过，前端 ESLint 与 Webpack 生产构建也通过。报告中的三张新版界面图分别展示风险判断、行情与公告信息、首次逐日趋势；首日趋势只有 1/30 个交易日的两个分数点，符合按交易日逐日积累的设计。
