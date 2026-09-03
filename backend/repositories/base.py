"""业务仓储共享基础设施：连接上下文、行序列化、工厂方法。

收敛各仓库重复的 ``_connection`` / ``from_environment`` / ``_serialize_row`` /
``_json_default`` 样板（news_summary / report_generation / research_report 等）。
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, ClassVar, Iterator

from backend.common.database import get_repo_connection


def serialize_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """将 DictCursor 行转换为可 JSON 化字典。

    - ``date`` / ``datetime`` → ISO 字符串
    - ``*_json`` 列（字符串）→ 尝试反序列化为结构
    """
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


def json_default(value: Any) -> str:
    """``json.dumps`` 的 ``default`` 钩子：``date`` / ``datetime`` 序列化为 ISO 字符串。"""
    return value.isoformat() if isinstance(value, (date, datetime)) else str(value)


class BaseRepository:
    """提供面向 repositories/ 的共享连接管理与工厂方法，避免各仓储重复样板。"""

    @classmethod
    def from_environment(cls) -> "BaseRepository":
        return cls()

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        with get_repo_connection() as connection:
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise


class RecycleBinMixin:
    """回收站通用 CRUD。

    收敛 `list_deleted_*` / `soft_delete_*` / `restore_*` / `permanently_delete_*` /
    `permanently_delete_all_deleted_*` 这套在各任务仓储里重复的垂直切片
    （news_summary / report_generation / ai_strategy_history）。
    子类通过类级规格属性声明差异，方法名与失败语义保持不变：

    - ``recycle_table``：回收站表名
    - ``recycle_now``：写入 `deleted_at` 的时间戳表达式（如 ``"CURRENT_TIMESTAMP(6)"``）
    - ``recycle_restore_suffix``：restore 时追加到 ``SET deleted_at = NULL`` 后的片段
    - ``recycle_list_columns``：`list_deleted_*` 的 SELECT 列
    - ``recycle_in_flight``：`soft_delete_*` 视为「进行中」而禁止删除的状态集合
    - ``recycle_not_found`` / ``recycle_conflict``：未找到 / 状态冲突的错误类
    - ``recycle_not_found_msg`` / ``recycle_in_flight_msg`` / ``recycle_not_in_trash_msg`` /
      ``recycle_restore_miss_msg``：各失败场景的文案（用户可见，必须逐字保真）
    - ``recycle_getter``：restore 成功后回查记录的方法名（如 ``"get_task"``）
    """

    recycle_table: ClassVar[str]
    recycle_now: ClassVar[str] = "CURRENT_TIMESTAMP(6)"
    recycle_restore_suffix: ClassVar[str] = ""
    recycle_list_columns: ClassVar[tuple[str, ...]]
    recycle_in_flight: ClassVar[frozenset[str]] = frozenset()
    recycle_not_found: ClassVar[type[Exception]] = RuntimeError
    recycle_conflict: ClassVar[type[Exception]] = RuntimeError
    recycle_not_found_msg: ClassVar[str]
    recycle_in_flight_msg: ClassVar[str]
    recycle_not_in_trash_msg: ClassVar[str]
    recycle_restore_miss_msg: ClassVar[str]
    recycle_getter: ClassVar[str] = "get_task"

    def list_deleted_tasks(self, owner_username: str, limit: int = 100) -> list[dict[str, Any]]:
        columns = ", ".join(self.recycle_list_columns)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT {columns} FROM {self.recycle_table}
                         WHERE owner_username = %s AND deleted_at IS NOT NULL
                         ORDER BY deleted_at DESC, id DESC LIMIT %s""",
                    (owner_username, limit),
                )
                rows = cursor.fetchall()
        return [serialize_row(row) or {} for row in rows]

    def soft_delete_task(self, owner_username: str, task_id: Any) -> dict[str, bool]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT status FROM {self.recycle_table}
                         WHERE id = %s AND owner_username = %s AND deleted_at IS NULL FOR UPDATE""",
                    (task_id, owner_username),
                )
                item = cursor.fetchone()
                if not item:
                    raise self.recycle_not_found(self.recycle_not_found_msg)
                if item["status"] in self.recycle_in_flight:
                    raise self.recycle_conflict(self.recycle_in_flight_msg)
                cursor.execute(
                    f"""UPDATE {self.recycle_table}
                         SET deleted_at = {self.recycle_now}
                         WHERE id = %s AND owner_username = %s""",
                    (task_id, owner_username),
                )
            conn.commit()
        return {"deleted": True}

    def restore_task(self, owner_username: str, task_id: Any) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""UPDATE {self.recycle_table}
                         SET deleted_at = NULL{self.recycle_restore_suffix}
                         WHERE id = %s AND owner_username = %s AND deleted_at IS NOT NULL""",
                    (task_id, owner_username),
                )
                restored = cursor.rowcount == 1
            conn.commit()
        if not restored:
            raise self.recycle_not_found(self.recycle_not_in_trash_msg)
        record = getattr(self, self.recycle_getter)(owner_username, task_id)
        if not record:
            raise RuntimeError(self.recycle_restore_miss_msg)
        return record

    def permanently_delete_task(self, owner_username: str, task_id: Any) -> dict[str, bool]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""DELETE FROM {self.recycle_table}
                         WHERE id = %s AND owner_username = %s AND deleted_at IS NOT NULL""",
                    (task_id, owner_username),
                )
                deleted = cursor.rowcount == 1
            conn.commit()
        if not deleted:
            raise self.recycle_not_found(self.recycle_not_in_trash_msg)
        return {"deleted": True}

    def permanently_delete_all_deleted_tasks(self, owner_username: str) -> int:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                deleted = cursor.execute(
                    f"""DELETE FROM {self.recycle_table}
                         WHERE owner_username = %s AND deleted_at IS NOT NULL""",
                    (owner_username,),
                )
            conn.commit()
        return int(deleted)