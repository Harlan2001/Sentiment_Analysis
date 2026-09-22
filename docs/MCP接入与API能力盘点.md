# MCP 接入与 API 能力盘点

## 1. 盘点目的

本文从“其他项目调用本项目”的角度，回答两个问题：

1. 当前 FastAPI Router 中，哪些能力已经开放为 MCP Tool，哪些尚未开放。
2. 当前代码中，哪些功能已经能够实际运行，但还没有独立 API。

> 盘点基于当前 `junlin.li` 分支。项目 REST API 默认前缀为 `/sapi`；MCP 是独立的只读服务，默认入口为 `/mcp`。  
> “已有 REST API”不代表“已接入 MCP”，只有在 `backend/mcp_server/server.py` 中注册的工具才算已接入 MCP。

## 2. 状态说明

| 标记 | 含义 |
|---|---|
| 已完成 | Router 中适合外部读取的主要能力已经注册为 MCP Tool |
| 部分完成 | Router 只有一部分接口已注册为 MCP Tool |
| 未接入（可考虑） | 已有 REST API，但尚未注册为 MCP Tool；满足条件后可开放 |
| 不建议接入 | 属于登录、内部运维、用户管理或强状态操作，不适合作为公共 MCP Tool |

## 3. Router / API 的 MCP 接入情况

### 3.1 面向外部调用的业务能力

