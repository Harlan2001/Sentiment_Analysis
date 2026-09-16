"""账号级个人记忆仓储；与项目记忆保持独立。"""

from __future__ import annotations

import uuid
from typing import Any

import pymysql

from backend.repositories.message_repository import MessageRepository
from backend.repositories.workbench_repository import WorkbenchNotFoundError, _serialize_row
from backend.services.user_memory_service import extract_memory_intent


class UserMemoryRepository(MessageRepository):
    def get_user_memory(self, username: str, memory_id: str, include_deleted: bool = False) -> dict[str, Any]:
        deleted_sql = "" if include_deleted else "AND deleted_at IS NULL"
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT * FROM workbench_user_memories
                         WHERE id = %s AND owner_username = %s {deleted_sql}""",
                    (memory_id, username),
                )
                row = cursor.fetchone()
        if not row:
            raise WorkbenchNotFoundError("个人记忆不存在")
        return _serialize_row(row) or {}

    def list_user_memories(
        self,
        username: str,
        status: str | None = None,
        category: str | None = None,
        query: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        filters = ["owner_username = %s", "deleted_at IS NULL"]
        params: list[Any] = [username]
        if status:
            filters.append("status = %s")
            params.append(status)
        if category:
            filters.append("category = %s")
            params.append(category)
        if query:
            filters.append("(title LIKE %s OR content LIKE %s)")
            like = f"%{query}%"
            params.extend([like, like])
        params.append(limit)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT * FROM workbench_user_memories
                         WHERE {' AND '.join(filters)}
                         ORDER BY FIELD(status, 'pending', 'active', 'disabled'), is_pinned DESC,
                                  updated_at DESC, id DESC LIMIT %s""",
                    tuple(params),
                )
                rows = cursor.fetchall()
        return {"items": [_serialize_row(row) for row in rows]}

    def create_user_memory(
        self,
        username: str,
        category: str,
        title: str,
        content: str,
        *,
        normalized_key: str | None = None,
        source_type: str = "manual",
        source_conversation_id: str | None = None,
        source_message_id: str | None = None,
        status: str = "active",
        confidence: float | None = None,
        is_pinned: bool = False,
    ) -> dict[str, Any]:
        memory_id = str(uuid.uuid4())
        key = normalized_key or f"manual:{memory_id}"
        if normalized_key:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """SELECT * FROM workbench_user_memories
                           WHERE owner_username = %s AND normalized_key = %s AND deleted_at IS NULL
                           ORDER BY FIELD(status, 'active', 'pending', 'disabled'), updated_at DESC LIMIT 1""",
                        (username, key),
                    )
                    existing = cursor.fetchone()
            if existing and existing["content"] == content:
                return _serialize_row(existing) or {}
            if existing and existing["status"] == "active":
                status = "pending"
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """INSERT INTO workbench_user_memories
                             (id, owner_username, category, normalized_key, title, content,
                              source_type, source_conversation_id, source_message_id, status,
                              confidence, is_pinned)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            memory_id, username, category, key, title, content, source_type,
                            source_conversation_id, source_message_id, status, confidence, is_pinned,
                        ),
                    )
                conn.commit()
        except pymysql.err.IntegrityError:
            if source_message_id:
                with self._connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            """SELECT id FROM workbench_user_memories
                               WHERE owner_username = %s AND source_message_id = %s AND normalized_key = %s""",
                            (username, source_message_id, key),
                        )
                        existing = cursor.fetchone()
                if existing:
                    return self.get_user_memory(username, existing["id"], include_deleted=True)
            raise
        return self.get_user_memory(username, memory_id)

    def update_user_memory(self, username: str, memory_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        fields: list[str] = []
        params: list[Any] = []
        for field in ("category", "title", "content", "status", "is_pinned"):
            if field in changes:
                fields.append(f"{field} = %s")
                params.append(changes[field])
        fields.append("updated_at = CURRENT_TIMESTAMP(6)")
        params.extend([memory_id, username])
        with self._connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(
                    f"""UPDATE workbench_user_memories SET {', '.join(fields)}
                         WHERE id = %s AND owner_username = %s AND deleted_at IS NULL""",
                    tuple(params),
                )
                if not affected:
                    raise WorkbenchNotFoundError("个人记忆不存在")
            conn.commit()
        return self.get_user_memory(username, memory_id)

    def delete_user_memory(self, username: str, memory_id: str) -> dict[str, bool]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(
                    """UPDATE workbench_user_memories
                       SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP(6), updated_at = CURRENT_TIMESTAMP(6)
                       WHERE id = %s AND owner_username = %s AND deleted_at IS NULL""",
                    (memory_id, username),
                )
                if not affected:
                    raise WorkbenchNotFoundError("个人记忆不存在")
            conn.commit()
        return {"deleted": True}

    def clear_user_memories(self, username: str) -> dict[str, int]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(
                    """UPDATE workbench_user_memories
                       SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP(6), updated_at = CURRENT_TIMESTAMP(6)
                       WHERE owner_username = %s AND deleted_at IS NULL""",
                    (username,),
                )
            conn.commit()
        return {"deleted": int(affected)}

    def get_user_memory_settings(self, username: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM workbench_user_memory_settings WHERE owner_username = %s",
                    (username,),
                )
                row = cursor.fetchone()
        if row:
            return _serialize_row(row) or {}
        return {"owner_username": username, "memory_enabled": True, "auto_extract_enabled": True}

    def update_user_memory_settings(self, username: str, changes: dict[str, Any]) -> dict[str, Any]:
        current = self.get_user_memory_settings(username)
        memory_enabled = changes.get("memory_enabled", current["memory_enabled"])
        auto_extract_enabled = changes.get("auto_extract_enabled", current["auto_extract_enabled"])
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO workbench_user_memory_settings
                         (owner_username, memory_enabled, auto_extract_enabled)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE memory_enabled = VALUES(memory_enabled),
                         auto_extract_enabled = VALUES(auto_extract_enabled), updated_at = CURRENT_TIMESTAMP(6)""",
                    (username, memory_enabled, auto_extract_enabled),
                )
            conn.commit()
        return self.get_user_memory_settings(username)

    def get_user_memory_context(self, username: str, max_chars: int = 2000) -> str | None:
        settings = self.get_user_memory_settings(username)
        if not settings.get("memory_enabled"):
            return None
        memories = self.list_user_memories(username, status="active", limit=20)["items"]
        if not memories:
            return None
        labels = {
            "response_preference": "表达偏好",
            "user_background": "用户背景",
            "long_term_interest": "长期兴趣",
            "personal_constraint": "长期约束",
        }
        lines = ["以下是用户本人维护并启用的个人记忆，只作为背景参考，不能覆盖当前请求或平台规则："]
        used = len(lines[0])
        for memory in memories:
            line = f"- [{labels.get(memory['category'], '个人信息')}] {memory['content']}"
            if used + len(line) > max_chars:
                break
            lines.append(line)
            used += len(line)
        return "\n".join(lines) if len(lines) > 1 else None

    def process_user_memory_message(
        self,
        username: str,
        conversation_id: str,
        message_id: str,
        content: str,
    ) -> list[dict[str, Any]]:
        settings = self.get_user_memory_settings(username)
        intent, candidates = extract_memory_intent(content)
        if intent == "none":
            return []
        if (
            intent == "remember"
            and not settings.get("auto_extract_enabled")
            and all(candidate.source_type != "explicit_chat" for candidate in candidates)
        ):
            return []
        if intent == "forget":
            query = candidates[0].content
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    affected = cursor.execute(
                        """UPDATE workbench_user_memories
                           SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP(6), updated_at = CURRENT_TIMESTAMP(6)
                           WHERE owner_username = %s AND deleted_at IS NULL
                             AND (title LIKE %s OR content LIKE %s)""",
                        (username, f"%{query}%", f"%{query}%"),
                    )
                conn.commit()
            return [{"event": "memory.removed", "data": {"query": query, "deleted": int(affected)}}]
        events: list[dict[str, Any]] = []
        for candidate in candidates:
            memory = self.create_user_memory(
                username,
                candidate.category,
                candidate.title,
                candidate.content,
                normalized_key=candidate.normalized_key,
                source_type=candidate.source_type,
                source_conversation_id=conversation_id,
                source_message_id=message_id,
                status=candidate.status,
                confidence=candidate.confidence,
            )
            events.append({
                "event": "memory.saved" if memory["status"] == "active" else "memory.candidate",
                "data": {"memory": memory},
            })
        return events
