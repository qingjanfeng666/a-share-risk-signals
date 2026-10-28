# 项目目录与职责

## 当前约定

- `pbl/` 是项目和 Git 仓库根目录。
- `frontend/app/` 保留现有 Next.js 工程位置，由浏览器展示新闻、行情、风险结果。
- `backend/api/` 是接口层：接收 HTTP 请求，校验输入并返回响应。
- `backend/services/` 是业务层：协调抓取、特征构建和模型推理。
- `backend/storage/` 是存储层：把历史预测 CSV 导入 SQLite，并供业务层查询。
- `backend/data/app.db` 是运行时数据库位置，由导入命令创建，不提交 Git。
- `data_pipeline/` 独立于后端：`sources/` 放采集与审计，`samples/` 放交易日样本、标签与索引，`text/` 放公告正文和情绪特征准备。
- `training/` 独立于后端和数据准备：`sentiment/` 训练 MacBERT，`risk/` 训练行情、文本和融合风险模型，不通过 HTTP 请求执行训练。
- `data/` 放训练数据；`models/` 放训练生成的模型权重。后端推理读取模型权重，不在请求处理时训练。
- `output/sentiment/` 放情绪模型训练日志；`output/features/` 放特征构建日志；`output/risk/` 放风险模型训练与评估日志，不放训练数据或模型权重。
- `docs/` 放需求、实验记录和作业报告材料。

## 数据流

```text
Next.js 页面 → FastAPI 接口层 → 业务层 → 存储层 → SQLite 历史预测表
训练评估脚本 → 历史预测 CSV → 导入命令 ────────────────────────↗
                               ↘ 模型权重 → 风险推理
数据准备脚本 → 训练数据 → 模型训练与评估脚本 → 模型权重、output/ 日志
```

## 本地运行约定

开发时由助手修改同一份项目文件，用户在 WSL 中运行并反馈完整命令、错误或实验指标。Python 依赖安装在 `backend/.fastapienv`，前端依赖安装在 `frontend/app/node_modules`；不使用 Conda 或全局 Python 环境。现有虚拟环境已由用户在 WSL 验证，可运行 Python 3.12.3 并导入 FastAPI 0.143.0。
