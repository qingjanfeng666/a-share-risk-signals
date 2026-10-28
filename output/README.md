# 终端运行日志

这里保存用户在 WSL 实际运行时的终端输出，供复现和作业检查；处理后数据放在 `data/processed/`，模型权重放在 `models/`。

| 分类 | 内容 |
| --- | --- |
| [`sentiment/`](sentiment/README.md) | MacBERT 情绪模型训练过程 |
| [`features/`](features/README.md) | 冻结模型提取公告特征的过程 |
| [`risk/`](risk/README.md) | 三组风险模型训练与后续评估过程 |

后续命令使用 `2>&1 | tee output/<分类>/<新文件名>.log` 同时显示并保存输出；运行前用 `set -o pipefail` 保留脚本失败状态。每次运行使用新文件名，不覆盖已有原始日志。现有 `sentiment-training-stdout.log` 是用户当时粘贴的真实终端记录，其中的旧脚本路径保留作为历史记录。
