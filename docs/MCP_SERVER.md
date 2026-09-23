# Sentiment MCP Server

本项目提供一个独立的 MCP Server，将 FastAPI 数据查询与债券研究业务能力暴露给其他
AI 项目。MCP facade 不复制数据库逻辑，而是通过内部 HTTP 调用已有 `/sapi` 接口。

## 配置

```dotenv
SENTIMENT_INTERNAL_API_URL=http://127.0.0.1:8000
SENTIMENT_INTERNAL_API_TOKEN=replace-with-backend-internal-token
SENTIMENT_MCP_ACCESS_TOKEN=replace-with-a-different-long-random-token
SENTIMENT_MCP_HOST=127.0.0.1
SENTIMENT_MCP_PORT=8002
SENTIMENT_MCP_RESOURCE_URL=http://127.0.0.1:8002/mcp
SENTIMENT_MCP_ISSUER_URL=http://127.0.0.1:8002
SENTIMENT_MCP_BACKEND_TIMEOUT_SECONDS=650
```

`SENTIMENT_MCP_ACCESS_TOKEN` 是外部 MCP 客户端使用的 Bearer Token；它必须与后端的
`SENTIMENT_INTERNAL_API_TOKEN` 不同。后者只供 MCP facade 调用现有 FastAPI 服务。

## 启动

先启动 FastAPI 后端，再启动 MCP：

```powershell
uv run sentiment-mcp
```

也可以直接运行模块：

```powershell
uv run python -m backend.mcp_server
```

客户端连接地址为 `http://127.0.0.1:8002/mcp`，并携带：

```http
Authorization: Bearer <SENTIMENT_MCP_ACCESS_TOKEN>
```

对外部署时，应把 `SENTIMENT_MCP_RESOURCE_URL` 和 `SENTIMENT_MCP_ISSUER_URL` 改成
真实 HTTPS 地址，并通过反向代理限制来源、请求大小和速率。

## 工具范围

服务显式注册 30 个工具，不会从 OpenAPI 自动暴露新增接口：

- 保留原有 23 个只读原子工具，覆盖新闻、收益率、因子、宏观信号、预测、市场概览、
  收益日历和研报检索。
- 新增 7 个业务工具：Sentiment 完整 Markdown 问答、单条债券舆情分析、
  市场舆情综述、市场变动归因、历史相似事件影响分析、债券市场预测生成、
  结构化新闻总结。

业务工具可能调用大模型并产生分析缓存或预测报告。服务仍不包含上传、删除、用户管理、
工作台项目、个人数据操作或交易执行。

## 本地 Client 验证

```powershell
uv run python scripts/ask_sentiment_client.py "政策驱动对下半年债市的影响"
```

`analyze_bond_sentiment` 同时返回新闻正文和 `source_url`，便于调用方直接
展示原文或提供可点击的来源链接。
