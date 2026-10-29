# A 股风险信号舱

输入六位 A 股代码，查看最近已收盘日的短期下跌风险信号、行情与公告依据，并保存个人查询记录。系统以当日收盘为观察点，预测未来 **3 个交易日内是否出现至少 5% 的收盘跌幅**。页面展示综合、行情、公告三路模型分数；近期新闻只供阅读，不进入模型。

> 模型信号仅供风险观察，不构成投资建议。没有预警不表示没有风险；估计概率来自验证集校准，不是未来实际跌幅或可靠收益承诺。

## 功能

- 查询最近收盘价、20 日走势、波动率、最大回撤与成交量变化，以及公告情绪和近期新闻。
- 查看三路风险信号、模型分数、判定阈值与估计风险概率。
- 通过邮箱验证码注册账户并登录；会话保存在可撤销的 HttpOnly Cookie 中。每个账户的最新结果、查询历史与逐日趋势分别保存。
- 手动刷新并补算自首次成功查询以来缺失的交易日；展示最多最近 30 个交易日的模型分数。
- 复现行情、文本、融合模型的训练和独立测试。训练数据与模型权重不随 Git 仓库发布。

## 模型效果与适用范围

2025 年下半年独立测试集包含 615 个样本，其中 22 个为高风险样本。以下数据取自 `risk_pdf_test` 评估；阈值在验证集确定，测试集未用于选轮或选阈值。

| 模型 | AP | ROC-AUC | 测试集召回率 | 测试集误报 / 漏报 |
| --- | ---: | ---: | ---: | ---: |
| 行情 | 0.0909 | 0.7689 | 68.2% | 102 / 7 |
| 公告文本 | 0.0352 | 0.4926 | 81.8% | 488 / 4 |
| 综合 | 0.0800 | 0.7490 | 63.6% | 151 / 8 |

召回率使用各自在验证集选定的阈值。文本模型的 AP 接近测试集 3.58% 的正例比例，且误报很多；综合模型也未优于行情模型。本项目目前适合研究和自托管试用，不应作为自动交易或单独投资决策依据。已有独立回测只覆盖五只试点股票；其他代码可以查询，但没有相同范围的效果验证。

## 项目结构

| 目录 | 用途 |
| --- | --- |
| `frontend/app/` | Next.js 页面、登录与风险展示 |
| `backend/api/`、`backend/services/`、`backend/storage/` | FastAPI 接口、实时推理、SQLite 持久化 |
| `data_pipeline/` | 行情、公告和样本特征准备 |
| `training/sentiment/`、`training/risk/` | 情绪分类及三路风险模型训练、评估 |
| `data/`、`models/` | 本地数据与模型文件，主要内容不提交 Git |
| `output/`、`docs/` | 实验产物说明、架构及接口文档 |

架构细节见 [架构文档](docs/architecture.md)，数据与训练步骤分别见 [数据管线](data_pipeline/README.md)和[训练说明](training/README.md)。

## 本地运行

推荐 WSL Ubuntu、Python 3.12、Node.js 20.9 或更高版本。以下命令均从本仓库根目录执行。

1. 创建 Python 环境并安装依赖。PyTorch 的 CPU/CUDA 安装命令请按本机环境选择 [官方安装说明](https://pytorch.org/get-started/locally/)；风险推理与训练需要 PyTorch。

   ```bash
   python3.12 -m venv backend/.fastapienv
   backend/.fastapienv/bin/python -m pip install -r backend/requirements.txt
   # 按 PyTorch 官方说明在同一虚拟环境安装 torch
   ```

2. 准备本地模型与数据。实时推理需要 `models/sentiment_macbert/` 和 `models/risk_pdf/{price,text,fusion}.pt`。历史回放需 `data/processed/risk_pdf_test_predictions.csv`，并执行：

   ```bash
   backend/.fastapienv/bin/python -m backend.storage.import_predictions
   ```

   这些文件没有放在 GitHub。需要复现时，按 [训练说明](training/README.md)和[数据管线说明](data_pipeline/README.md)准备数据、训练并评估；已有本地文件也可直接放到对应目录。没有权重时，登录和页面可运行，但实时风险推理不可用。

3. 根据需要创建 `backend/.env.local`：

   ```dotenv
   BACKEND_HOST=127.0.0.1
   BACKEND_PORT=8000
   FRONTEND_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
   SESSION_COOKIE_SECURE=false
   SMTP_HOST=smtp.example.com
   SMTP_PORT=465
   SMTP_SECURITY=ssl
   SMTP_USERNAME=your-address@example.com
   SMTP_PASSWORD=your-smtp-app-password
   SMTP_FROM=your-address@example.com
   ```

4. 在两个终端分别启动服务：

   ```bash
   backend/.fastapienv/bin/python -m backend.run
   ```

   ```bash
   cd frontend/app
   npm ci
   npm run dev
   ```

打开 <http://localhost:3000>，用邮箱和至少 12 个字符的密码申请注册，输入邮件中的 8 位验证码后才会创建账户并登录。SMTP 配置使用邮件服务商提供的服务器、端口和应用密码；若使用 587 端口，通常设 `SMTP_SECURITY=starttls`。未配置 SMTP 时注册接口返回 503，已有账户仍可登录。前端通过 Next.js 的 `/api` 转发访问后端；若后端地址不是 `http://127.0.0.1:8000`，在 `frontend/app/.env.local` 设置 `BACKEND_INTERNAL_URL` 并重启前端。Windows 和 WSL 不应共用同一个 `node_modules`，切换环境后在目标环境重新执行 `npm ci`。

## 账户与数据

密码以 Argon2id 哈希保存；服务端只存会话令牌的哈希，Cookie 设置 `HttpOnly` 与 `SameSite=Lax`。登录会话绝对有效期为 30 天，连续 7 天未使用会失效；退出登录会撤销当前会话。登录失败有基础限速。数据库位于 `backend/data/app.db`，不提交 Git。账户的保存结果互相隔离；此前无账户版本的本地记录保留在旧表中，不自动归属任何账户。

新账户的验证码 10 分钟有效、只能使用一次；同一邮箱 60 秒内不可重发、每小时最多发送 5 次，连续输错 5 次后需重新申请。已有账户无需重新验证。当前**没有密码找回**。面向公网部署前还需增加代理层全局限流、配置 HTTPS、`SESSION_COOKIE_SECURE=true`、准确的 `FRONTEND_ORIGINS`、持久化数据库备份和运行监控。不要把 `.env.local`、数据库、原始数据、模型权重或生成日志提交到 Git。

## 检查与参考

```bash
backend/.fastapienv/bin/python -m unittest backend.api.test_auth backend.api.test_routes backend.storage.test_daily_observations backend.services.test_daily_refresh -v
cd frontend/app && npm run lint && npm run build
```

接口详情见 [API 文档](docs/api-contract.md)。模型训练与数据集说明保留在各模块 README 中，便于复现和审查。
