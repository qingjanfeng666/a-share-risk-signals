# 数据准备

本目录按数据流分为三个分类。模型训练和评估另放在 `training/`，原始与处理后的数据放在项目根目录的 `data/`。

| 分类 | 负责内容 | 说明 |
| --- | --- | --- |
| [`sources/`](sources/README.md) | 数据源探针、历史公告采集与可用性审计 | 外部数据进入 `data/raw/` |
| [`samples/`](samples/README.md) | 交易日样本、风险标签和每日文本索引 | 时间对齐与防止标签跨界 |
| [`text/`](text/README.md) | 公告 PDF 正文、情绪样本与 MacBERT 特征准备 | 不执行模型微调 |

`requirements-probe.txt` 是采集探针和 PDF 提取共用的依赖文件。所有命令从 `pbl/` 根目录运行，使用现有 WSL 虚拟环境 `backend/.fastapienv/bin/python`。分类之间有 Python 导入，因此运行脚本使用 `python -m data_pipeline.<分类>.<模块>`；测试使用 `python -m unittest data_pipeline.<分类>.<测试模块> -v`。各分类 README 给出完整命令与输出位置。

已完成的数据质量与实验统计见 [`docs/data-audit.md`](../docs/data-audit.md)。
