# 三组风险预测模型

## PDF 完整特征版（优先验收）

`data/processed/risk_inputs_pdf.npz` 使用 20×10 行情输入和 777 维公告输入，包含 PDF 指定的波动率、回撤、成交量变化和日级情绪统计。下面命令在 WSL 项目根目录运行，权重存入 `models/risk_pdf/`：

```bash
set -o pipefail
backend/.fastapienv/bin/python -u -m training.risk.train_risk --input data/processed/risk_inputs_pdf.npz --output-dir models/risk_pdf 2>&1 | tee output/risk/risk-pdf-training.log
backend/.fastapienv/bin/python -u -m training.risk.evaluate_risk --input data/processed/risk_inputs_pdf.npz --model-dir models/risk_pdf --output-stem risk_pdf_test 2>&1 | tee output/risk/risk-pdf-test.log
```

仍分别训练行情 LSTM、公告 MLP 和两路融合模型。测试汇总在 `data/processed/risk_pdf_test_summary.json`，包括准确率、精确率、召回率、F1、ROC-AUC、AP、TP/FP/FN/TN 和校准后 Brier 分数。原模型分数用于验证阈值预警；另使用验证集拟合单调 sigmoid 映射，输出**模型估计**风险概率。验证集只有 28 个高风险日，估计概率不能保证是真实未来跌幅频率。完整逐轮终端日志由 `tee` 原样保存。

当前训练与验收使用上述 PDF 完整特征版。旧版 20×5 行情、772 维公告输入的模型文件与日志已清理。
