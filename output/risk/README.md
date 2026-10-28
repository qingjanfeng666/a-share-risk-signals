# PDF 完整特征版风险模型日志

`risk-pdf-training.log` 记录三组新版风险模型（行情、公告、融合）的完整训练过程、逐轮验证指标和最佳轮次。输入为 `data/processed/risk_inputs_pdf.npz`，最佳权重与结构化指标位于 `models/risk_pdf/`。

`risk-pdf-test.log` 记录固定模型与验证集阈值后，在 2025 年下半年独立测试集上的评估结果；结构化汇总位于 `data/processed/risk_pdf_test_summary.json`。旧版 20×5 行情、772 维公告特征的训练与测试日志已清理。
