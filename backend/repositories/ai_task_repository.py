"""统一工作台任务读模型；不复制领域状态。"""

from __future__ import annotations

from datetime import date
from typing import Any

from backend.common.pagination import paginated_payload
from backend.repositories.base import BaseRepository, serialize_row
from backend.task_execution.queue import AITaskQueue

TASK_TYPES = (
    "research_report",
    "policy_document",
    "report_generation",
    "daily_news",
    "strategy",
)

# 每个 SELECT 都先限定 owner，外层筛选不会把其他用户记录带入分页或统计。
_UNION_SQL = """
SELECT CONVERT(CAST(id AS CHAR) USING utf8mb4) COLLATE utf8mb4_unicode_ci AS domain_id,
       CONVERT('research_report' USING utf8mb4) COLLATE utf8mb4_unicode_ci AS task_type,
       CONVERT(CASE WHEN uploaded_by IS NULL OR uploaded_by IN ('', 'web') THEN 'admin' ELSE uploaded_by END USING utf8mb4) COLLATE utf8mb4_unicode_ci AS owner_username,
       CONVERT(title USING utf8mb4) COLLATE utf8mb4_unicode_ci AS title,
       CONVERT(COALESCE(institution, '用户上传') USING utf8mb4) COLLATE utf8mb4_unicode_ci AS description,
       CONVERT('研报解析' USING utf8mb4) COLLATE utf8mb4_unicode_ci AS module,
       CONVERT('研报分析' USING utf8mb4) COLLATE utf8mb4_unicode_ci AS source,
       CONVERT(status USING utf8mb4) COLLATE utf8mb4_unicode_ci AS domain_status,
       CONVERT(CASE WHEN status='queued' THEN 'queued'
            WHEN status IN ('processing','analyzing') THEN 'running'
            WHEN status='analyzed' THEN 'succeeded'
            WHEN status='failed' THEN 'failed' ELSE 'pending' END USING utf8mb4) COLLATE utf8mb4_unicode_ci AS status,
       CONVERT(stage USING utf8mb4) COLLATE utf8mb4_unicode_ci AS stage,
       CONVERT(parse_error USING utf8mb4) COLLATE utf8mb4_unicode_ci AS error_message,
       COALESCE(retry_count,0) AS retry_count, DATE(created_at) AS task_date, created_at, updated_at
  FROM research_report
 WHERE CASE WHEN uploaded_by IS NULL OR uploaded_by IN ('', 'web') THEN 'admin' ELSE uploaded_by END = %s
UNION ALL
SELECT CONVERT(CAST(id AS CHAR) USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT('policy_document' USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(owner_username USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(title USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(COALESCE(focus_title, issuer, '政策文件解读') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT('政策文件分析' USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT('政策文件分析' USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(status USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(CASE WHEN status='queued' THEN 'queued' WHEN status='analyzing' THEN 'running'
            WHEN status='completed' THEN 'succeeded' WHEN status='failed' THEN 'failed' ELSE 'pending' END USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(stage USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(error_message USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       retry_count, COALESCE(publish_date, DATE(created_at)), created_at, updated_at
  FROM policy_document WHERE owner_username = %s
UNION ALL
SELECT CONVERT(id USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT('report_generation' USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(owner_username USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(title USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(requirement USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT('综合研报' USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT('研报分析' USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(status USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(CASE WHEN status='queued' THEN 'queued' WHEN status='running' THEN 'running'
            WHEN status='completed' THEN 'succeeded' WHEN status='failed' THEN 'failed' ELSE 'pending' END USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(stage USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(error_message USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       retry_count, COALESCE(date_start, DATE(created_at)), created_at, updated_at
  FROM report_generation_tasks WHERE owner_username = %s AND deleted_at IS NULL
UNION ALL
SELECT CONVERT(CAST(id AS CHAR) USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT('daily_news' USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(owner_username USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(CONCAT(start_date, ' 至 ', end_date, ' 新闻总结') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(COALESCE(focus, '按日期与来源聚合新闻') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT('每日新闻总结' USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT('新闻总结' USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(status USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(CASE WHEN status='pending' THEN 'queued' WHEN status='running' THEN 'running'
            WHEN status='succeeded' THEN 'succeeded' WHEN status='failed' THEN 'failed'
            WHEN status='empty' THEN 'empty' ELSE 'pending' END USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(stage USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(error_message USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       retry_count, start_date, created_at, updated_at
  FROM daily_news_summary_tasks WHERE owner_username = %s AND deleted_at IS NULL
UNION ALL
SELECT CONVERT(CAST(id AS CHAR) USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT('strategy' USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(owner_username USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(title USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(IF(current_local_version_no > 0, '历史策略结果（只读）', '提示词草稿等待确认') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT('策略生成' USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT('策略生成' USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(status USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CONVERT(IF(current_local_version_no > 0, 'succeeded', 'pending_confirmation') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
       CAST(NULL AS CHAR) COLLATE utf8mb4_unicode_ci,
       CAST(NULL AS CHAR) COLLATE utf8mb4_unicode_ci,
       0, DATE(COALESCE(last_message_at, created_at)), created_at,
       COALESCE(last_message_at, updated_at)
  FROM ai_strategy_conversations WHERE owner_username = %s AND deleted_at IS NULL
"""

