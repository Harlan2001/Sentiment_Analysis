# BondSense Workbench Backend

新版工作台的独立后端服务。它只操作 `workbench_*` 表，并通过 HTTP 调用旧后端的 `/sapi/auth/status` 与 `/sapi/chat`；不导入、不修改旧 `backend/`。

## 启动

```powershell
Set-Location bondsense-workbench
$env:WORKBENCH_MYSQL_DATABASE = 'Sentiment_analysis_test'
..\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload --port 8010
```

服务会自动读取根目录 `.env` 的 `MYSQL_*`。无需复制密码；只需为新版工作台进程设置 `WORKBENCH_MYSQL_DATABASE=Sentiment_analysis_test`。数据库名不完全匹配时服务拒绝启动。启动时会仅创建 `backend/migrations/001_workbench_core.sql` 中的 `workbench_*` 表。

新服务默认监听 `http://127.0.0.1:8010`，旧 Agent 地址由 `LEGACY_API_BASE_URL` 配置。

## 第一批接口

- `GET /health`
- `GET /api/workbench/sidebar`
- `GET/POST/PATCH /api/workbench/projects`
- `GET /api/workbench/projects/{project_id}/conversations`
- `GET/POST/PATCH /api/workbench/conversations`
- `POST /api/workbench/conversations/{conversation_id}/messages`（SSE）

接口字段与行为以 `../docs/06-第一批最小接口契约.md` 为准。
