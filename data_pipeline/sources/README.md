# 数据源探针、采集与审计

本目录只负责从外部来源验证和采集数据，不生成风险训练标签。

| 文件 | 用途 |
| --- | --- |
| `probe_sources.py` | 试取个股新闻、日行情，并检查本地情绪 CSV |
| `probe_live_sources.py` | 检查最新已收盘交易日的行情、可用公告与新闻；不写数据 |
| `diagnose_price_connection.py` | 对比行情接口使用 WSL 代理设置与直连时的结果；不写数据或输出代理地址 |
| `probe_tencent_prices.py` | 试取腾讯前复权日行情，并与已有东方财富快照比较模型输入差异 |
| `probe_announcements.py`、`probe_announcement_pdf.py` | 试取巨潮资讯公告元数据和单份 PDF 正文 |
| `collect_announcements.py` | 按股票和季度采集 2023–2025 年公告元数据 |
| `audit_announcements.py` | 去重、统计公告交易日覆盖并抽样检查 PDF |
| `check_announcement_alignment.py` | 复核公告时间如何归入交易日 |

从 `pbl/` 根目录用 WSL 虚拟环境运行；模块命令保留跨分类导入所需的项目路径：

```bash
backend/.fastapienv/bin/python -m pip install -r data_pipeline/requirements-probe.txt
backend/.fastapienv/bin/python -m data_pipeline.sources.probe_sources --stock 300750
backend/.fastapienv/bin/python -m data_pipeline.sources.probe_live_sources --stock 300750
backend/.fastapienv/bin/python -m data_pipeline.sources.probe_announcements --stock 300750 --start 20250101 --end 20250331
backend/.fastapienv/bin/python -m data_pipeline.sources.probe_announcement_pdf
backend/.fastapienv/bin/python -m data_pipeline.sources.collect_announcements
backend/.fastapienv/bin/python -m data_pipeline.sources.audit_announcements
backend/.fastapienv/bin/python -m data_pipeline.sources.check_announcement_alignment
```

`probe_live_sources` 可把 `--stock` 换成任意六位 A 股代码，用于先检查该代码能否取到足够行情、公告和新闻；训练用批量采集仍只覆盖五只试点股票。

采集脚本按五只股票、12 个季度写 CSV 到 `data/raw/`，已存在的季度默认跳过；要重新下载时加 `--refresh`。审计读取这些 CSV 和已有行情快照，统计公告数量、发布时间精度和交易日覆盖，并从每只股票每年抽样一份 PDF；`--skip-pdf` 可只重算元数据。审计结果写入 `data/processed/announcement_audit_20230101_20251231.json`，原始 PDF 缓存于 `data/raw/announcement_pdfs/`。实测结论见 [`docs/data-audit.md`](../../docs/data-audit.md)。
