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

| Router | 当前 REST API | 已完成的 MCP Tool | 尚未接入 MCP 的接口 | 结论 |
|---|---|---|---|---|
| `news` | `GET /news`<br>`GET /news/{news_id}`<br>`GET /news/sources`<br>`GET /news/latest-trading-day`<br>`GET /news/similar`<br>`GET /news/search`<br>`GET /yields`<br>`GET /news/{news_id}/yield`<br>`GET /factor/{factor_code}/news` | `search_news`<br>`get_news_detail`<br>`list_news_sources`<br>`get_latest_news_date`<br>`find_similar_news`<br>`semantic_search_news`<br>`get_yield_series`<br>`get_news_yield_impact` | `GET /factor/{factor_code}/news` | **部分完成（8/9）**。建议下一步补 `get_news_by_factor`。 |
| `factors` | `GET /factors`<br>`GET /factors/paged`<br>`GET /factors/by-category/{category}`<br>`GET /factors/activity-overview` | `list_factors`<br>`list_factors_paged`<br>`list_factors_by_category` | `GET /factors/activity-overview` | **部分完成（3/4）**。未接接口与因子列表信息有一定重叠，优先级低。 |
| `macro` | `GET /macro/signal`<br>`GET /macro/signal/logs` | `get_macro_signal` | `GET /macro/signal/logs` | **部分完成（1/2）**。日志偏排障和审计，不建议直接公开。 |
| `forecast` | `GET /forecast`<br>`GET /forecast/history` | `get_latest_forecast`<br>`get_forecast_history` | 无 | **已完成（2/2）**。 |
| `change` | `POST /change/trigger`<br>`GET /change/snapshots`<br>`POST /change/compare` | `list_change_snapshots` | `POST /change/compare`<br>`POST /change/trigger` | **部分完成（1/3）**。建议补只读的 `compare_change_snapshots`；`trigger` 会生成并写入快照，不应放入当前只读 MCP。 |
| `macro-data` | `GET /macro-data/indicators`<br>`GET /macro-data/data` | `list_macro_indicators`<br>`get_macro_data` | 无 | **已完成（2/2）**。 |
| `discover` | `GET /discover/news`<br>`GET /discover/market-panel`<br>`GET /discover/yield-detail`<br>`GET /discover/factor-detail` | `get_market_overview`<br>`get_yield_detail`<br>`get_factor_detail` | `GET /discover/news` | **部分完成（3/4）**。`discover/news` 与 `search_news` 高度重叠，暂不必重复开放。 |
| `returns` | `GET /returns/calendar` | `get_returns_calendar` | 无 | **已完成（1/1）**。 |
| `research` | `GET /research/summary`<br>`GET /research/list`<br>`GET /research/{report_id}`<br>`POST /research/upload`<br>`POST /research/{report_id}/analyze` | `get_research_summary`<br>`search_research_reports` | `GET /research/{report_id}`<br>`POST /research/upload`<br>`POST /research/{report_id}/analyze` | **部分完成（2/5）**。建议补裁剪后的 `get_research_detail`，但应去除内部文件路径和过长正文；上传、分析属于写操作和高成本任务。 |
| `strategy` | `POST /strategy/portfolio-analysis` | 无 | 全部 | **未接入（可考虑）**。对外价值较高，但依赖用户输入、模型费用和执行时长；需先加鉴权、限流、超时及成本控制。 |
| `report` | `GET /report/files/{filename}` | 无 | 全部 | **未接入（可考虑）**。文件下载更适合做 MCP Resource，而不是 Tool。 |
| `graph-augment` | `GET /graph-augment/job-by-news/{news_id}` | 无 | 全部 | **未接入（低优先级）**。主要用于查询内部图谱增强任务状态。 |
| `report-generation` | 来源查询、任务列表、创建、详情、重试、删除、恢复、永久删除、导出，共 9 个接口 | 无 | 全部 | **未接入（有条件）**。任务查询和导出可考虑；创建、重试、删除等强状态操作不应进入当前只读 MCP。 |
| `daily-news-summaries` | 任务列表、详情、创建、重试、删除、恢复、永久删除，共 7 个接口 | 无 | 全部 | **未接入（有条件）**。列表和详情可只读开放；生成与管理操作需要用户身份、成本和权限控制。 |
| `ai-strategy-generation` | 会话列表、详情、创建、生成草稿、确认、归档、恢复、删除等，共 9 个接口 | 无 | 全部 | **未接入（有条件）**。与用户会话和异步生成任务强绑定，不适合作为首批公共 MCP。 |
| `watchlist` | `GET /watchlist`<br>`POST /watchlist`<br>`DELETE /watchlist/{item_id}` | 无 | 全部 | **未接入（有条件）**。读取可在明确用户身份后开放；新增和删除属于个人状态写操作。 |

