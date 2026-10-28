# 公告特征提取日志

`sentiment-feature-extraction.log` 是用户在 WSL 用已训练的 MacBERT 对 1,985 份公告做冻结推理时的原始终端输出。它记录处理进度和最终数量，不是重新训练模型的日志。生成脚本位于 `data_pipeline/text/build_sentiment_features.py`；公告级情绪分数和向量保存在 `data/processed/`。

只输入标题的对照实验运行时，可另存为 `sentiment-title-only.log`，不要覆盖已有日志：

```bash
set -o pipefail
backend/.fastapienv/bin/python -u -m data_pipeline.text.build_sentiment_features --text-view title_only 2>&1 | tee output/features/sentiment-title-only.log
```

命令从项目根目录 `pbl/` 运行。两种输入视图的结果文件名不同，详见[公告正文与情绪特征准备说明](../../data_pipeline/text/README.md)。

构建 PDF 完整特征版风险模型输入时，可用新的日志文件保存真实终端过程：

```bash
set -o pipefail
backend/.fastapienv/bin/python -u -m data_pipeline.samples.build_risk_inputs 2>&1 | tee output/features/risk-pdf-input-build.log
```

当前新版输入的结构化摘要位于 `data/processed/risk_inputs_pdf_summary.json`；旧版输入构建日志已清理。
