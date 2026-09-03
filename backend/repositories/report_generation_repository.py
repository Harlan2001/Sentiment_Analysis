"""研报生成任务与来源快照持久化。"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

from backend.repositories.base import (
    BaseRepository,
    RecycleBinMixin,
    RepositoryError,
    serialize_row,
)

# 任务统一列（list_tasks / get_task 共用）；get_task 按需追加 result_markdown
_TASK_COLUMNS = (
    "id",
    "title",
    "requirement",
    "date_start",
    "date_end",
    "report_ids_json",
    "source_snapshot_json",
    "status",
    "model_name",
    "error_message",
    "retry_count",
    "started_at",
    "finished_at",
    "created_at",
    "updated_at",
)
_TASK_SELECT = ", ".join(_TASK_COLUMNS)


class ReportGenerationNotFoundError(RepositoryError):
    """任务或研报来源不存在。"""

    status_code = 404


class ReportGenerationConflictError(RepositoryError):
    """当前任务状态不允许执行请求的操作。"""

    status_code = 409


class ReportGenerationRepository(BaseRepository, RecycleBinMixin):
    """仅负责任务持久化和读取既有研报数据。

    回收站 CRUD（soft_delete / restore / permanently_delete）继承自
    ``RecycleBinMixin``。
    """

    recycle_table = "report_generation_tasks"
    recycle_now = "NOW(6)"
    recycle_list_columns = (
        "id",
        "title",
        "requirement",
        "date_start",
        "date_end",
        "status",
        "created_at",
        "updated_at",
        "deleted_at",
    )
    recycle_in_flight = frozenset({"queued", "running"})
    recycle_not_found = ReportGenerationNotFoundError
    recycle_conflict = ReportGenerationConflictError
    recycle_not_found_msg = "研报生成任务不存在"
    recycle_in_flight_msg = "进行中的研报生成任务不能删除"
    recycle_not_in_trash_msg = "研报生成任务不存在或不在最近删除中"
    recycle_restore_miss_msg = "恢复研报生成任务后未找到记录"
    recycle_getter = "get_task"

    def list_sources(
        self,
        *,
        keyword: str | None,
        institution: str | None,
        industry: str | None,
        date_start: date | None,
        date_end: date | None,
        limit: int,
    ) -> dict[str, Any]:
        # 研报来源筛选复用 ResearchReportRepository（与 /research/list 共用一套查询/筛选面）
        from backend.repositories.research_report_repository import (
            ResearchReportRepository,
        )

        repository = ResearchReportRepository.from_environment()
        columns = (
            "id",
            "title",
            "institution",
            "publish_date",
            "industry",
            "report_type",
            "ai_summary",
            "ai_market_view",
            "ai_key_points",
            "status",
        )
        rows = repository.query_reports(
            columns=columns,
            keyword=keyword,
            keyword_columns=("title", "ai_summary"),
            institution=institution,
            industry=industry,
            status="analyzed",
            date_start=date_start,
            date_end=date_end,
            limit=limit,
        )
        return {
            "items": [serialize_row(row) for row in rows],
            "filters": repository.get_filter_facets(status="analyzed"),
        }

    def load_sources(self, report_ids: list[int]) -> list[dict[str, Any]]:
        placeholders = ",".join(["%s"] * len(report_ids))
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT id, title, institution, analyst, publish_date, industry,
                               report_type, ai_summary, ai_key_points, ai_evidence,
                               ai_market_view, ai_time_horizon, full_text, status
                          FROM research_report
                         WHERE id IN ({placeholders})""",
                    tuple(report_ids),
                )
                rows = cursor.fetchall()
        by_id = {int(row["id"]): row for row in rows}
        missing = [report_id for report_id in report_ids if report_id not in by_id]
        if missing:
            raise ReportGenerationNotFoundError(
                f"以下研报不存在：{', '.join(str(item) for item in missing)}"
            )
        unavailable = [
            report_id
            for report_id in report_ids
            if by_id[report_id].get("status") != "analyzed"
        ]
        if unavailable:
            raise ReportGenerationConflictError(
                f"以下研报尚未完成 AI 分析：{', '.join(str(item) for item in unavailable)}"
            )
        return [serialize_row(by_id[report_id]) for report_id in report_ids]

    def create_task(
        self,
        *,
        owner_username: str,
        title: str,
        requirement: str,
        date_start: date | None,
        date_end: date | None,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        report_ids = [int(source["id"]) for source in sources]
        snapshot = [
            {
                "id": source["id"],
                "title": source["title"],
                "institution": source.get("institution"),
                "publish_date": source.get("publish_date"),
                "industry": source.get("industry"),
                "report_type": source.get("report_type"),
                "ai_market_view": source.get("ai_market_view"),
            }
            for source in sources
        ]
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO report_generation_tasks (
                           id, owner_username, title, requirement, date_start, date_end,
                           report_ids_json, source_snapshot_json, status
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'queued')""",
                    (
                        task_id,
                        owner_username,
                        title,
                        requirement,
                        date_start,
                        date_end,
                        json.dumps(report_ids, ensure_ascii=False),
                        json.dumps(snapshot, ensure_ascii=False),
                    ),
                )
            conn.commit()
        task = self.get_task(owner_username, task_id)
        if not task:
            raise RuntimeError("创建研报生成任务后未找到记录")
        return task

    def list_tasks(
        self,
        owner_username: str,
        *,
        status: str | None,
        date_start: date | None,
        date_end: date | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        conditions = ["owner_username = %s", "deleted_at IS NULL"]
        params: list[Any] = [owner_username]
        if status:
            conditions.append("status = %s")
            params.append(status)
        if date_start:
            conditions.append("DATE(created_at) >= %s")
            params.append(date_start)
        if date_end:
            conditions.append("DATE(created_at) <= %s")
            params.append(date_end)
        params.append(limit)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT {_TASK_SELECT}
                          FROM report_generation_tasks
                         WHERE {' AND '.join(conditions)}
                         ORDER BY updated_at DESC, id DESC
                         LIMIT %s""",
                    tuple(params),
                )
                rows = cursor.fetchall()
        return [serialize_row(row) for row in rows]

    def get_task(
        self, owner_username: str, task_id: str, *, include_result: bool = True
    ) -> dict[str, Any] | None:
        result_column = ", result_markdown" if include_result else ""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT {_TASK_SELECT}{result_column}
                          FROM report_generation_tasks
                         WHERE id = %s AND owner_username = %s AND deleted_at IS NULL""",
                    (task_id, owner_username),
                )
                row = cursor.fetchone()
        return serialize_row(row) if row else None

    def claim_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE report_generation_tasks
                          SET status = 'running', started_at = NOW(6), finished_at = NULL,
                              error_message = NULL, updated_at = NOW(6)
                        WHERE id = %s AND status = 'queued' AND deleted_at IS NULL""",
                    (task_id,),
                )
                claimed = cursor.rowcount == 1
            conn.commit()
        if not claimed:
            return None
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT owner_username FROM report_generation_tasks WHERE id = %s",
                    (task_id,),
                )
                row = cursor.fetchone()
        return self.get_task(row["owner_username"], task_id) if row else None

    def finish_task_success(
        self, task_id: str, *, model_name: str, result_markdown: str
    ) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE report_generation_tasks
                          SET status = 'completed', model_name = %s,
                              result_markdown = %s, error_message = NULL,
                              finished_at = NOW(6), updated_at = NOW(6)
                        WHERE id = %s AND status = 'running' AND deleted_at IS NULL""",
                    (model_name, result_markdown, task_id),
                )
            conn.commit()

    def finish_task_failed(self, task_id: str, error_message: str) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE report_generation_tasks
                          SET status = 'failed', error_message = %s,
                              finished_at = NOW(6), updated_at = NOW(6)
                        WHERE id = %s AND status IN ('queued', 'running') AND deleted_at IS NULL""",
                    (error_message[:2000], task_id),
                )
            conn.commit()

    def retry_task(self, owner_username: str, task_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE report_generation_tasks
                          SET status = 'queued', result_markdown = NULL,
                              error_message = NULL, model_name = NULL,
                              retry_count = retry_count + 1,
                              started_at = NULL, finished_at = NULL, updated_at = NOW(6)
                        WHERE id = %s AND owner_username = %s AND status = 'failed' AND deleted_at IS NULL""",
                    (task_id, owner_username),
                )
                updated = cursor.rowcount == 1
            conn.commit()
        if not updated:
            task = self.get_task(owner_username, task_id)
            if not task:
                raise ReportGenerationNotFoundError("研报生成任务不存在")
            raise ReportGenerationConflictError("仅失败任务可以重试")
        task = self.get_task(owner_username, task_id)
        if not task:
            raise RuntimeError("重试任务后未找到记录")
        return task

    def mark_incomplete_failed(self) -> int:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE report_generation_tasks
                          SET status = 'failed', error_message = '服务重启导致生成中断，请重试',
                              finished_at = NOW(6), updated_at = NOW(6)
                        WHERE status IN ('queued', 'running')"""
                )
                updated = cursor.rowcount
            conn.commit()
        return updated
