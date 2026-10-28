# 运行时数据库

SQLite 数据库文件使用 `app.db`，由 `backend/storage/` 中的代码读写。先运行 `backend/.fastapienv/bin/python -m backend.storage.import_predictions` 导入课程历史回测。每次最新推理成功后，`latest_predictions` 更新该股票最近结果，`live_prediction_runs` 追加一条查询记录。`daily_observations` 单独保存新趋势：每只股票每个交易日一条，重复刷新会更新当天分数；缺失日期保留为 `missing` 以便下次重试。旧查询记录和 2025 年测试集不会混入新趋势。数据库文件不会提交到 Git。