| Router 代码定位 | 当前 REST API | 已完成的 MCP Tool | 尚未接入 MCP 的接口 | 结论 |
|---|---|---|---|---|
| `backend/routers/news.py`<br>变量：`router`<br>Tag：`news` | `GET /news`<br>`GET /news/{news_id}`<br>`GET /news/sources`<br>`GET /news/latest-trading-day`<br>`GET /news/similar`<br>`GET /news/search`<br>`GET /yields`<br>`GET /news/{news_id}/yield`<br>`GET /factor/{factor_code}/news` | `search_news`<br>`get_news_detail`<br>`list_news_sources`<br>`get_latest_news_date`<br>`find_similar_news`<br>`semantic_search_news`<br>`get_yield_series`<br>`get_news_yield_impact` | `GET /factor/{factor_code}/news` | **部分完成（8/9）**。建议下一步补 `get_news_by_factor`。 |
| `backend/routers/factors.py`<br>变量：`router`<br>Tag：`factors` | `GET /factors`<br>`GET /factors/paged`<br>`GET /factors/by-category/{category}`<br>`GET /factors/activity-overview` | `list_factors`<br>`list_factors_paged`<br>`list_factors_by_category` | `GET /factors/activity-overview` | **部分完成（3/4）**。未接接口与因子列表信息有一定重叠，优先级低。 |
| `backend/routers/macro.py`<br>变量：`router`<br>Tag：`macro` | `GET /macro/signal`<br>`GET /macro/signal/logs` | `get_macro_signal` | `GET /macro/signal/logs` | **部分完成（1/2）**。日志偏排障和审计，不建议直接公开。 |
| `backend/routers/forecast.py`<br>变量：`router`<br>Tag：`forecast` | `GET /forecast`<br>`GET /forecast/history` | `get_latest_forecast`<br>`get_forecast_history` | 无 | **已完成（2/2）**。 |
| `backend/routers/change.py`<br>变量：`router`<br>Tag：`change` | `POST /change/trigger`<br>`GET /change/snapshots`<br>`POST /change/compare` | `list_change_snapshots` | `POST /change/compare`<br>`POST /change/trigger` | **部分完成（1/3）**。建议补只读的 `compare_change_snapshots`；`trigger` 会生成并写入快照，不应放入当前只读 MCP。 |
| `backend/routers/macro_data.py`<br>变量：`router`<br>Tag：`macro-data` | `GET /macro-data/indicators`<br>`GET /macro-data/data` | `list_macro_indicators`<br>`get_macro_data` | 无 | **已完成（2/2）**。 |
| `backend/routers/discover.py`<br>变量：`router`<br>Tag：`discover` | `GET /discover/news`<br>`GET /discover/market-panel`<br>`GET /discover/yield-detail`<br>`GET /discover/factor-detail` | `get_market_overview`<br>`get_yield_detail`<br>`get_factor_detail` | `GET /discover/news` | **部分完成（3/4）**。`discover/news` 与 `search_news` 高度重叠，暂不必重复开放。 |
| `backend/routers/returns.py`<br>变量：`router`<br>Tag：`returns` | `GET /returns/calendar` | `get_returns_calendar` | 无 | **已完成（1/1）**。 |
| `backend/routers/research.py`<br>变量：`router`<br>Tag：`research` | `GET /research/summary`<br>`GET /research/list`<br>`GET /research/{report_id}`<br>`POST /research/upload`<br>`POST /research/{report_id}/analyze` | `get_research_summary`<br>`search_research_reports` | `GET /research/{report_id}`<br>`POST /research/upload`<br>`POST /research/{report_id}/analyze` | **部分完成（2/5）**。建议补裁剪后的 `get_research_detail`，但应去除内部文件路径和过长正文；上传、分析属于写操作和高成本任务。 |
| `backend/routers/strategy.py`<br>变量：`router`<br>Tag：`strategy` | `POST /strategy/portfolio-analysis` | 无 | `POST /strategy/portfolio-analysis` | **未接入（可考虑）**。对外价值较高，但依赖用户输入、模型费用和执行时长；需先加鉴权、限流、超时及成本控制。 |
| `backend/routers/report.py`<br>变量：`router`<br>Tag：`report` | `GET /report/files/{filename}` | 无 | `GET /report/files/{filename}` | **未接入（可考虑）**。文件下载更适合做 MCP Resource，而不是 Tool。 |
| `backend/routers/graph_augment.py`<br>变量：`router`<br>Tag：`graph-augment` | `GET /graph-augment/job-by-news/{news_id}` | 无 | `GET /graph-augment/job-by-news/{news_id}` | **未接入（低优先级）**。主要用于查询内部图谱增强任务状态。 |
| `backend/routers/report_generation.py`<br>变量：`router`<br>Tag：`report-generation` | `GET /report-generation/sources`<br>`GET /report-generation/tasks`<br>`POST /report-generation/tasks`<br>`GET /report-generation/tasks/{task_id}`<br>`POST /report-generation/tasks/{task_id}/retry`<br>`DELETE /report-generation/tasks/{task_id}`<br>`POST /report-generation/tasks/{task_id}/restore`<br>`DELETE /report-generation/tasks/{task_id}/permanently`<br>`GET /report-generation/tasks/{task_id}/export` | 无 | 左列全部接口 | **未接入（有条件）**。任务查询和导出可考虑；创建、重试、删除等强状态操作不应进入当前只读 MCP。 |
| `backend/routers/daily_news_summary.py`<br>变量：`router`<br>Tag：`daily-news-summaries` | `GET /daily-news-summaries`<br>`GET /daily-news-summaries/{task_id}`<br>`POST /daily-news-summaries`<br>`POST /daily-news-summaries/{task_id}/retry`<br>`DELETE /daily-news-summaries/{task_id}`<br>`POST /daily-news-summaries/{task_id}/restore`<br>`DELETE /daily-news-summaries/{task_id}/permanently` | 无 | 左列全部接口 | **未接入（有条件）**。列表和详情可只读开放；生成与管理操作需要用户身份、成本和权限控制。 |
| `backend/routers/ai_strategy_generation.py`<br>变量：`router`<br>Tag：`ai-strategy-generation` | `POST /ai-strategy-generation/conversations`<br>`GET /ai-strategy-generation/conversations`<br>`GET /ai-strategy-generation/conversations/{conversation_id}`<br>`POST /ai-strategy-generation/conversations/{conversation_id}/draft`<br>`POST /ai-strategy-generation/conversations/{conversation_id}/drafts/{assistant_message_id}/confirm`<br>`PATCH /ai-strategy-generation/conversations/{conversation_id}/archive`<br>`DELETE /ai-strategy-generation/conversations/{conversation_id}`<br>`POST /ai-strategy-generation/conversations/{conversation_id}/restore`<br>`DELETE /ai-strategy-generation/conversations/{conversation_id}/permanently` | 无 | 左列全部接口 | **未接入（有条件）**。与用户会话和异步生成任务强绑定，不适合作为首批公共 MCP。 |
| `backend/routers/watchlist.py`<br>变量：`router`<br>Tag：`watchlist` | `GET /watchlist`<br>`POST /watchlist`<br>`DELETE /watchlist/{item_id}` | 无 | 左列全部接口 | **未接入（有条件）**。读取可在明确用户身份后开放；新增和删除属于个人状态写操作。 |

