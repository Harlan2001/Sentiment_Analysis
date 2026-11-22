# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

这是面向中国债券市场的事件舆情与研究工作台：**FastAPI + MySQL + React/Vite**。新闻分析、因子与宏观信号、事件研究、新闻推荐、研报/政策/新闻总结、账号级研究组合和统一 AI 任务中心共用一套后端。另有 MCP、飞书集成及独立脚本任务；MySQL 是外部依赖，不在 Docker Compose 中启动。

- 后端入口：`main.py` → `backend.app:app`，监听 8000。
- 前端入口：`frontend/src/main.tsx`，Vite 监听 5173，将 `/sapi` 代理到 8000。
- API 前缀默认为 `/sapi`；健康检查为 `GET /health`。
- Python 固定为 3.12.x；依赖用 `uv` 和 `uv.lock` 管理。
- 前端 CI 使用 Node 24；以 CI 为准，README 中的 Node 18 要求已过时。

## 安装与本地启动

```bash
uv sync --locked
uv run playwright install chromium
npm --prefix frontend ci
npm --prefix frontend exec -- playwright install chromium
```

Windows 可在仓库根目录运行 `.\start.ps1`，它会分别启动前后端窗口并探测 `/health`。也可手动启动：

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
npm --prefix frontend run dev
```

Docker 全栈启动使用 `docker compose up --build`。Compose 包含 backend、独立 MCP 和 frontend，挂载 `data/`、`logs/`、`models/`，仍需可用的外部 MySQL 和 `.env`。

Windows 本机执行前端命令时，绝对路径使用大写盘符，例如 `D:/Project/Sentiment_Analysis/frontend`；小写盘符曾造成 Vite/Vitest 路径与缓存异常。

## 后端检查与测试

```bash
# Ruff（与 CI 相同）
uv run ruff check backend tests

# 不连接真实数据库或外部模型的测试
uv run pytest -m "not slow and not integration"

# 单个文件、单个用例
uv run pytest tests/unit/test_openapi_snapshot.py
uv run pytest tests/unit/test_openapi_snapshot.py::test_openapi_contract_snapshot

# CI 覆盖率形式；PR 后端增量覆盖率门槛为 60%
uv run pytest -m "not slow and not integration" --cov=backend --cov-report=term-missing:skip-covered --cov-report=xml

# 锁文件检查
uv lock --check
```

有意的 API 结构变更需要审查并更新 OpenAPI 快照：

```bash
# Bash
UPDATE_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_snapshot.py

# PowerShell
$env:UPDATE_SNAPSHOT=1; uv run pytest tests/unit/test_openapi_snapshot.py; Remove-Item Env:UPDATE_SNAPSHOT
```

随后正常运行该测试，确认 `tests/snapshots/openapi.json` 只包含预期差异。

## 前端检查与测试

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run test:coverage
npm --prefix frontend run build

# 单个 Vitest 文件
npm --prefix frontend run test -- src/features/market/pages/PortfolioPage.test.tsx

# 单个 Playwright 文件
npm --prefix frontend run e2e -- e2e/tests/portfolio.spec.ts
```

Vitest 使用 jsdom 和 MSW；组件测试优先复用 `frontend/src/test/render.tsx` 的 `renderWithProviders`，它封装 QueryClient、Router 和可选 AuthProvider。Playwright 配置会自动拉起 mock LLM(8080)、后端(8000)和前端(5173)，并且 `reuseExistingServer=true`：运行前确认这些端口没有指向其他工作区的服务。

## 测试库、集成测试与 E2E

`backend/config/config.py` 使用 `load_dotenv(..., override=True)`，因此仓库 `.env` 会覆盖进程中的 `MYSQL_*`。运行集成测试前必须显式确认目标连接和数据库，不要依赖临时导出的变量一定优先于 `.env`。

```bash
# 同时显式设置 MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD
export MYSQL_TEST_DATABASE=Sentiment_analysis_test

# 注意：会重建该测试库；脚本强制要求库名以 _test 结尾
uv run python scripts/migrate_test_db.py

uv run pytest tests/integration -m integration -q
uv run pytest tests/integration/test_portfolio_db.py -m integration -q
```

未设置 `MYSQL_TEST_DATABASE` 时集成测试会 skip；这不是通过。`tests/integration/conftest.py` 在导入后端配置前缓存显式 MySQL 连接，并使用该连接初始化测试连接池。

完整 E2E 与 CI 使用同一测试库和 mock LLM：

```bash
export MYSQL_DATABASE=Sentiment_analysis_test
export MYSQL_TEST_DATABASE=Sentiment_analysis_test
export LLM_API_KEY=ci-dummy-key
export LLM_BASE_URL=http://127.0.0.1:8080/v1
export OUTBOUND_PROXY_ENABLED=false
export AUTH_ENABLED=false
uv run python scripts/migrate_test_db.py
npm --prefix frontend run e2e
```

## 后端架构

### 应用与 API

