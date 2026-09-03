"""个人关注列表的持久化访问。"""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from backend.repositories.workbench_repository import (
    WorkbenchNotFoundError,
    WorkbenchRepository,
    _serialize_row,
)

WatchlistObjectType = Literal["news", "factor", "macro_signal"]


def _row_metadata(row: dict[str, Any]) -> dict[str, Any]:
    """将 ``metadata_json`` 列重命名为 ``metadata`` 并保证为结构。

    ``serialize_row`` 已把 JSON 字符串解析为结构，此处仅做键名迁移；
    对残留字符串（极少见的非法 JSON）再兜底解析一次。
    """
    metadata = row.pop("metadata_json", None) or {}
    return json.loads(metadata) if isinstance(metadata, str) else metadata


class WatchlistRepository(WorkbenchRepository):
    """个人关注列表（新闻/因子/宏观信号）的增删查。"""

    def list_items(self, username: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT * FROM workbench_watchlist_items
                       WHERE owner_username = %s AND deleted_at IS NULL
                       ORDER BY updated_at DESC, id DESC""",
                    (username,),
                )
                rows = cursor.fetchall()
        for row in rows:
            row["metadata"] = _row_metadata(row)
        return [_serialize_row(row) or {} for row in rows]

    def add_item(
        self,
        username: str,
        object_type: WatchlistObjectType,
        object_id: str,
        title: str,
        source_url: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        item_id = str(uuid.uuid4())
        metadata_json = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO workbench_watchlist_items
                         (id, owner_username, object_type, object_id, title, source_url, metadata_json)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                         title = VALUES(title), source_url = VALUES(source_url),
                         metadata_json = VALUES(metadata_json), deleted_at = NULL,
                         updated_at = CURRENT_TIMESTAMP(6)""",
                    (item_id, username, object_type, object_id, title, source_url, metadata_json),
                )
                cursor.execute(
                    """SELECT * FROM workbench_watchlist_items
                       WHERE owner_username = %s AND object_type = %s AND object_id = %s""",
                    (username, object_type, object_id),
                )
                row = cursor.fetchone()
            conn.commit()
        row["metadata"] = _row_metadata(row)
        return _serialize_row(row) or {}

    def remove_item(self, username: str, item_id: str) -> dict[str, bool]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE workbench_watchlist_items
                       SET deleted_at = CURRENT_TIMESTAMP(6), updated_at = CURRENT_TIMESTAMP(6)
                       WHERE id = %s AND owner_username = %s AND deleted_at IS NULL""",
                    (item_id, username),
                )
                if cursor.rowcount != 1:
                    raise WorkbenchNotFoundError("关注项不存在或无权操作")
            conn.commit()
        return {"deleted": True}