### 3.2 用户工作台、集成及内部管理能力

| Router 代码定位 | 当前 REST API | MCP 状态 | 判断 |
|---|---|---|---|
| `backend/routers/auth.py`<br>变量：`router`<br>Tag：`auth` | `POST /auth/login`<br>`POST /auth/login/phone`<br>`GET /auth/status`<br>`GET /auth/me` | 未接入 | **不建议接入**。MCP 自身应独立鉴权，不能把登录接口当业务工具。 |
| `backend/routers/pipeline.py`<br>变量：`router`<br>Tag：`pipeline` | `POST /internal/pipeline/trigger` | 未接入 | **不建议公开**。这是内部运维入口，会触发批处理和写库。 |
| `backend/routers/dashboard.py`<br>变量：`router`<br>Tag：`dashboard` | `GET /dashboard/core`<br>`GET /dashboard/history`<br>`POST /dashboard/snapshot`<br>`POST /dashboard/behavior/batch`<br>`POST /dashboard/cleanup-sessions`<br>`POST /dashboard/cleanup-behavior-logs`<br>`GET /dashboard/behavior-stats`<br>`GET /dashboard/behavior-logs`<br>`GET /dashboard/users/active`<br>`GET /dashboard/behavior/profiles`<br>`GET /dashboard/behavior/profile/{user_id}`<br>`GET /dashboard/behavior/compare`<br>`POST /dashboard/behavior/compute-profile/{user_id}`<br>`POST /dashboard/behavior/compute-all-profiles`<br>`GET /dashboard/token/overview`<br>`GET /dashboard/token/trend`<br>`GET /dashboard/token/by-model`<br>`GET /dashboard/token/users`<br>`GET /dashboard/usage/overview`<br>`GET /dashboard/usage/behavior`<br>`GET /dashboard/my-usage/overview`<br>`GET /dashboard/my-usage/trend`<br>`GET /dashboard/my-usage/behavior` | 未接入 | **不建议公开**。该 Router 接口较多且均属用户行为、管理统计或清理操作；如有管理型 MCP，应单独建设并使用管理员权限。 |
| `backend/routers/workbench_sidebar.py`<br>变量：`router`<br>Tag：`workbench-sidebar` | `GET /workbench/sidebar`<br>`GET /workbench/deleted-items`<br>`DELETE /workbench/deleted-items` | 未接入 | **不建议作为公共 MCP**。属于前端聚合和个人工作台状态。 |
| `backend/routers/workbench_projects.py`<br>变量：`router`<br>Tag：`workbench-projects` | `GET /workbench/projects`<br>`POST /workbench/projects`<br>`GET /workbench/projects/{project_id}`<br>`PATCH /workbench/projects/{project_id}`<br>`GET /workbench/projects/{project_id}/conversations`<br>`DELETE /workbench/projects/{project_id}`<br>`POST /workbench/projects/{project_id}/restore`<br>`DELETE /workbench/projects/{project_id}/permanently` | 未接入 | **有条件接入**。必须绑定用户身份和项目权限，不能使用当前共享只读令牌直接开放。 |
| `backend/routers/workbench_conversations.py`<br>变量：`router`<br>Tag：`workbench-conversations` | `POST /workbench/conversations/visitor-chat`<br>`GET /workbench/conversations`<br>`POST /workbench/conversations`<br>`GET /workbench/conversations/{conversation_id}`<br>`PATCH /workbench/conversations/{conversation_id}`<br>`POST /workbench/conversations/{conversation_id}/messages`<br>`DELETE /workbench/conversations/{conversation_id}`<br>`POST /workbench/conversations/{conversation_id}/restore`<br>`DELETE /workbench/conversations/{conversation_id}/permanently` | 未接入 | **有条件接入**。涉及私有会话、模型调用和写操作，需要会话级授权。 |
| `backend/routers/workbench_memories.py`<br>变量：`router`、`settings_router`<br>Tag：`workbench-memories` | `GET/POST /workbench/memories`<br>`PATCH/DELETE /workbench/memories/{memory_id}`<br>`DELETE /workbench/memories`<br>`GET/PATCH /workbench/memory-settings` | 未接入 | **不建议公开**。数据敏感且几乎都是用户私有状态。 |
| `backend/routers/workbench_project_management.py`<br>变量：`router`<br>Tag：`workbench-project-management` | `GET/POST /workbench/projects/{project_id}/memories`<br>`GET/PATCH/DELETE /workbench/projects/{project_id}/memories/{memory_id}`<br>`GET /workbench/projects/{project_id}/members`<br>`PUT/DELETE /workbench/projects/{project_id}/members/{member_username}` | 未接入 | **不建议公开**。涉及项目权限和成员管理。 |
| `backend/routers/workbench_computer.py`<br>变量：`router`<br>Tag：`workbench-computer` | `GET /workbench/computer/tasks` | 未接入 | **不建议公开**。可能暴露本地任务状态。 |
| `backend/routers/workbench_users.py`<br>变量：`router`<br>Tag：`workspace-users` | `GET /workbench/users`<br>`POST /workbench/users`<br>`PATCH /workbench/users/{user_id}` | 未接入 | **不建议公开**。属于管理员用户管理。 |
| `backend/routers/skills.py`<br>变量：`router`<br>Tag：`skills` | `GET/POST /skills`<br>`GET /skills/chat-options`<br>`GET/PUT/DELETE /skills/{skill_id}`<br>`POST /skills/{skill_id}/enable`、`disable`、`archive`、`activate`<br>`POST /skills/{skill_id}/attachments`<br>`DELETE /skills/{skill_id}/attachments/{attachment_id}` | 未接入 | **有条件接入**。更适合工作台内部管理；若开放，需要用户隔离、文件校验和写权限模型。 |
| `backend/routers/feishu_mcp.py`<br>变量：`router`<br>Tag：`feishu-mcp` | `GET/DELETE /mcp/feishu`<br>`POST /mcp/feishu/authorize`<br>`GET /mcp/feishu/callback`<br>`GET /mcp/feishu/tools`<br>`POST /mcp/feishu/tools/{tool_name}` | 未接入当前 MCP | **不建议直接转接**。它本身是第三方 MCP 集成管理层，直接套入公共 MCP 会形成权限和调用链嵌套。 |

