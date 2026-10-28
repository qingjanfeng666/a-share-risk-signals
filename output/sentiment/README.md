# 情绪模型训练日志

`sentiment-training-stdout.log` 是用户在 WSL 训练 MacBERT 时的原始终端输出，含每 100 步训练损失、每轮验证指标以及最佳模型保存结果。它记录的是整理目录前执行的旧脚本路径；当前训练脚本位于 `training/sentiment/train_sentiment.py`。

结构化逐轮指标另外保存在 `models/sentiment_macbert/training_metrics.json`。重新训练时在本目录用新文件名保存日志，命令见 [`training/sentiment/README.md`](../../training/sentiment/README.md)。
