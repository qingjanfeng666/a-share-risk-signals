# 训练数据

本目录用于训练数据。后续可按 `raw/` 与 `processed/` 分开保存原始和处理后的数据；大体积数据不提交到 Git。

已下载情绪训练数据 `raw/all_languages_clean.csv`，来源为 [Kenpache/multilingual-financial-sentiment](https://huggingface.co/datasets/Kenpache/multilingual-financial-sentiment)。文件被 Git 忽略；字段、行数和 SHA-256 记录在 [数据源验证记录](../docs/data-audit.md)。

运行 `data_pipeline/text/prepare_sentiment_data.py` 后，会生成 `processed/sentiment_train.csv`、`processed/sentiment_validation.csv` 和 `processed/sentiment_split_summary.json`；它们只包含中文情绪样本，供后续 MacBERT 微调使用。

五只股票 2023–2025 年的巨潮公告元数据按季度保存在 `raw/`；已提取的公告 PDF 位于 `raw/announcement_pdfs/`。审计 JSON 位于 `processed/`。这些均为可重新生成的数据，不提交 Git。

`processed/daily_samples_2023_2025.csv` 是按交易日对齐的风险标签与公告引用表；`processed/daily_samples_summary_2023_2025.json` 记录样本、正例及公告交集统计。它们由 `data_pipeline/samples/build_daily_samples.py` 生成，同样不提交 Git。

`processed/announcement_texts/` 按公告 ID 保存提取的正文与质量状态；`processed/announcement_text_manifest_<split>.json` 汇总每批次结果。提取规则见 `data_pipeline/README.md`。

`processed/daily_text_index_train.csv` 按“股票—交易日”列出训练样本可用和不可用正文的公告 ID，与 `daily_samples_2023_2025.csv` 按 `stock`、`date` 关联。逐日统计位于同名 `_summary.json`；生成方法见 `data_pipeline/README.md`。

`processed/risk_inputs_pdf.npz` 是行情窗口和预测日公告特征对齐后的风险模型输入，包含 `price`、`news`、`label`、`split`、`stock` 和 `date` 数组；`risk_inputs_pdf_summary.json` 记录形状与各时间段样本数。生成方式见 [`data_pipeline/samples/README.md`](../data_pipeline/samples/README.md)。