### 3.3 当前 MCP 覆盖结论

- 当前共注册 **23 个只读 MCP Tool**，覆盖 9 个业务 Router：`news`、`factors`、`macro`、`forecast`、`change`、`macro-data`、`discover`、`returns`、`research`。
- 核心市场查询能力已经具备对外调用基础，且未修改现有 Router，而是通过独立 MCP 服务复用 REST API。
- 下一批最值得补充的接口是：`get_news_by_factor`、`compare_change_snapshots`、`get_research_detail`。
- `analyze_portfolio_strategy` 也有较高外部价值，但必须先补齐鉴权、限流、超时和模型成本控制，不建议直接并入当前只读 MCP。

## 4. 已有实际功能、但没有独立 API 的能力

下表中的能力已经存在可执行代码或命令行入口，但外部系统不能通过稳定、独立的 HTTP API 直接调用。这里的“未实现”指**未实现 API 层**，不是底层功能不存在。

| 已有能力 | 当前实现位置 / 调用方式 | Router 状态 | 建议新增的 API / Router | 是否适合对外开放 |
|---|---|---|---|---|
| 国债收益率数据下载与增量入库 | `backend/tools/bond_downloader.py`；部署脚本 `scripts/deploy/yield_update_*.sh` | **无对应 Router**。现有 `backend/routers/news.py` 只能读取收益率数据 | 建议新增内部 Router，例如 `backend/routers/yield_admin.py`：触发更新、查询任务状态、查看更新结果 | **优先做内部 API**。涉及外部下载和写库，不建议直接做公共 MCP。 |
| 批量新闻分析与失败兜底 | `backend/analysis/analyzer_runner.py`；`scripts/deploy/analysis_fallback_*.sh` | **只有部分入口**：`backend/routers/pipeline.py` 的 `POST /internal/pipeline/trigger`，没有完整包装该 Runner | 建议扩展 `pipeline.py`：提交分析任务、查询进度、获取问题报告 | **适合内部任务 API**。应采用异步任务、幂等和管理员权限。 |
| 按新闻日期生成预测报告 | `backend/analysis/generate_report.py`；定时脚本 `scripts/deploy/report_push_*.sh` | **无生成 Router**。`backend/routers/forecast.py` 只有结果查询接口 | 建议新增内部生成接口及任务状态接口；可放入独立 `forecast_generation.py` Router | **适合内部 API**。模型成本较高，不宜直接公开。 |
| 预测报告 PDF 生成 | `backend/push/pdf_generator.py` | **无对应 Router**。`backend/routers/report.py` 只能读取已经存在的文件 | 建议新增受控的 PDF 生成接口，或把生成结果作为 MCP Resource 提供 | **适合受控 API 或 MCP Resource**。需限制文件路径和下载权限。 |
| 飞书日报生成与推送 | `backend/push/feishu_daily_push.py` | **无对应 Router**。`backend/routers/feishu_mcp.py` 管理的是飞书 MCP 授权与工具调用，不是日报推送 | 建议新增内部 `feishu_push.py` Router：试运行、执行推送、查询推送结果 | **适合内部 API**。对外推送是有副作用操作，需要审批、去重和审计。 |
| 宏观 CSV 批量导入 | `scripts/macro/import_macro_data.py` | **无导入 Router**。`backend/routers/macro_data.py` 只有指标和数据查询 | 建议新增管理员 Router：上传文件、校验预览、执行导入、返回错误报告 | **适合管理员 API**。必须校验文件、限制目录并支持事务回滚。 |
| 因子自动发现、相似度去重与入标准库 | `backend/factor/factor_candidate_pool.py`<br>`backend/factor/factor_similarity.py`<br>`backend/factor/factor_management.py` | **无管理 Router**。`backend/routers/factors.py` 只有因子读取接口 | 建议新增管理员 Router：候选查询、相似项查看、审核、合并、加入标准库 | **适合管理员审核 API**。不建议让外部 MCP 自动写入标准因子库。 |
| Showcase 演示账号初始化 | `backend/demo/`、`scripts/setup_showcase_profile.py` | **无对应 Router，且代码尚未提交** | 暂不新增；能力稳定并纳入版本管理后再评估管理 API | **暂不做 API**。不能视为正式稳定能力。 |

## 5. 建议顺序

1. 先补三个低风险、只读 MCP Tool：按因子查新闻、快照对比、裁剪后的研报详情。
2. 再为预测报告生成、数据更新、批量分析建设统一的内部异步任务 API。
3. 最后再评估策略生成、日报生成、个人项目等有成本或用户状态的能力；这些能力需要比当前共享只读 MCP 更细的身份和权限模型。
