"""每日新闻总结任务持久化，复用项目业务库连接配置。"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterator

import pymysql
from pymysql.cursors import DictCursor

from backend.config.config import MYSQL_CONFIG


class DailyNewsSummaryNotFoundError(RuntimeError):
    """任务不存在或不属于当前用户。"""


def _json_default(value: Any) -> str:
    return value.isoformat() if isinstance(value, (date, datetime)) else str(value)


def _serialize_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (date, datetime)):
            result[key] = value.isoformat()
        elif key.endswith("_json") and isinstance(value, str):
            try:
                result[key] = json.loads(value)
            except json.JSONDecodeError:
                result[key] = value
        else:
            result[key] = value
    return result


class DailyNewsSummaryRepository:
    @classmethod
    def from_environment(cls) -> "DailyNewsSummaryRepository":
        return cls(dict(MYSQL_CONFIG))

    def __init__(self, settings: dict[str, Any]):
        self._settings = settings

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        connection = pymysql.connect(
            **{**self._settings, "autocommit": False}, cursorclass=DictCursor
        )
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

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
                       WHERE owner_username = %s
                       ORDER BY updated_at DESC, id DESC LIMIT %s""",
                    (owner_username, limit),
                )
                rows = cursor.fetchall()
        return [_serialize_row(row) or {} for row in rows]

    def get_task(self, owner_username: str, task_id: int) -> dict[str, Any] | None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM daily_news_summary_tasks WHERE id = %s AND owner_username = %s",
                    (task_id, owner_username),
                )
                row = cursor.fetchone()
        return _serialize_row(row)

    def mark_running(self, owner_username: str, task_id: int) -> bool:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(
                    """UPDATE daily_news_summary_tasks
                       SET status = 'running', started_at = CURRENT_TIMESTAMP(6), error_message = NULL
                       WHERE id = %s AND owner_username = %s AND status = 'pending'""",
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
                       WHERE id = %s AND owner_username = %s AND status = 'running'""",
                    (
                        status,
                        news_count,
                        json.dumps(source_stats, ensure_ascii=False),
                        summary,
                        json.dumps(references, ensure_ascii=False, default=_json_default),
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
                       WHERE id = %s AND owner_username = %s AND status IN ('pending', 'running')""",
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
