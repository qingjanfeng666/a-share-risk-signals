# 交易日样本、风险标签与文本索引

本目录把已保存的行情、公告元数据与正文提取结果对齐到“股票—交易日”。

| 文件 | 用途 |
| --- | --- |
| `check_risk_labels.py` | 预览未来三交易日跌幅至少 5% 的标签分布 |
| `build_daily_samples.py` | 生成 20 日行情窗口、未来三交易日风险标签和公告 ID 引用 |
| `build_daily_text_index.py` | 将可用与不可用公告正文 ID 关联到每日样本 |
| `build_risk_inputs.py` | 将 20 日行情窗口与预测日公告特征拼成风险模型输入 |
| `test_build_daily_samples.py` | 验证公告时间归属和时间划分边界 |
| `test_build_risk_inputs.py` | 验证行情窗口不读取未来交易日、无公告日有显式零特征 |

从 `pbl/` 根目录运行：

```bash
backend/.fastapienv/bin/python -m data_pipeline.samples.check_risk_labels
backend/.fastapienv/bin/python -m data_pipeline.samples.build_daily_samples
backend/.fastapienv/bin/python -m unittest data_pipeline.samples.test_build_daily_samples -v
backend/.fastapienv/bin/python -m data_pipeline.samples.build_daily_text_index
backend/.fastapienv/bin/python -m data_pipeline.samples.build_daily_text_index --split validation
backend/.fastapienv/bin/python -m data_pipeline.samples.build_daily_text_index --split test
```

`build_daily_samples.py` 输出 `data/processed/daily_samples_2023_2025.csv` 及统计 JSON。训练、验证、测试按时间分别覆盖 2023–2024 年、2025 年上半年、2025 年下半年；跨越划分边界的未来三日标签样本会排除。公告在 15:00 后发布或只有日期精度时，保守归到下一交易日。

正文提取完成后，`build_daily_text_index.py` 为各时间段输出 `daily_text_index_<split>.csv` 和统计 JSON。它核对公告 ID、股票代码及发布时间归属；索引保留正文不可用的公告 ID，不含风险标签、情绪分数或文本向量。运行验证或测试索引前，先按[正文提取说明](../text/README.md)处理相应公告。

公告特征提取完成后，生成风险模型输入：

```bash
backend/.fastapienv/bin/python -m unittest data_pipeline.samples.test_build_risk_inputs -v
backend/.fastapienv/bin/python -m data_pipeline.samples.build_risk_inputs
```

输出 `data/processed/risk_inputs_pdf.npz`、`risk_inputs_pdf_summary.json` 和 `daily_text_stats_pdf.csv`。每行保留原样本的股票、日期、时间划分及风险标签；行情输入为 20 个交易日、每日 10 个特征，包含价格与成交量变化、5/10/20 日波动率、最大回撤和成交量变化率。文本输入为预测日公告的 768 维 CLS 向量均值、三类情绪分数、公告数及日级情绪统计，共 777 维；无公告日保留显式零特征。脚本核对公告 ID、股票、时间划分和行情窗口，不使用未来价格构造输入特征。标题单独输入的对照文件可用 `--text-view title_only` 另行生成。
