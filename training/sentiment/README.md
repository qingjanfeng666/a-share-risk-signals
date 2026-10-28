# MacBERT 中文金融情绪分类

本目录包含：

- `train_baseline.py`：用同一训练/验证划分训练字符 TF-IDF + 线性 SVM，作为 PDF 实验 1 要求的传统基线；指标写入 `models/sentiment_baseline_metrics.json`。
- `requirements-baseline.txt`：基线所需的 scikit-learn，不使用全局 Python 环境。

- `download_macbert.py`：将预训练 MacBERT 下载到 `models/pretrained/chinese-macbert-base/`。
- `train_sentiment.py`：读取 `data/processed/sentiment_train.csv` 和 `sentiment_validation.csv`，训练 negative、neutral、positive 三分类模型；按验证 macro-F1 保存最佳权重到 `models/sentiment_macbert/`。
- `requirements.txt`：情绪模型所需的 Transformers 与 ModelScope 依赖；PyTorch 按本机 CUDA 版本单独安装。

训练脚本的验证集是金融情绪短句，不是未来三日股价风险验证集。最佳模型的逐轮指标位于 `models/sentiment_macbert/training_metrics.json`；完整原始终端输出位于 `output/sentiment/sentiment-training-stdout.log`。

2026-10-20 在 WSL 运行传统基线后，验证集 1,585 条上的 Accuracy 为 0.7533、Macro-F1 为 0.7515；相同划分下 MacBERT 分别为 0.8025、0.8071。基线真实终端输出保存在 `output/sentiment/sentiment-baseline.log`。

## WSL 中运行

从 `pbl/` 根目录检查 GPU 和依赖：

```bash
nvidia-smi
backend/.fastapienv/bin/python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
backend/.fastapienv/bin/python -m pip install -r training/sentiment/requirements.txt
```

本项目曾在 WSL 中使用 PyTorch 2.13.0+cu132。若需要重新配置环境，先按 [PyTorch 官方安装说明](https://pytorch.org/get-started/previous-versions/)安装适合驱动的版本；不需要 torchvision。

当前 WSL 无法直连 Hugging Face。可先用 `download_macbert.py` 从 [ModelScope 镜像](https://modelscope.cn/models/dienstag/chinese-macbert-base)下载本地预训练权重，再训练：

```bash
backend/.fastapienv/bin/python training/sentiment/download_macbert.py
backend/.fastapienv/bin/python training/sentiment/train_sentiment.py --model models/pretrained/chinese-macbert-base
```

默认 batch size 4、最长 128 token、3 轮；显存不足时加 `--batch-size 2`。若需重训并保存本次真实终端输出，请使用新日志名，避免覆盖已有记录：

```bash
set -o pipefail
backend/.fastapienv/bin/python -u training/sentiment/train_sentiment.py --model models/pretrained/chinese-macbert-base 2>&1 | tee output/sentiment/sentiment-training-next-run.log
```

这条命令会重新训练；只查看已有日志可运行 `cat output/sentiment/sentiment-training-stdout.log`。预训练权重的分类头首次加载时会提示新初始化，训练会更新它和 MacBERT 主体参数。
