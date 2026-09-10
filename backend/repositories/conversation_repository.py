"""通用会话列表、消息与侧栏查询。"""

from __future__ import annotations

import uuid
from typing import Any

import pymysql

from backend.repositories.workbench_repository import (
    WorkbenchConflictError,
    WorkbenchNotFoundError,
    WorkbenchPermissionError,
    WorkbenchRepository,
    _decode_cursor,
    _encode_cursor,
    _serialize_row,
)


class ConversationRepository(WorkbenchRepository):
    """在基础项目仓储上补充通用会话操作。"""

    def get_conversation_detail(self, username: str, conversation_id: str, message_limit: int) -> dict[str, Any]:
        conversation = self.get_conversation(username, conversation_id)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT * FROM (
                           SELECT * FROM workbench_messages WHERE conversation_id = %s
                           ORDER BY created_at DESC, id DESC LIMIT %s
                       ) recent ORDER BY created_at ASC, id ASC""",
                    (conversation_id, message_limit),
                )
                messages = cursor.fetchall()
                message_ids = [message["id"] for message in messages]
                skill_names_by_message: dict[str, list[str]] = {}
                if message_ids:
                    placeholders = ", ".join(["%s"] * len(message_ids))
                    cursor.execute(
                        f"""SELECT message_id, skill_name FROM workbench_message_skills
                            WHERE message_id IN ({placeholders}) ORDER BY created_at ASC""",
                        tuple(message_ids),
                    )
                    for usage in cursor.fetchall():
                        skill_names_by_message.setdefault(usage["message_id"], []).append(usage["skill_name"])
                for message in messages:
                    message["skill_names"] = skill_names_by_message.get(message["id"], [])
        return {"conversation": conversation, "messages": [_serialize_row(message) for message in messages]}

    def list_conversations(
        self,
        username: str,
        project_id: str | None,
        limit: int,
        cursor: str | None = None,
        archived: bool = False,
        conversation_owner: str | None = None,
        include_all_members: bool = False,
    ) -> dict[str, Any]:
        decoded = _decode_cursor(cursor)
        status = "archived" if archived else "active"
        page_sql, page_params = "", []
        if decoded:
            page_sql = "AND (COALESCE(c.last_message_at, c.created_at) < %s OR (COALESCE(c.last_message_at, c.created_at) = %s AND c.id < %s))"
            page_params = [decoded[0], decoded[0], decoded[1]]
        if project_id:
            project = self.get_project(username, project_id)
            if include_all_members and not self._is_project_manager(project.get("role")):
                raise WorkbenchPermissionError("只有项目管理者可以查看其他成员的会话")
            if conversation_owner and conversation_owner != username and not self._is_project_manager(project.get("role")):
                raise WorkbenchPermissionError("编辑者只能查看自己的项目会话")
            owner_sql = "" if include_all_members else "AND c.owner_username = %s"
            owner_params = [] if include_all_members else [conversation_owner or username]
            query = f"""SELECT c.* FROM workbench_conversations c
                          INNER JOIN workbench_project_members pm ON pm.project_id = c.project_id
                          WHERE c.project_id = %s AND pm.username = %s {owner_sql}
                            AND c.status = %s AND c.deleted_at IS NULL AND c.last_message_at IS NOT NULL {page_sql}
                          ORDER BY COALESCE(c.last_message_at, c.created_at) DESC, c.id DESC LIMIT %s"""
            params = [project_id, username, *owner_params, status, *page_params, limit + 1]
        else:
            query = f"""SELECT c.* FROM workbench_conversations c
                          WHERE c.owner_username = %s AND c.project_id IS NULL AND c.status = %s AND c.deleted_at IS NULL AND c.last_message_at IS NOT NULL {page_sql}
                          ORDER BY COALESCE(c.last_message_at, c.created_at) DESC, c.id DESC LIMIT %s"""
            params = [username, status, *page_params, limit + 1]
        with self._connection() as conn:
            with conn.cursor() as db_cursor:
                db_cursor.execute(query, tuple(params))
                rows = db_cursor.fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": [_serialize_row(row) for row in rows],
            "next_cursor": _encode_cursor(rows[-1]["last_message_at"] or rows[-1]["created_at"], rows[-1]["id"]) if has_more and rows else None,
        }

    def update_conversation(self, username: str, conversation_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                conversation = self._conversation_for_user(cursor, username, conversation_id)
                if not conversation:
                    raise WorkbenchNotFoundError("会话不存在或当前用户无权访问")
                self._require_conversation_write(conversation, username)
                fields, params = [], []
                if "title" in changes:
                    fields.append("title = %s")
                    params.append(changes["title"])
                if "archived" in changes:
                    fields.append("status = %s")
                    params.append("archived" if changes["archived"] else "active")
                fields.append("updated_at = CURRENT_TIMESTAMP(6)")
                params.append(conversation_id)
                cursor.execute(f"UPDATE workbench_conversations SET {', '.join(fields)} WHERE id = %s", tuple(params))
            conn.commit()
        # 归档不更新项目时间；项目更新时间只由项目内容变化驱动。
        return self.get_conversation(username, conversation_id)

    def soft_delete_conversation(self, username: str, conversation_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                conversation = self._conversation_for_user(cursor, username, conversation_id)
                if not conversation:
                    raise WorkbenchNotFoundError("会话不存在或当前用户无权访问")
                self._require_conversation_write(conversation, username)
                cursor.execute(
                    "UPDATE workbench_conversations SET deleted_at = NOW(6) WHERE id = %s",
                    (conversation_id,),
                )
            conn.commit()
        return {"deleted": True}

    def restore_conversation(self, username: str, conversation_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT c.*, pm.role AS project_role
                       FROM workbench_conversations c
                       LEFT JOIN workbench_project_members pm
                         ON pm.project_id = c.project_id AND pm.username = %s
                       WHERE c.id = %s
                         AND c.deleted_at IS NOT NULL
                         AND ((c.project_id IS NULL AND c.owner_username = %s)
                              OR (c.project_id IS NOT NULL AND
                                  pm.role IN ('manager', 'owner', 'editor', 'viewer') AND
                                  (pm.role IN ('manager', 'owner') OR c.owner_username = %s)))""",
                    (username, conversation_id, username, username),
                )
                conversation = cursor.fetchone()
                if not conversation:
                    raise WorkbenchNotFoundError("会话不存在或当前用户无权访问")
                self._require_conversation_write(conversation, username)
                if conversation.get("project_id"):
                    cursor.execute(
                        "SELECT 1 FROM workbench_projects WHERE id = %s AND deleted_at IS NULL",
                        (conversation["project_id"],),
                    )
                    if not cursor.fetchone():
                        raise WorkbenchConflictError("所属项目已被删除，请先恢复项目再恢复会话")
                cursor.execute(
                    "UPDATE workbench_conversations SET deleted_at = NULL WHERE id = %s",
                    (conversation_id,),
                )
            conn.commit()
        return self.get_conversation(username, conversation_id)

    def permanently_delete_conversation(self, username: str, conversation_id: str) -> dict[str, bool]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT c.*, pm.role AS project_role
                       FROM workbench_conversations c
                       LEFT JOIN workbench_project_members pm
                         ON pm.project_id = c.project_id AND pm.username = %s
                       WHERE c.id = %s AND c.deleted_at IS NOT NULL
                         AND ((c.project_id IS NULL AND c.owner_username = %s)
                              OR (c.project_id IS NOT NULL AND
                                  pm.role IN ('manager', 'owner', 'editor', 'viewer') AND
                                  (pm.role IN ('manager', 'owner') OR c.owner_username = %s)))""",
                    (username, conversation_id, username, username),
                )
                conversation = cursor.fetchone()
                if not conversation:
                    raise WorkbenchNotFoundError("会话不存在或不在最近删除中")
                self._require_conversation_write(conversation, username)
                cursor.execute("DELETE FROM workbench_conversations WHERE id = %s", (conversation_id,))
            conn.commit()
        return {"deleted": True}

    def permanently_delete_all_deleted_items(self, username: str) -> dict[str, int]:
        """Empty the user's project and conversation recycle-bin entries."""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT p.id FROM workbench_projects p
                       INNER JOIN workbench_project_members pm ON pm.project_id = p.id
                       WHERE pm.username = %s AND pm.role IN ('manager', 'owner') AND p.deleted_at IS NOT NULL""",
                    (username,),
                )
                project_ids = [row["id"] for row in cursor.fetchall()]
                project_count = len(project_ids)
                for project_id in project_ids:
                    cursor.execute("DELETE FROM workbench_conversations WHERE project_id = %s", (project_id,))
                    cursor.execute("DELETE FROM workbench_project_memories WHERE project_id = %s", (project_id,))
                    cursor.execute("DELETE FROM workbench_projects WHERE id = %s", (project_id,))
                cursor.execute(
                    """DELETE FROM workbench_conversations
                       WHERE owner_username = %s AND project_id IS NULL AND deleted_at IS NOT NULL""",
                    (username,),
                )
                conversation_count = cursor.rowcount
            conn.commit()
        return {"projects": project_count, "conversations": conversation_count}

    def list_deleted_items(self, username: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT p.* FROM workbench_projects p
                       INNER JOIN workbench_project_members pm ON pm.project_id = p.id
                       WHERE pm.username = %s AND pm.role IN ('manager', 'owner') AND p.deleted_at IS NOT NULL
                       ORDER BY p.deleted_at DESC LIMIT 50""",
                    (username,),
                )
                deleted_projects = cursor.fetchall()
                cursor.execute(
                    """SELECT c.* FROM workbench_conversations c
                       LEFT JOIN workbench_projects p ON p.id = c.project_id
                       LEFT JOIN workbench_project_members pm
                         ON pm.project_id = c.project_id AND pm.username = %s
                       WHERE c.owner_username = %s
                         AND c.deleted_at IS NOT NULL
                         AND (c.project_id IS NULL OR
                              (p.deleted_at IS NULL AND
                               pm.role IN ('manager', 'owner', 'editor', 'viewer')))
                       ORDER BY c.deleted_at DESC LIMIT 50""",
                    (username, username),
                )
                deleted_conversations = cursor.fetchall()
        return {
            "deleted_projects": [_serialize_row(row) for row in deleted_projects],
            "deleted_conversations": [_serialize_row(row) for row in deleted_conversations],
        }

    def get_sidebar(self, username: str, conversation_limit: int = 5) -> dict[str, Any]:
        projects = self.list_projects(username, limit=100)["items"]
        for project in projects:
            project["recent_conversations"] = self.list_conversations(username, project["id"], conversation_limit)["items"]
        return {
            "projects": projects,
            "recent_conversations": self.list_conversations(username, None, conversation_limit)["items"],
            "limits": {"project_conversations": conversation_limit, "recent_conversations": conversation_limit},
        }

    def get_message_retry(
        self,
        username: str,
        conversation_id: str,
        content: str,
        client_message_id: str,
    ) -> dict[str, Any] | None:
        """Return an already accepted idempotent message before revalidating Skills."""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                conversation = self._conversation_for_user(cursor, username, conversation_id)
                if not conversation:
                    raise WorkbenchNotFoundError("会话不存在或当前用户无权访问")
                self._require_conversation_write(conversation, username)
                cursor.execute(
                    "SELECT * FROM workbench_messages WHERE conversation_id = %s AND client_message_id = %s",
                    (conversation_id, client_message_id),
                )
                user_message = cursor.fetchone()
                if not user_message:
                    return None
                if user_message["content"] != content:
                    raise WorkbenchConflictError("相同 client_message_id 对应了不同消息内容")
                cursor.execute(
                    "SELECT * FROM workbench_messages WHERE parent_message_id = %s AND role = 'assistant' LIMIT 1",
                    (user_message["id"],),
                )
                assistant_message = cursor.fetchone()
        return {
            "created": False,
            "user_message": _serialize_row(user_message),
            "assistant_message": _serialize_row(assistant_message),
        }

    def prepare_message(self, username: str, conversation_id: str, content: str, client_message_id: str, selected_skills: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """原子保存用户消息和占位助手消息，防止重试重复调用 Agent。
        并发重试撞唯一索引时回查已存消息做幂等返回（对齐 create_project 的兜底）。"""
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    conversation = self._conversation_for_user(cursor, username, conversation_id)
                    if not conversation:
                        raise WorkbenchNotFoundError("会话不存在或当前用户无权访问")
                    self._require_conversation_write(conversation, username)
                    if conversation["status"] == "archived":
                        raise WorkbenchConflictError("已归档会话不能继续发送消息")
                    cursor.execute(
                        "SELECT * FROM workbench_messages WHERE conversation_id = %s AND client_message_id = %s",
                        (conversation_id, client_message_id),
                    )
                    user_message = cursor.fetchone()
                    if user_message:
                        if user_message["content"] != content:
                            raise WorkbenchConflictError("相同 client_message_id 对应了不同消息内容")
                        cursor.execute("SELECT * FROM workbench_messages WHERE parent_message_id = %s AND role = 'assistant' LIMIT 1", (user_message["id"],))
                        return {"created": False, "user_message": _serialize_row(user_message), "assistant_message": _serialize_row(cursor.fetchone())}

                    user_message_id, assistant_message_id = str(uuid.uuid4()), str(uuid.uuid4())
                    cursor.execute(
                        """INSERT INTO workbench_messages
                             (id, conversation_id, role, content, status, client_message_id, completed_at)
                           VALUES (%s, %s, 'user', %s, 'completed', %s, CURRENT_TIMESTAMP(6))""",
                        (user_message_id, conversation_id, content, client_message_id),
                    )
                    cursor.execute(
                        """INSERT INTO workbench_messages
                             (id, conversation_id, parent_message_id, role, content, status)
                           VALUES (%s, %s, %s, 'assistant', '', 'streaming')""",
                        (assistant_message_id, conversation_id, user_message_id),
                    )
                    for skill in selected_skills or []:
                        cursor.execute(
                            """INSERT INTO workbench_message_skills
                                 (id, message_id, skill_id, skill_name)
                               VALUES (%s, %s, %s, %s)""",
                            (str(uuid.uuid4()), assistant_message_id, skill["id"], skill["name"]),
                        )
                    default_title = " ".join(content.split())[:120]
                    cursor.execute(
                        """UPDATE workbench_conversations
                             SET title = COALESCE(title, %s), last_message_at = CURRENT_TIMESTAMP(6), updated_at = CURRENT_TIMESTAMP(6)
                           WHERE id = %s""",
                        (default_title, conversation_id),
                    )
                    if conversation.get("project_id"):
                        cursor.execute("UPDATE workbench_projects SET updated_at = CURRENT_TIMESTAMP(6) WHERE id = %s", (conversation["project_id"],))
                    cursor.execute("SELECT * FROM workbench_messages WHERE id = %s", (user_message_id,))
                    user_message = cursor.fetchone()
                    cursor.execute("SELECT * FROM workbench_messages WHERE id = %s", (assistant_message_id,))
                    assistant_message = cursor.fetchone()
                    conn.commit()
        except pymysql.err.IntegrityError:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT * FROM workbench_messages WHERE conversation_id = %s AND client_message_id = %s",
                        (conversation_id, client_message_id),
                    )
                    user_message = cursor.fetchone()
                    if not user_message:
                        raise
                    if user_message["content"] != content:
                        raise WorkbenchConflictError("相同 client_message_id 对应了不同消息内容")
                    cursor.execute("SELECT * FROM workbench_messages WHERE parent_message_id = %s AND role = 'assistant' LIMIT 1", (user_message["id"],))
                    return {"created": False, "user_message": _serialize_row(user_message), "assistant_message": _serialize_row(cursor.fetchone())}
        return {"created": True, "user_message": _serialize_row(user_message), "assistant_message": _serialize_row(assistant_message)}