### 3.2 用户工作台、集成及内部管理能力

| Router | 当前能力 | MCP 状态 | 判断 |
|---|---|---|---|
| `auth` | 登录、手机号登录、登录状态、当前用户，共 4 个接口 | 未接入 | **不建议接入**。MCP 自身应独立鉴权，不能把登录接口当业务工具。 |
| `pipeline` | 触发内部新闻处理流水线，共 1 个接口 | 未接入 | **不建议公开**。这是内部运维入口，会触发批处理和写库。 |
| `dashboard` | 核心统计、历史、行为日志、画像、Token 与用量统计、清理任务等，共 23 个接口 | 未接入 | **不建议公开**。包含用户行为、管理统计和清理操作；如有管理型 MCP，应单独建设并使用管理员权限。 |
| `workbench-sidebar` | 侧边栏、已删除项目、清空回收站，共 3 个接口 | 未接入 | **不建议作为公共 MCP**。属于前端聚合和个人工作台状态。 |
| `workbench-projects` | 项目列表、创建、详情、修改、会话列表、删除、恢复、永久删除，共 8 个接口 | 未接入 | **有条件接入**。必须绑定用户身份和项目权限，不能使用当前共享只读令牌直接开放。 |
| `workbench-conversations` | 游客聊天、会话列表、创建、详情、修改、发消息、删除、恢复、永久删除，共 9 个接口 | 未接入 | **有条件接入**。涉及私有会话、模型调用和写操作，需要会话级授权。 |
| `workbench-memories` | 记忆查询、创建、修改、删除、批量清空，以及记忆设置读取和修改，共 7 个接口 | 未接入 | **不建议公开**。数据敏感且几乎都是用户私有状态。 |
| `workbench-project-management` | 项目记忆增删改查、项目成员查询与增删，共 8 个接口 | 未接入 | **不建议公开**。涉及项目权限和成员管理。 |
| `workbench-computer` | 计算机任务查询，共 1 个接口 | 未接入 | **不建议公开**。可能暴露本地任务状态。 |
| `workspace-users` | 用户列表、创建、修改，共 3 个接口 | 未接入 | **不建议公开**。属于管理员用户管理。 |
| `skills` | Skill 列表、详情、创建、修改、启停、归档、删除及附件管理，共 12 个接口 | 未接入 | **有条件接入**。更适合工作台内部管理；若开放，需要用户隔离、文件校验和写权限模型。 |
| `feishu-mcp` | 飞书授权、回调、连接删除、工具列表、工具调用，共 6 个接口 | 未接入当前 MCP | **不建议直接转接**。它本身是第三方 MCP 集成管理层，直接套入公共 MCP 会形成权限和调用链嵌套。 |

### 3.3 当前 MCP 覆盖结论

