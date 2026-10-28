# 模型训练与评估

本目录只放模型训练、评估及其依赖文件；数据构建和预处理放在并列的 `data_pipeline/`。当前已有的代码归入以下分类：

| 分类 | 内容 | 说明 |
| --- | --- | --- |
| [`sentiment/`](sentiment/README.md) | MacBERT 下载、中文金融情绪分类训练与依赖 | 已完成首轮训练 |
| [`risk/`](risk/README.md) | 行情 LSTM、公告 MLP、融合风险模型的训练与验证 | 三组消融 |

项目根目录的 `data/processed/` 存放输入数据，`models/` 存放权重，`output/` 存放终端日志。所有命令从 `pbl/` 根目录运行，使用 `backend/.fastapienv/bin/python`，不使用 Conda 或全局 Python。最终测试集评估在模型与验证阈值固定后进行。
