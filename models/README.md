# 模型权重

本目录用于存放训练得到的模型权重。权重文件不提交到 Git，后端推理时从此目录读取。

`sentiment_macbert/` 用于保存最佳验证 macro-F1 的情绪分类模型、分词器和 `training_metrics.json`；`pretrained/` 可放手动下载的预训练模型。这两个目录被 Git 忽略。

`risk_pdf/` 保存 PDF 完整特征版的行情、公告与融合三组风险模型检查点及验证指标；当前后端只读取这组三份权重。
