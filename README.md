# 股票新闻与行情风险预测项目

本项目用于课程作业。本目录 `pbl/` 是项目根目录；前端、后端、数据准备、模型训练、训练数据与模型文件分开存放。

## 目录

```text
pbl/
├── frontend/
│   └── app/              # 现有 Next.js 应用，保留原位置
├── backend/
│   ├── .fastapienv/      # 现有 WSL Python 虚拟环境，不提交 Git
│   ├── api/              # FastAPI 路由、请求与响应
│   ├── services/         # 新闻抓取、特征处理与风险推理
│   ├── storage/          # SQLite 和文件读写
│   └── data/             # 运行时 SQLite 数据库（app.db）
├── data_pipeline/
│   ├── sources/          # 数据源探针、采集与审计
│   ├── samples/          # 交易日样本、标签与文本索引
│   └── text/             # 公告正文与情绪特征准备
├── training/
│   ├── sentiment/        # MacBERT 下载与情绪分类训练
│   └── risk/             # 行情、文本和融合风险模型训练
├── data/                 # 训练使用的原始与处理后数据
├── models/               # 训练得到的模型权重
├── output/
│   ├── sentiment/        # 情绪模型训练日志
│   ├── features/         # 公告特征提取日志
│   └── risk/             # 风险模型训练日志
└── docs/                 # 作业文档与架构说明
```

`data_pipeline/` 负责生成训练数据，`training/` 负责训练模型和评估；后端读取权重进行推理。数据库文件和大体积数据、权重不提交到 Git。各目录的具体职责见 [docs/architecture.md](docs/architecture.md)，分类索引见 [data_pipeline/README.md](data_pipeline/README.md)、[training/README.md](training/README.md) 和 [output/README.md](output/README.md)。

作业 PDF 的逐项核对结果及实际验收状态见 [docs/assignment-compliance.md](docs/assignment-compliance.md)。PDF 完整特征版模型已于 2026-10-20 完成训练和独立测试；七章项目报告见 [docs/基于金融文本与行情融合的A股短期风险预警系统项目报告_按PDF要求更新.docx](docs/基于金融文本与行情融合的A股短期风险预警系统项目报告_按PDF要求更新.docx)。

## WSL 中进入项目

```bash
cd '/mnt/d/新建文件夹/pbl xinwen/pbl'
backend/.fastapienv/bin/python --version
cd frontend/app && npm run dev
```

前端与后端需要分别运行。启动和逐日趋势的使用说明分别见 [backend/README.md](backend/README.md) 和 [frontend/app/README.md](frontend/app/README.md)；接口字段见 [docs/api-contract.md](docs/api-contract.md)。数据准备和模型训练命令见各目录的 README。
