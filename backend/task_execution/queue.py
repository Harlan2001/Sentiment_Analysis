"""四类 AI 任务共用的 MySQL 队列、租约与执行日志。

领域表仍是唯一业务状态来源。本模块只统一排队、竞争、心跳、失败恢复和重试，
成功终态由各领域仓储与业务结果在同一事务内写入。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from backend.common.task_logging import add_task_event, finish_task_run, start_task_run
from backend.repositories.base import BaseRepository, RepositoryError, serialize_row


class TaskNotFoundError(RepositoryError):
    status_code = 404


class TaskConflictError(RepositoryError):
    status_code = 409


@dataclass(frozen=True)
class TaskSpec:
    table: str
    queued: str
    running: str
    error_column: str = "error_message"
    owner_expression: str = "owner_username"
    not_deleted: str = "1=1"
    clear_on_retry: str = ""
    claim_extra: str = ""
    failure_extra: str = ""


@dataclass(frozen=True)
class TaskHandle:
    task_type: str
    domain_id: str
    owner_username: str
    lease_token: str
    run_id: int
    requested_model: str | None = None


SPECS = {
    "research_report": TaskSpec(
        table="research_report",
        queued="queued",
        running="processing",
        error_column="parse_error",
        owner_expression=(
            "CASE WHEN uploaded_by IS NULL OR uploaded_by IN ('', 'web') "
            "THEN 'admin' ELSE uploaded_by END"
        ),
    ),
    "policy_document": TaskSpec(
        table="policy_document", queued="queued", running="analyzing"
    ),
    "report_generation": TaskSpec(
        table="report_generation_tasks",
        queued="queued",
        running="running",
        not_deleted="deleted_at IS NULL",
        clear_on_retry=(
            "result_markdown = NULL, model_name = NULL, "
            "started_at = NULL, finished_at = NULL"
        ),
        claim_extra="started_at = CURRENT_TIMESTAMP(6), finished_at = NULL",
        failure_extra="finished_at = CURRENT_TIMESTAMP(6)",
    ),
    "daily_news": TaskSpec(
        table="daily_news_summary_tasks",
        queued="pending",
        running="running",
        not_deleted="deleted_at IS NULL",
        clear_on_retry=(
            "summary = NULL, references_json = NULL, source_stats_json = NULL, "
            "news_count = 0, started_at = NULL, completed_at = NULL"
        ),
        claim_extra="started_at = CURRENT_TIMESTAMP(6), completed_at = NULL",
        failure_extra="completed_at = CURRENT_TIMESTAMP(6)",
    ),
}

_QUEUE_COLUMNS = (
    "queued_at = CURRENT_TIMESTAMP(6), stage = 'queued', lease_token = NULL, "
    "lease_expires_at = NULL, active_run_id = NULL"
)


def _spec(task_type: str) -> TaskSpec:
    try:
        return SPECS[task_type]
    except KeyError as exc:
        raise TaskNotFoundError("不支持的任务类型") from exc


class AITaskQueue(BaseRepository):
    """以原子 UPDATE 竞争任务；调用方无需持有数据库锁等待 LLM。"""

    def enqueue(
        self,
        task_type: str,
        domain_id: int | str,
        *,
        allowed_statuses: tuple[str, ...],
        requested_model: str | None = None,
    ) -> bool:
        spec = _spec(task_type)
        placeholders = ",".join(["%s"] * len(allowed_statuses))
        model_sql = ", requested_model = %s" if requested_model is not None else ""
        params: list[Any] = [spec.queued]
        if requested_model is not None:
            params.append(requested_model)
        params.extend([domain_id, *allowed_statuses])
        with self._connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(
                    f"""UPDATE {spec.table}
                           SET status = %s, {_QUEUE_COLUMNS},
                               {spec.error_column} = NULL{model_sql}
                         WHERE id = %s AND status IN ({placeholders})
                           AND {spec.not_deleted}""",
                    tuple(params),
                )
            conn.commit()
        return affected == 1

    def list_queued(self, *, per_type_limit: int = 100) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        with self._connection() as conn:
            with conn.cursor() as cursor:
                for task_type, spec in SPECS.items():
                    cursor.execute(
                        f"""SELECT id FROM {spec.table}
                             WHERE status = %s AND {spec.not_deleted}
                             ORDER BY COALESCE(queued_at, created_at), id
                             LIMIT %s""",
                        (spec.queued, per_type_limit),
                    )
                    result.extend((task_type, str(row["id"])) for row in cursor.fetchall())
        return result

    def claim(
        self, task_type: str, domain_id: int | str, *, lease_seconds: int
    ) -> TaskHandle | None:
        spec = _spec(task_type)
        token = str(uuid.uuid4())
        claim_sql = f", {spec.claim_extra}" if spec.claim_extra else ""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                claimed = cursor.execute(
                    f"""UPDATE {spec.table}
                           SET status = %s, stage = 'loading', lease_token = %s,
                               lease_expires_at = DATE_ADD(NOW(6), INTERVAL %s SECOND),
                               active_run_id = NULL, {spec.error_column} = NULL{claim_sql}
                         WHERE id = %s AND status = %s AND {spec.not_deleted}""",
                    (spec.running, token, lease_seconds, domain_id, spec.queued),
                )
                if claimed != 1:
                    conn.rollback()
                    return None
                cursor.execute(
                    f"""SELECT {spec.owner_expression} AS owner_username,
                               active_run_id
                          FROM {spec.table} WHERE id = %s""",
                    (domain_id,),
                )
                row = cursor.fetchone()
                owner = str(row["owner_username"])
                run_id = start_task_run(
                    conn,
                    task_name=f"{task_type}:{domain_id}",
                    task_type="ai_task",
                    idempotency_key=f"ai-task:{task_type}:{domain_id}:{token}",
                    payload={"task_type": task_type, "domain_id": str(domain_id), "owner": owner},
                )
                cursor.execute(
                    f"UPDATE {spec.table} SET active_run_id = %s WHERE id = %s AND lease_token = %s",
                    (run_id, domain_id, token),
                )
                requested_model = None
                if task_type in {"research_report", "report_generation"}:
                    cursor.execute(
                        f"SELECT requested_model FROM {spec.table} WHERE id = %s",
                        (domain_id,),
                    )
                    requested_model = cursor.fetchone().get("requested_model")
                add_task_event(conn, run_id, "queued", "任务已领取，准备执行", status="running")
            conn.commit()
        return TaskHandle(
            task_type=task_type,
            domain_id=str(domain_id),
            owner_username=owner,
            lease_token=token,
            run_id=int(run_id),
            requested_model=requested_model,
        )

    def heartbeat(self, handle: TaskHandle, *, lease_seconds: int) -> bool:
        spec = _spec(handle.task_type)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(
                    f"""UPDATE {spec.table}
                           SET lease_expires_at = DATE_ADD(NOW(6), INTERVAL %s SECOND)
                         WHERE id = %s AND lease_token = %s AND status = %s""",
                    (lease_seconds, handle.domain_id, handle.lease_token, spec.running),
                )
            conn.commit()
        return affected == 1

    def update_stage(self, handle: TaskHandle, stage: str, message: str) -> None:
        spec = _spec(handle.task_type)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(
                    f"""UPDATE {spec.table} SET stage = %s
                         WHERE id = %s AND lease_token = %s AND status = %s""",
                    (stage, handle.domain_id, handle.lease_token, spec.running),
                )
                if affected != 1:
                    conn.rollback()
                    return
                add_task_event(conn, handle.run_id, stage, message, status="running")
            conn.commit()

    def fail(self, handle: TaskHandle, message: str) -> bool:
        """只有当前租约能把任务标为失败，执行日志在同一事务内结束。"""
        spec = _spec(handle.task_type)
        error_limit = 500 if handle.task_type in {"research_report", "policy_document"} else 1000
        message = message[:error_limit]
        failure_sql = f", {spec.failure_extra}" if spec.failure_extra else ""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(
                    f"""UPDATE {spec.table}
                           SET status = 'failed', {spec.error_column} = %s,
                               stage = 'failed', lease_token = NULL,
                               lease_expires_at = NULL, active_run_id = NULL{failure_sql}
                         WHERE id = %s AND lease_token = %s AND status = %s""",
                    (message, handle.domain_id, handle.lease_token, spec.running),
                )
                if affected == 1:
                    finish_task_run(
                        conn, handle.run_id, "failed", error_message=message[:2000]
                    )
                    add_task_event(
                        conn, handle.run_id, "failed", message[:2000], status="failed"
                    )
            conn.commit()
        return affected == 1

    def recover_interrupted(self) -> int:
        """回收无租约遗留任务和已过期任务；queued/pending 一律保留。"""
        recovered = 0
        with self._connection() as conn:
            with conn.cursor() as cursor:
                for task_type, spec in SPECS.items():
                    cursor.execute(
                        f"""SELECT id, active_run_id FROM {spec.table}
                             WHERE status IN (%s, %s)
                               AND (lease_token IS NULL OR lease_expires_at <= NOW(6))""",
                        (spec.running, "analyzing" if task_type == "research_report" else spec.running),
                    )
                    rows = list(cursor.fetchall())
                    failure_sql = f", {spec.failure_extra}" if spec.failure_extra else ""
                    for row in rows:
                        affected = cursor.execute(
                            f"""UPDATE {spec.table}
                                   SET status = 'failed', {spec.error_column} = '服务中断，请确认后重试',
                                       stage = 'failed', lease_token = NULL,
                                       lease_expires_at = NULL, active_run_id = NULL{failure_sql}
                                 WHERE id = %s AND status IN (%s, %s)
                                   AND (lease_token IS NULL OR lease_expires_at <= NOW(6))""",
                            (row["id"], spec.running, "analyzing" if task_type == "research_report" else spec.running),
                        )
                        if affected == 1:
                            recovered += 1
                            if row.get("active_run_id"):
                                finish_task_run(
                                    conn,
                                    int(row["active_run_id"]),
                                    "failed",
                                    error_message="服务中断，请确认后重试",
                                )
            conn.commit()
        return recovered

    def retry(self, task_type: str, domain_id: str, owner_username: str) -> None:
        spec = _spec(task_type)
        allowed = ("failed", "empty") if task_type == "daily_news" else ("failed",)
        placeholders = ",".join(["%s"] * len(allowed))
        clear_sql = f", {spec.clear_on_retry}" if spec.clear_on_retry else ""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT status FROM {spec.table}
                         WHERE id = %s AND {spec.owner_expression} = %s
                           AND {spec.not_deleted}""",
                    (domain_id, owner_username),
                )
                if not cursor.fetchone():
                    raise TaskNotFoundError("任务不存在或当前用户无权访问")
                affected = cursor.execute(
                    f"""UPDATE {spec.table}
                           SET status = %s, {_QUEUE_COLUMNS}, {spec.error_column} = NULL,
                               retry_count = COALESCE(retry_count, 0) + 1{clear_sql}
                         WHERE id = %s AND {spec.owner_expression} = %s
                           AND status IN ({placeholders}) AND {spec.not_deleted}""",
                    (spec.queued, domain_id, owner_username, *allowed),
                )
                if affected != 1:
                    raise TaskConflictError("只有失败任务可以重试")
            conn.commit()

    def get_owned_task(
        self, task_type: str, domain_id: str, owner_username: str
    ) -> dict[str, Any]:
        spec = _spec(task_type)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT * FROM {spec.table}
                         WHERE id = %s AND {spec.owner_expression} = %s
                           AND {spec.not_deleted}""",
                    (domain_id, owner_username),
                )
                row = serialize_row(cursor.fetchone())
        if not row:
            raise TaskNotFoundError("任务不存在或当前用户无权访问")
        return row
