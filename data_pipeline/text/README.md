# 公告正文与情绪特征准备

本目录负责提取 PDF 正文、准备中文金融情绪训练数据，以及用冻结的 MacBERT 生成公告级特征。模型微调代码位于 [`training/sentiment/`](../../training/sentiment/README.md)。

| 文件 | 用途 |
| --- | --- |
| `extract_announcement_texts.py` | 下载样本引用的公告 PDF，提取正文并记录可用状态 |
| `test_extract_announcement_texts.py` | 验证巨潮附件 `.PDF` 返回 404 时尝试 `.pdf` |
| `prepare_sentiment_data.py` | 从已下载的金融情绪 CSV 清洗、去重并分层切分中文样本 |
| `build_sentiment_features.py` | 冻结 MacBERT，计算每份公告的三类情绪分数与 CLS 向量 |

从 `pbl/` 根目录运行正文提取：

```bash
backend/.fastapienv/bin/python -m pip install -r data_pipeline/requirements-probe.txt
backend/.fastapienv/bin/python -m unittest data_pipeline.text.test_extract_announcement_texts -v
backend/.fastapienv/bin/python -m data_pipeline.text.extract_announcement_texts --split train
backend/.fastapienv/bin/python -m data_pipeline.text.extract_announcement_texts --split validation
backend/.fastapienv/bin/python -m data_pipeline.text.extract_announcement_texts --split test
```

也可用 `--split pilot` 对训练公告等距抽样。每份 PDF 缓存到 `data/raw/announcement_pdfs/`，正文及状态按 ID 存于 `data/processed/announcement_texts/`。重复运行跳过已有结果；`--retry-errors` 只重试处理错误，`--retry-unusable` 重试所有正文不达标项。大写 `.PDF` 地址若返回 404，会尝试小写 `.pdf`。单份 PDF 限制 30 MB，只取前 10 页和最多 20,000 字符；失败和不足 100 个汉字的结果保留状态，不伪装为可用正文。

准备情绪训练数据及公告特征：

```bash
backend/.fastapienv/bin/python -m data_pipeline.text.prepare_sentiment_data
backend/.fastapienv/bin/python -m data_pipeline.text.build_sentiment_features
backend/.fastapienv/bin/python -m data_pipeline.text.build_sentiment_features --text-view title_only
```

`prepare_sentiment_data.py` 读取 `data/raw/all_languages_clean.csv`，筛选中文、去重和排除互相冲突的句子；固定随机种子 42，按标签分层切为 80% 训练、20% 验证，输出 `sentiment_train.csv`、`sentiment_validation.csv` 和切分摘要。

`build_sentiment_features.py` 不读取风险标签，输入是公告标题加可用正文开头最多 512 字符、最长 128 token；正文不可用时只输入标题并标记。默认输出 `announcement_sentiment_features.csv`、`announcement_embeddings.npz` 和摘要 JSON，均位于 `data/processed/`。只输入标题的对照模式另存带 `_title_only` 的文件，不覆盖默认结果；摘要 `predicted_labels` 记录预测类别数量。分数未在公告领域校准，不能解释为未来股价下跌概率。显存不足时加 `--batch-size 2`。
