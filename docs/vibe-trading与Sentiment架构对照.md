# vibe-trading 与 Sentiment 技术架构对照

更新时间：2026-05-12

## 一、重合项（Sentiment 已具备）

| 维度 | vibe-trading 架构项 | Sentiment 现状 | 结论 |
|---|---|---|---|
| 前端基础 | TypeScript + React 19 + Vite | 已使用 | 重合 |
| 样式 | Tailwind CSS | 已使用 | 重合 |
| 状态管理 | Zustand | 已使用 | 重合 |
| 路由 | React Router v7 | 已使用（react-router-dom 7.x） | 重合 |
| 流式通信 | SSE（Server-Sent Events） | 已有后端 text/event-stream，前端已有 EventSource 与流式解析 | 重合 |
| 后端框架 | Python 3.11+ + FastAPI + Uvicorn | 已使用（当前主要端口为 8000） | 重合（端口不同） |
| 数据校验 | Pydantic v2 | 已使用 | 重合 |
| LLM 接入 | OpenAI 兼容接口 | 已接入（OpenAI SDK + 兼容网关） | 重合 |
| 图表 | ECharts | 已使用 | 可以 |

## 二、未重合项（Sentiment 当前未落地）

| 维度 | vibe-trading 架构项 | Sentiment 当前情况 | 是否可加入 |
|---|---|---|---|
| Agent 编排 | LangChain / LangGraph（含 Swarm） | 未发现相关依赖与编排代码 | 可以 |
| 本地分析库 | DuckDB | 当前主库为 MySQL，向量检索为 Faiss | 可以 |
| 协议层 | MCP Server（fastmcp） | 未发现 fastmcp / mcp server | 可以 |
| 多市场数据源 | yfinance、akshare、tushare、ccxt | 未发现对应接入 | 可以 |
| 回测层 | backtest/ 自研引擎 | 未发现 backtest 目录 | 可以 |
| 服务端口规范 | 后端 8899 | 当前为 8000（本地与容器） | 可以 |

## 三、缺失项可接入性判断（简版）

| 项目 | 接入难度 | 价值 | 建议 |
|---|---|---|---|
| LangGraph 编排 | 中 | 高（Agent 可维护性与扩展性提升） | 先单 Agent 编排，再扩展多 Agent |
| DuckDB 分析层 | 中 | 高（本地分析/聚合/回测效率） | 建议做 MySQL -> DuckDB 增量同步 |
| fastmcp | 中-高 | 中-高（标准化工具暴露、利于外部 Agent 集成） | 先暴露 3-5 个核心只读工具 |
| 多市场数据源接入 | 中 | 高（覆盖面和策略可用性提升） | 建统一 Data Adapter，再分源接入 |
| backtest 引擎 | 高 | 高（策略闭环能力） | 先做 MVP：信号->持仓->绩效 |
| 端口切换到 8899 | 低 | 低（主要是部署规范对齐） | 最后一步统一改造 |

## 四、推荐实施顺序（两阶段）

### 阶段 A（快速增益，1-2 周）

1. ECharts 试点接入（不替换全站，先并存）。
2. 引入一个外部数据源（建议 yfinance 或 akshare）并统一数据结构。
3. 统一配置项，支持后端端口可配（包含 8899）。

### 阶段 B（架构升级，2-4 周）

1. 引入 LangGraph，重构现有 Agent/工具调用链。
2. 增加 DuckDB 分析层并建立增量同步。
3. 上线 fastmcp，暴露核心数据查询/分析工具。
4. 新建 backtest 模块，打通“信号 -> 回测 -> 报告”闭环。

## 五、结论

Sentiment 与 vibe-trading 在前后端基础栈和流式交互上重合度较高。主要差距集中在 Agent 编排标准化、分析型数据层、跨市场数据源、回测引擎四个方向。以上缺失项都可以在当前项目基础上渐进式引入，不需要推翻重建。