- 当前共注册 **23 个只读 MCP Tool**，覆盖 9 个业务 Router：`news`、`factors`、`macro`、`forecast`、`change`、`macro-data`、`discover`、`returns`、`research`。
- 核心市场查询能力已经具备对外调用基础，且未修改现有 Router，而是通过独立 MCP 服务复用 REST API。
- 下一批最值得补充的接口是：`get_news_by_factor`、`compare_change_snapshots`、`get_research_detail`。
- `analyze_portfolio_strategy` 也有较高外部价值，但必须先补齐鉴权、限流、超时和模型成本控制，不建议直接并入当前只读 MCP。

## 4. 已有实际功能、但没有独立 API 的能力

下表中的能力已经存在可执行代码或命令行入口，但外部系统不能通过稳定、独立的 HTTP API 直接调用。这里的“未实现”指**未实现 API 层**，不是底层功能不存在。

| 已有能力 | 当前实现位置 / 调用方式 | 当前能做什么 | 缺少的 API | 是否适合对外开放 |
|---|---|---|---|---|
| 国债收益率数据下载与增量入库 | `backend/tools/bond_downloader.py`；部署脚本 `scripts/deploy/yield_update_*.sh` | 下载历史或最新收益率 Excel，并更新收益率数据库 | 缺少受控的“触发更新、查询任务状态、查看更新结果”API | **优先做内部 API**。涉及外部下载和写库，不建议直接做公共 MCP。 |
| 批量新闻分析与失败兜底 | `backend/analysis/analyzer_runner.py`；`scripts/deploy/analysis_fallback_*.sh` | 支持并发、重试、强制重跑、失败统计和问题 JSON 报告 | 现有 `/internal/pipeline/trigger` 能触发部分流水线，但没有完整暴露该 Runner 的参数、进度和问题报告 | **适合内部任务 API**。应采用异步任务、幂等和管理员权限。 |
| 按新闻日期生成预测报告 | `backend/analysis/generate_report.py`；定时脚本 `scripts/deploy/report_push_*.sh` | 调用模型生成预测内容并保存预测报告 | 当前 `/forecast` 仅查询结果，没有独立的生成触发与任务状态 API | **适合内部 API**。模型成本较高，不宜直接公开。 |
| 预测报告 PDF 生成 | `backend/push/pdf_generator.py` | 从数据库读取预测报告，生成可分发 PDF | 缺少独立的“生成 PDF / 获取生成结果”API | **适合受控 API 或 MCP Resource**。需限制文件路径和下载权限。 |
| 飞书日报生成与推送 | `backend/push/feishu_daily_push.py` | 生成最新 PDF、构建摘要并推送飞书 | 缺少独立的“试运行、执行推送、查询推送结果”API | **适合内部 API**。对外推送是有副作用操作，需要审批、去重和审计。 |
| 宏观 CSV 批量导入 | `scripts/macro/import_macro_data.py` | 解析宏观数据 CSV、生成指标编码并批量入库 | 缺少文件上传、校验预览、执行导入和错误报告 API | **适合管理员 API**。必须校验文件、限制目录并支持事务回滚。 |
| 因子自动发现、相似度去重与入标准库 | `backend/factor/factor_candidate_pool.py`<br>`backend/factor/factor_similarity.py`<br>`backend/factor/factor_management.py` | 从分析结果发现新因子，计算相似度并在满足条件时加入因子库 | 目前由分析流程内部调用，没有独立的候选查询、审核、合并或新增 API | **适合管理员审核 API**。不建议让外部 MCP 自动写入标准因子库。 |
| Showcase 演示账号初始化 | `backend/demo/`、`scripts/setup_showcase_profile.py` | 初始化演示环境所需的数据或账号配置 | 缺少管理 API | **暂不做 API**。该能力目前仍是本地未提交内容，不能视为正式稳定能力。 |

## 5. 建议顺序

1. 先补三个低风险、只读 MCP Tool：按因子查新闻、快照对比、裁剪后的研报详情。
2. 再为预测报告生成、数据更新、批量分析建设统一的内部异步任务 API。
3. 最后再评估策略生成、日报生成、个人项目等有成本或用户状态的能力；这些能力需要比当前共享只读 MCP 更细的身份和权限模型。

