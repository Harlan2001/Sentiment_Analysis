# AI 策略生成模块：部署与验证

本模块提供“提示词草稿 → 用户确认 → DreamStrategy 生成 → 策略版本与回测展示”的流程。

## 1. 前置条件

- Python 3.11 或更高版本；项目依赖由 `uv.lock` 锁定。
- Node.js 20 或更高版本；前端依赖由 `frontend/package-lock.json` 锁定。
- 可访问的业务 MySQL、独立 AI 策略历史 MySQL，以及 DreamStrategy 服务（仅确认生成阶段需要）。
- 历史库的数据库账号必须有建表/读写权限；业务库账号至少应能读取用户、新闻、分析、因子和收益率数据。

## 2. 环境变量

1. 复制 `.env.example` 为 `.env`。
2. 从部署负责人或密钥管理系统取得真实值；不要将 `.env`、密码、JWT 密钥或 Dream 地址写入 Git、日志或截图。
3. `MYSQL_DATABASE` 是现有业务库；`AI_STRATEGY_HISTORY_MYSQL_DATABASE` 必须是不同的独立 schema。
4. 共享环境应设置 `AUTH_ENABLED=true`，并为 `JWT_SECRET_KEY` 配置随机密钥。

`DREAM_PORTAL_CONFIG_URL` 和 `DREAM_TEMPLATE_ID` 缺失时，用户仍可创建提示词草稿；点击“确认发送并生成策略”会返回明确配置错误，且不会产生策略版本。

## 3. 数据库迁移

所有 AI 策略历史迁移都只能在 `AI_STRATEGY_HISTORY_MYSQL_DATABASE` 执行，禁止在业务库执行。

### 新建空历史库

执行基础迁移一次：

```powershell
uv run python scripts/apply_ai_strategy_history_migration.py
```

它会创建 `ai_strategy_conversations`、`ai_strategy_messages`、`ai_strategy_versions` 三张表，已包含提示词快照与回测指标字段。脚本会拒绝把历史迁移执行到 `MYSQL_DATABASE`。

### 已部署早期历史库

仅当目标历史库缺少相应字段时，按顺序人工执行：

1. `migrations/20260729_ai_strategy_prompt_snapshot_up.sql`
2. `migrations/20260729_ai_strategy_backtest_metrics_up.sql`

不要对已拥有这些字段的库重复执行增量 SQL。旧会话数据不会迁移或写入业务库。

## 4. 安装与启动

```powershell
uv sync
Set-Location frontend
npm ci
Set-Location ..
uv run uvicorn main:app --host 127.0.0.1 --port 8010
```

另开一个终端启动前端：

```powershell
Set-Location frontend
npm run dev
```

开发环境的 Vite 将 `/api` 转发至 `http://127.0.0.1:8010`。生产部署应由反向代理将同源 `/api` 转发到后端，不应把开发机的 `127.0.0.1` 配置用于生产。

## 5. 核心接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/ai-strategy-generation/conversations` | 创建会话 |
| GET | `/api/ai-strategy-generation/conversations` | 获取当前用户会话列表 |
| GET | `/api/ai-strategy-generation/conversations/{id}` | 获取会话、消息与版本 |
| POST | `/api/ai-strategy-generation/conversations/{id}/draft` | 构建并保存提示词草稿，不调用 DreamStrategy |
| POST | `/api/ai-strategy-generation/conversations/{id}/drafts/{messageId}/confirm` | 保存最终提示词并调用 DreamStrategy |
| PATCH | `/api/ai-strategy-generation/conversations/{id}/archive` | 归档当前用户会话 |

当 `AUTH_ENABLED=true` 时，所有策略会话接口从 JWT 获取 `owner_username`，并按该值隔离数据。

## 6. 最小验证

1. 打开 `http://127.0.0.1:5173` 并使用测试账号登录。
2. 创建会话并发送策略需求：右侧应出现可编辑提示词和新闻引用；此时 DreamStrategy 不应被调用。
3. 修改提示词可编辑区后确认发送：页面应显示“正在生成策略与回测结果，请稍候”。
4. 完成后确认页面展示策略版本、新闻引用、代码、回测摘要和回测指标。
5. 使用第二个账号确认：列表不显示第一个账号的会话，直接访问其会话 URL 应返回 404。

## 7. 提交边界

提交代码、迁移、`.env.example`、本文件、`pyproject.toml` 与 `uv.lock`；不要提交 `.env`、业务/历史库数据、测试账号、运行日志或 `__pycache__`。