- `main.py` 只导出 `backend.app:app`；`backend/app.py` 显式注册各 `backend/routers/` 路由，并处理启动/关闭生命周期。
- 新路由的成功响应使用 `backend.common.api_response.ok()`，返回 `{"data": payload}`。部分旧接口仍有历史响应壳，修改时先核对现有调用方。
- `backend/auth/dependencies.py` 在 `request.state` 写入 username/admin/role。匿名访客只读 GET/HEAD/OPTIONS；写操作需要认证或内部服务 token。`AUTH_ENABLED=false` 时全部归入 admin，主要用于测试，不能据此省略归属校验。
- `frontend/src/api/client.ts` 的 `request()` 自动携带 JWT、处理错误并解包 `data`；Blob/SSE 不走该封装，要显式携带认证头。

### MySQL 与事务

项目没有 ORM，业务 SQL 使用 PyMySQL。`backend/common/database.py` 维护两种连接池：

1. 主池：tuple 游标，供旧查询和 `execute_query/execute_update` 使用；更新与批量写入通过对应 helper 显式提交。
2. 仓储池：DictCursor、`autocommit=False`，供 `backend/repositories/` 使用，写方法必须显式 `commit()`。

`BaseRepository._connection()` 在异常时 rollback；`serialize_row()` 负责日期和 `*_json` 字段转换。路由可通过 `RepositoryError.status_code` 和 `workbench_helpers.raise_repository_error` 复用错误映射。多表写入、任务终态与执行日志需要保持同一事务，不要拆成独立连接提交。

### 新闻、因子与推荐数据流

- `news` 由外部数据链路写入；`backend/analysis/` 调用模型生成 `analysis` 和 `news_factor`，不是 FastAPI 启动时自动全量产生。
- `backend/factor/`、`backend/macrosignal/`、`backend/evaluation/` 分别处理因子、宏观信号和离线事件研究。很多结果由 `scripts/` 定时或批量生成，不能把离线结果误认为实时重算。
- `backend/recommend/` 将可解释静态分幂等写入 `news_importance_score`；`analyzer_runner` 增量打分，`scripts/recompute_news_importance.py` 全量/窗口回算，查询时再应用时间衰减。
- 因子回测与信号必须固定单一 model，时间锚点只能使用 `news_factor.pub_time`，不能用分析落库时间 `created_at`。方向是中国国债口径：positive 表示利多债券、收益率下行。

### 统一 AI 任务中心

`backend/task_execution/` 是四类 AI 工作流共用的执行层：研报解析、政策文件、综合研报和每日新闻总结。

- 各领域表仍是唯一业务状态来源，不另建双写任务表。`queue.py` 的 `SPECS` 描述领域状态、所有者、错误字段和重试清理规则。
- `dispatcher.py` 随 FastAPI 启停，使用 MySQL 原子 claim、租约、心跳和有界 executor；不要恢复“每个排队任务一个线程/协程”的模式。
- queued/pending 重启后继续；无租约或租约过期的 running/processing/analyzing 标记“服务中断”，由用户人工重试，不自动重跑 LLM。
- 成功结果、领域终态和 `task_runs/task_events` 必须校验同一 lease token 并在同一事务提交，防止旧 worker 覆盖重试结果。
- `backend/repositories/ai_task_repository.py` 是统一只读聚合；`backend/routers/workbench_computer.py` 提供筛选、详情和重试。策略历史在这里只读，不属于该执行器。

### 其他业务边界

- 文档工作流分别位于 `research_report/`、`report/`、`policy_document/`、`news_summary/`，其路由只负责入队、查询、重试和导出。
- `backend/portfolio/` 提供纯 Decimal 的组合指标；`portfolio_repository.py` 用父组合行锁和 version 处理权重与并发。组合是研究配置，不包含实时估值、交易或真实收益。
- `file_library` 从现有业务表聚合文件，不复制文件内容；`mcp_server/`、`business_mcp/` 和 `integrations/feishu/` 是独立集成边界。

## 前端架构

- `frontend/src/config/routes.ts` 是纯路由元数据；`frontend/src/routes.tsx` 另存 React 元素映射和 `LOGIN_REQUIRED_ROUTES`。新增或修改路由时必须同步这些位置，缺少元素映射的路径会静默落入 `/market`。
- `features/market/` 包含新闻、因子、收益、预测、关注、组合等市场页面；`features/workflow/` 包含文档工作流和统一任务中心。
- 服务端状态主要用 React Query；请求集中在 `src/api/`，通用认证与错误处理集中在 `api/client.ts`。
- `WorkflowHomePage` 只提供模块入口；实际任务逻辑位于 `features/workflow/components/tasks/`，不要另建一套任务轮询或状态模型。

## Schema 与交付检查

- `sql/schema_full.sql` 是测试库结构的权威快照。新增结构变更需有 `NNN_*.sql` 迁移并同步该快照，生产执行与快照重导是独立、需明确授权的操作。
- `migrate_test_db.py` 只重建结构，不执行 `012_workbench_system_skills_v2.sql` 和 `013_workbench_system_skills_research_suite.sql` 的系统技能数据脚本。
- CI 包含 backend、frontend、backend-integration、e2e、security 五类检查。除上述测试外，还检查后端增量覆盖率、`uv.lock`、pip-audit、npm audit 和 gitleaks。
