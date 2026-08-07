"""Agent 会话上下文和助手消息状态持久化。"""

from __future__ import annotations

from typing import Any, Optional

from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.workbench_repository import WorkbenchNotFoundError, _serialize_row


class MessageRepository(ConversationRepository):
    def get_agent_history(self, username: str, conversation_id: str, limit: int) -> list[dict[str, str]]:
        self.get_conversation(username, conversation_id)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT role, content FROM (
                           SELECT id, role, content, created_at FROM workbench_messages
                           WHERE conversation_id = %s AND status = 'completed' AND content <> ''
                           ORDER BY created_at DESC, id DESC LIMIT %s
                       ) recent ORDER BY created_at ASC, id ASC""",
                    (conversation_id, limit),
                )
                rows = cursor.fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def finish_assistant_message(self, assistant_message_id: str, content: str, status: str, error_code: Optional[str] = None) -> dict[str, Any]:
        """在 SSE 结束、失败或断连时保存完整或部分助手内容。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE workbench_messages
                         SET content = %s, status = %s, error_code = %s, completed_at = CURRENT_TIMESTAMP(6)
                       WHERE id = %s AND role = 'assistant'""",
                    (content, status, error_code, assistant_message_id),
                )
                cursor.execute(
                    """SELECT m.*, c.project_id FROM workbench_messages m
                         INNER JOIN workbench_conversations c ON c.id = m.conversation_id
                         WHERE m.id = %s""",
                    (assistant_message_id,),
                )
                message = cursor.fetchone()
                if not message:
                    raise WorkbenchNotFoundError("助手消息不存在")
                cursor.execute(
                    """UPDATE workbench_conversations
                         SET last_message_at = CURRENT_TIMESTAMP(6), updated_at = CURRENT_TIMESTAMP(6)
                       WHERE id = %s""",
                    (message["conversation_id"],),
                )
                if message.get("project_id"):
                    cursor.execute("UPDATE workbench_projects SET updated_at = CURRENT_TIMESTAMP(6) WHERE id = %s", (message["project_id"],))
                message.pop("project_id", None)
            conn.commit()
        return _serialize_row(message) or {}

    def mark_streaming_messages_interrupted(self) -> int:
        """服务重启后不让旧的 streaming 状态永久卡住。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(
                    """UPDATE workbench_messages
                         SET status = 'interrupted', completed_at = CURRENT_TIMESTAMP(6)
                       WHERE role = 'assistant' AND status = 'streaming'"""
                )
            conn.commit()
        return affected