_STATUS_LABELS = {
    "queued": "排队中",
    "running": "执行中",
    "succeeded": "已完成",
    "failed": "失败",
    "empty": "无新闻",
    "pending": "待处理",
    "pending_confirmation": "待确认",
}
_STAGE_LABELS = {
    "queued": "排队等待",
    "loading": "读取输入",
    "analyzing": "AI 分析中",
    "generating": "生成内容",
    "summarizing": "分批总结",
    "merging": "合并总结",
    "saving": "保存结果",
    "succeeded": "已完成",
    "empty": "无新闻",
    "failed": "执行失败",
}


def _result_url(task_type: str, domain_id: str) -> str:
    if task_type == "research_report":
        return f"/computer/reports/library?reportId={domain_id}"
    if task_type == "policy_document":
        return f"/computer/policy/{domain_id}"
    if task_type == "report_generation":
        return f"/computer/reports/{domain_id}"
    if task_type == "daily_news":
        return f"/computer/news/{domain_id}"
    return f"/strategy/prompt?id={domain_id}"


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    task_type = str(row["task_type"])
    domain_id = str(row["domain_id"])
    status = str(row["status"])
    result_url = _result_url(task_type, domain_id)
    stage = row.get("stage")
    return {
        "task_id": f"{task_type}:{domain_id}",
        "domain_id": domain_id,
        "task_type": task_type,
        "module": row["module"],
        "title": row["title"] or "未命名任务",
        "description": str(row.get("description") or "")[:500],
        "source": row["source"],
        "result": "查看结果" if status in {"succeeded", "empty"} else "—",
        "status": status,
        "domain_status": row["domain_status"],
        "status_label": _STATUS_LABELS.get(status, status),
        "stage": stage,
        "stage_label": _STAGE_LABELS.get(stage, stage),
        "error_message": row.get("error_message"),
        "retry_count": int(row.get("retry_count") or 0),
        "date": row.get("task_date"),
        "updated_at": row.get("updated_at") or row.get("created_at"),
        "needs_action": status in {"failed", "pending_confirmation"},
        "result_url": result_url,
    }


class AITaskRepository(BaseRepository):
    def list_tasks(
        self,
        owner_username: str,
        *,
        task_type: str | None = None,
        status: str | None = None,
        selected_date: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        base = f"FROM ({_UNION_SQL}) task_items"
        base_params: list[Any] = [owner_username] * 5
        conditions: list[str] = []
        params = list(base_params)
        if task_type:
            conditions.append("task_type = %s")
            params.append(task_type)
        if selected_date:
            conditions.append("task_date = %s")
            params.append(selected_date)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        filtered_params = list(params)
        if status:
            conditions.append("status = %s")
            params.append(status)
        filtered_where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT COUNT(*) AS total {base} {filtered_where}", tuple(params)
                )
                total = int(cursor.fetchone()["total"] or 0)
                cursor.execute(
                    f"SELECT task_type, status, COUNT(*) AS count {base} {where} GROUP BY task_type, status",
                    tuple(filtered_params),
                )
                count_rows = list(cursor.fetchall())
                cursor.execute(
                    f"""SELECT * {base} {filtered_where}
                         ORDER BY updated_at DESC, task_type, domain_id DESC
                         LIMIT %s OFFSET %s""",
                    (*params, page_size, (page - 1) * page_size),
                )
                rows = [serialize_row(row) or {} for row in cursor.fetchall()]
        totals = {task_type_name: 0 for task_type_name in TASK_TYPES}
        status_counts: dict[str, int] = {}
        for row in count_rows:
            count = int(row["count"])
            totals[row["task_type"]] = count
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + count
        payload = paginated_payload(
            [_normalize(row) for row in rows], total, page, page_size
        )
        payload.update({"totals": {**totals, "total": sum(totals.values())}, "status_counts": status_counts})
        return payload

    def get_task(self, owner_username: str, task_type: str, domain_id: str) -> dict[str, Any]:
        result = self.list_tasks(owner_username, task_type=task_type, page_size=100)
        for item in result["items"]:
            if item["domain_id"] == str(domain_id):
                return item
        # 第二页及更旧任务仍需可直接定位，不受首页限制。
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT * FROM ({_UNION_SQL}) task_items WHERE task_type=%s AND domain_id=%s",
                    (*([owner_username] * 5), task_type, str(domain_id)),
                )
                row = serialize_row(cursor.fetchone())
        if not row:
            from backend.task_execution.queue import TaskNotFoundError

            raise TaskNotFoundError("任务不存在或当前用户无权访问")
        return _normalize(row)

    def get_execution_detail(
        self, owner_username: str, task_type: str, domain_id: str
    ) -> dict[str, Any]:
        task = self.get_task(owner_username, task_type, domain_id)
        if task_type == "strategy":
            return {"task": task, "execution": None, "items": []}
        # 策略之外的执行日志必须先通过领域归属检查。
        AITaskQueue.from_environment().get_owned_task(task_type, domain_id, owner_username)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT id, status, error_message, started_at, finished_at
                         FROM task_runs
                        WHERE idempotency_key LIKE %s
                        ORDER BY id DESC LIMIT 1""",
                    (f"ai-task:{task_type}:{domain_id}:%",),
                )
                run = serialize_row(cursor.fetchone())
                events = []
                if run:
                    cursor.execute(
                        """SELECT id, event_type, status, message, created_at
                             FROM task_events WHERE task_run_id=%s ORDER BY id""",
                        (run["id"],),
                    )
                    events = [serialize_row(row) or {} for row in cursor.fetchall()]
        return {"task": task, "execution": run, "items": events}
