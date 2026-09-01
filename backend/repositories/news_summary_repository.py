"""每日新闻总结任务持久化，复用项目业务库连接配置。"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from backend.repositories.base import BaseRepository, json_default, serialize_row


class DailyNewsSummaryNotFoundError(RuntimeError):
    """任务不存在或不属于当前用户。"""


class DailyNewsSummaryRepository(BaseRepository):

    def create_task(
        self,
        owner_username: str,
        start_date: date,
        end_date: date,
        sources: list[str],
        focus: str,
        retry_of_id: int | None = None,
    ) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO daily_news_summary_tasks
                       (owner_username, start_date, end_date, sources_json, focus, retry_of_id)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        owner_username,
                        start_date,
                        end_date,
                        json.dumps(sources, ensure_ascii=False),
                        focus or None,
                        retry_of_id,
                    ),
                )
                task_id = int(cursor.lastrowid)
            conn.commit()
        task = self.get_task(owner_username, task_id)
        if not task:
            raise RuntimeError("创建新闻总结任务后未找到记录")
        return task

    def list_tasks(self, owner_username: str, limit: int) -> list[dict[str, Any]]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT * FROM daily_news_summary_tasks
                       WHERE owner_username = %s AND deleted_at IS NULL
                       ORDER BY updated_at DESC, id DESC LIMIT %s""",
                    (owner_username, limit),
                )
                rows = cursor.fetchall()
        return [serialize_row(row) or {} for row in rows]

    def get_task(self, owner_username: str, task_id: int) -> dict[str, Any] | None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM daily_news_summary_tasks WHERE id = %s AND owner_username = %s AND deleted_at IS NULL",
                    (task_id, owner_username),
                )
                row = cursor.fetchone()
        return serialize_row(row)

    def mark_running(self, owner_username: str, task_id: int) -> bool:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(
                    """UPDATE daily_news_summary_tasks
                       SET status = 'running', started_at = CURRENT_TIMESTAMP(6), error_message = NULL
                       WHERE id = %s AND owner_username = %s AND status = 'pending' AND deleted_at IS NULL""",
                    (task_id, owner_username),
                )
            conn.commit()
        return bool(affected)

    def complete_task(
        self,
        owner_username: str,
        task_id: int,
        *,
        status: str,
        news_count: int,
        source_stats: dict[str, int],
        summary: str,
        references: list[dict[str, Any]],
    ) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(
                    """UPDATE daily_news_summary_tasks
                       SET status = %s, news_count = %s, source_stats_json = %s,
                           summary = %s, references_json = %s, error_message = NULL,
                           completed_at = CURRENT_TIMESTAMP(6)
                       WHERE id = %s AND owner_username = %s AND status = 'running' AND deleted_at IS NULL""",
                    (
                        status,
                        news_count,
                        json.dumps(source_stats, ensure_ascii=False),
                        summary,
                        json.dumps(references, ensure_ascii=False, default=json_default),
                        task_id,
                        owner_username,
                    ),
                )
            conn.commit()
        if not affected:
            raise DailyNewsSummaryNotFoundError("新闻总结任务已不存在或状态已变化")

    def fail_task(self, owner_username: str, task_id: int, message: str) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE daily_news_summary_tasks
                       SET status = 'failed', error_message = %s, completed_at = CURRENT_TIMESTAMP(6)
                       WHERE id = %s AND owner_username = %s AND status IN ('pending', 'running') AND deleted_at IS NULL""",
                    (message[:1000], task_id, owner_username),
                )
            conn.commit()

    def mark_interrupted_tasks_failed(self) -> int:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(
                    """UPDATE daily_news_summary_tasks
                       SET status = 'failed', error_message = '服务重启中断了生成，请重试。',
                           completed_at = CURRENT_TIMESTAMP(6)
                       WHERE status IN ('pending', 'running')"""
                )
            conn.commit()
        return int(affected)

    def list_deleted_tasks(self, owner_username: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT id, start_date, end_date, focus, status, news_count, created_at, updated_at, deleted_at
                       FROM daily_news_summary_tasks
                       WHERE owner_username = %s AND deleted_at IS NOT NULL
                       ORDER BY deleted_at DESC, id DESC LIMIT %s""",
                    (owner_username, limit),
                )
                rows = cursor.fetchall()
        return [serialize_row(row) or {} for row in rows]

    def soft_delete_task(self, owner_username: str, task_id: int) -> dict[str, bool]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT status FROM daily_news_summary_tasks WHERE id = %s AND owner_username = %s AND deleted_at IS NULL FOR UPDATE",
                    (task_id, owner_username),
                )
                task = cursor.fetchone()
                if not task:
                    raise DailyNewsSummaryNotFoundError("新闻总结任务不存在")
                if task["status"] in {"pending", "running"}:
                    raise RuntimeError("进行中的新闻总结任务不能删除")
                cursor.execute(
                    "UPDATE daily_news_summary_tasks SET deleted_at = CURRENT_TIMESTAMP(6) WHERE id = %s AND owner_username = %s",
                    (task_id, owner_username),
                )
            conn.commit()
        return {"deleted": True}

    def restore_task(self, owner_username: str, task_id: int) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE daily_news_summary_tasks SET deleted_at = NULL WHERE id = %s AND owner_username = %s AND deleted_at IS NOT NULL",
                    (task_id, owner_username),
                )
                restored = cursor.rowcount == 1
            conn.commit()
        if not restored:
            raise DailyNewsSummaryNotFoundError("新闻总结任务不存在或不在最近删除中")
        task = self.get_task(owner_username, task_id)
        if not task:
            raise RuntimeError("恢复新闻总结任务后未找到记录")
        return task

    def permanently_delete_task(self, owner_username: str, task_id: int) -> dict[str, bool]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM daily_news_summary_tasks WHERE id = %s AND owner_username = %s AND deleted_at IS NOT NULL",
                    (task_id, owner_username),
                )
                deleted = cursor.rowcount == 1
            conn.commit()
        if not deleted:
            raise DailyNewsSummaryNotFoundError("新闻总结任务不存在或不在最近删除中")
        return {"deleted": True}

    def permanently_delete_all_deleted_tasks(self, owner_username: str) -> int:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM daily_news_summary_tasks WHERE owner_username = %s AND deleted_at IS NOT NULL",
                    (owner_username,),
                )
                deleted = cursor.rowcount
            conn.commit()
        return int(deleted)
