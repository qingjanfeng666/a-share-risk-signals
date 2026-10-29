# FastAPI 服务

后端提供账户登录、独立测试集历史回放、最新已收盘日推理及按账户保存的逐日趋势。最新推理读取 `models/sentiment_macbert/` 与 `models/risk_pdf/` 的已有权重，不会重新训练；新闻仅供展示，风险模型的文本输入来自公司公告。

## 启动

从仓库根目录，在 WSL 中安装 [依赖](requirements.txt)并按 [根目录 README](../README.md) 准备 PyTorch、模型文件及历史 CSV。首次需要历史回放时运行：

```bash
backend/.fastapienv/bin/python -m backend.storage.import_predictions
backend/.fastapienv/bin/python -m backend.run
```

服务默认监听 `127.0.0.1:8000`。可在不提交 Git 的 `backend/.env.local` 中配置：

```dotenv
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
FRONTEND_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
SESSION_COOKIE_SECURE=false
```

前端通过 Next.js 同源 `/api` 转发请求。非本地 HTTPS 部署时设置 `SESSION_COOKIE_SECURE=true`，并只列出实际前端域名。数据库 `backend/data/app.db` 在本机创建，不提交 Git。

## 账户与会话

`POST /api/auth/register` 用邮箱和至少 12 字符的密码注册并自动登录；`POST /api/auth/login` 登录；`GET /api/auth/me` 检查会话；`POST /api/auth/logout` 撤销会话。密码用 Argon2id 哈希保存，会话 Cookie 设有 HttpOnly 和 SameSite=Lax。除 `/api/health` 外，接口需要有效会话。账户的最新推理结果、运行历史和逐日趋势各自隔离；旧版无账户数据仍在旧表，不自动展示给任何新账户。

登录失败有基础限速。当前没有邮箱验证与密码找回，公网部署还需补齐相关能力、注册限流、HTTPS 和数据库备份。

## 推理与检查

```bash
backend/.fastapienv/bin/python -u -m backend.services.live_inference --stock 300750
backend/.fastapienv/bin/python -m unittest backend.api.test_auth backend.api.test_routes backend.storage.test_daily_observations backend.services.test_daily_refresh -v
```

直接运行 `live_inference` 只打印推理结果；网页的刷新接口还会按账户保存结果与逐日趋势。完整端点和返回字段见 [API 约定](../docs/api-contract.md)。历史回放仍只覆盖五只试点股票；其他六位代码可尝试最新推理，但尚无同范围独立回测。
