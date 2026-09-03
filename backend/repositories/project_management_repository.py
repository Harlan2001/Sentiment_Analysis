"""项目记忆与成员权限管理仓储。"""

from __future__ import annotations

import uuid
from typing import Any

import pymysql

from backend.repositories.message_repository import MessageRepository
from backend.repositories.workbench_repository import (
    WorkbenchConflictError,
    WorkbenchNotFoundError,
    WorkbenchPermissionError,
    _serialize_row,
)


class ProjectManagementRepository(MessageRepository):
    """在工作台消息仓储上补充项目管理能力。"""

    @staticmethod
    def _require_project_owner(project: dict[str, Any]) -> None:
        if project.get("role") != "owner":
            raise WorkbenchPermissionError("只有项目所有者才能管理成员")

    def create_project(
        self,
        username: str,
        name: str,
        description: str | None,
        client_request_id: str | None = None,
        initial_memories: list[dict[str, Any]] | None = None,
        initial_members: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        initial_memories = initial_memories or []
        initial_members = initial_members or []
        if not client_request_id and not initial_memories and not initial_members:
            return super().create_project(username, name, description)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT id FROM workbench_projects
                       WHERE owner_username = %s AND client_request_id = %s""",
                    (username, client_request_id),
                )
                existing = cursor.fetchone()
        if existing:
            self._revive_project(username, existing["id"])
            return self.get_project(username, existing["id"])

        project_id = str(uuid.uuid4())
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    for member in initial_members:
                        if member["username"] == username:
                            raise WorkbenchConflictError("项目所有者无需重复添加为成员")
                        cursor.execute(
                            "SELECT username FROM users WHERE username = %s AND is_active = 1",
                            (member["username"],),
                        )
                        if not cursor.fetchone():
                            raise WorkbenchNotFoundError(
                                f"未找到可用的本地用户：{member['username']}"
                            )
                    cursor.execute(
                        """INSERT INTO workbench_projects
                             (id, owner_username, name, description, visibility, client_request_id)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (project_id, username, name, description, "shared" if initial_members else "private", client_request_id),
                    )
                    cursor.execute(
                        """INSERT INTO workbench_project_members (project_id, username, role)
                           VALUES (%s, %s, 'owner')""",
                        (project_id, username),
                    )
                    for memory in initial_memories:
                        cursor.execute(
                            """INSERT INTO workbench_project_memories
                                 (id, project_id, category, title, content, is_active, created_by, updated_by)
                               VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s)""",
                            (
                                str(uuid.uuid4()), project_id, memory["category"], memory["title"],
                                memory["content"], username, username,
                            ),
                        )
                    for member in initial_members:
                        cursor.execute(
                            """INSERT INTO workbench_project_members
                                 (project_id, username, role) VALUES (%s, %s, %s)""",
                            (project_id, member["username"], member["role"]),
                        )
                conn.commit()
        except pymysql.err.IntegrityError:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM workbench_projects WHERE owner_username = %s AND client_request_id = %s", (username, client_request_id))
                    existing = cursor.fetchone()
            if existing:
                self._revive_project(username, existing["id"])
                return self.get_project(username, existing["id"])
            raise
        return self.get_project(username, project_id)

    def _revive_project(self, username: str, project_id: str) -> None:
        """同一幂等键命中的项目若处于软删状态，先恢复为可用再返回。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE workbench_projects SET deleted_at = NULL WHERE id = %s AND owner_username = %s",
                    (project_id, username),
                )
            conn.commit()

    def list_project_memories(self, username: str, project_id: str, include_inactive: bool = True) -> list[dict[str, Any]]:
        self.get_project(username, project_id)
        active_sql = "" if include_inactive else "AND is_active = TRUE"
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT * FROM workbench_project_memories
                         WHERE project_id = %s {active_sql}
                         ORDER BY is_active DESC, updated_at DESC, id DESC""",
                    (project_id,),
                )
                rows = cursor.fetchall()
        return [_serialize_row(row) or {} for row in rows]

    def get_project_memory(self, username: str, project_id: str, memory_id: str) -> dict[str, Any]:
        self.get_project(username, project_id)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM workbench_project_memories WHERE id = %s AND project_id = %s",
                    (memory_id, project_id),
                )
                memory = cursor.fetchone()
        if not memory:
            raise WorkbenchNotFoundError("项目记忆不存在")
        return _serialize_row(memory) or {}

    def create_project_memory(
        self,
        username: str,
        project_id: str,
        category: str,
        title: str,
        content: str,
        is_active: bool,
    ) -> dict[str, Any]:
        memory_id = str(uuid.uuid4())
        with self._connection() as conn:
            with conn.cursor() as cursor:
                project = self._project_for_user(cursor, username, project_id)
                if not project:
                    raise WorkbenchNotFoundError("项目不存在或当前用户无权访问")
                self._require_project_write(project)
                cursor.execute(
                    """INSERT INTO workbench_project_memories
                         (id, project_id, category, title, content, is_active, created_by, updated_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (memory_id, project_id, category, title, content, is_active, username, username),
                )
                cursor.execute(
                    "UPDATE workbench_projects SET updated_at = CURRENT_TIMESTAMP(6) WHERE id = %s",
                    (project_id,),
                )
            conn.commit()
        return self.get_project_memory(username, project_id, memory_id)

    def update_project_memory(
        self,
        username: str,
        project_id: str,
        memory_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                project = self._project_for_user(cursor, username, project_id)
                if not project:
                    raise WorkbenchNotFoundError("项目不存在或当前用户无权访问")
                self._require_project_write(project)
                cursor.execute(
                    "SELECT id FROM workbench_project_memories WHERE id = %s AND project_id = %s",
                    (memory_id, project_id),
                )
                if not cursor.fetchone():
                    raise WorkbenchNotFoundError("项目记忆不存在")
                fields: list[str] = []
                params: list[Any] = []
                for field in ("category", "title", "content", "is_active"):
                    if field in changes:
                        fields.append(f"{field} = %s")
                        params.append(changes[field])
                fields.extend(["updated_by = %s", "updated_at = CURRENT_TIMESTAMP(6)"])
                params.extend([username, memory_id])
                cursor.execute(
                    f"UPDATE workbench_project_memories SET {', '.join(fields)} WHERE id = %s",
                    tuple(params),
                )
                cursor.execute(
                    "UPDATE workbench_projects SET updated_at = CURRENT_TIMESTAMP(6) WHERE id = %s",
                    (project_id,),
                )
            conn.commit()
        return self.get_project_memory(username, project_id, memory_id)

    def delete_project_memory(self, username: str, project_id: str, memory_id: str) -> dict[str, bool]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                project = self._project_for_user(cursor, username, project_id)
                if not project:
                    raise WorkbenchNotFoundError("项目不存在或当前用户无权访问")
                self._require_project_write(project)
                affected = cursor.execute(
                    "DELETE FROM workbench_project_memories WHERE id = %s AND project_id = %s",
                    (memory_id, project_id),
                )
                if not affected:
                    raise WorkbenchNotFoundError("项目记忆不存在")
                cursor.execute(
                    "UPDATE workbench_projects SET updated_at = CURRENT_TIMESTAMP(6) WHERE id = %s",
                    (project_id,),
                )
            conn.commit()
        return {"deleted": True}

    def get_project_memory_context(self, username: str, project_id: str, max_chars: int = 6000) -> str | None:
        memories = self.list_project_memories(username, project_id, include_inactive=False)
        if not memories:
            return None
        lines = ["以下内容是用户明确维护并启用的项目记忆，仅作为当前项目的长期上下文："]
        used = len(lines[0])
        labels = {
            "background": "背景",
            "goal": "目标",
            "constraint": "约束",
            "preference": "偏好",
            "conclusion": "结论",
            "other": "其他",
        }
        for memory in memories:
            line = f"- [{labels.get(memory['category'], '其他')}] {memory['title']}：{memory['content']}"
            remaining = max_chars - used
            if remaining <= 1:
                break
            if len(line) > remaining:
                lines.append(line[: remaining - 1] + "…")
                break
            lines.append(line)
            used += len(line)
        return "\n".join(lines) if len(lines) > 1 else None

    def list_project_members(self, username: str, project_id: str) -> list[dict[str, Any]]:
        self.get_project(username, project_id)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT pm.project_id, pm.username, pm.role, pm.created_at, pm.updated_at,
                              COALESCE(u.display_name, pm.username) AS display_name,
                              COALESCE(u.is_active, TRUE) AS is_active
                       FROM workbench_project_members pm
                       LEFT JOIN users u ON u.username COLLATE utf8mb4_unicode_ci = pm.username
                       WHERE pm.project_id = %s
                       ORDER BY FIELD(pm.role, 'owner', 'editor', 'viewer'), pm.created_at ASC""",
                    (project_id,),
                )
                rows = cursor.fetchall()
        return [_serialize_row(row) or {} for row in rows]

    def upsert_project_member(self, username: str, project_id: str, member_username: str, role: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                project = self._project_for_user(cursor, username, project_id)
                if not project:
                    raise WorkbenchNotFoundError("项目不存在或当前用户无权访问")
                self._require_project_owner(project)
                cursor.execute(
                    "SELECT username FROM users WHERE username = %s AND is_active = 1",
                    (member_username,),
                )
                if not cursor.fetchone():
                    raise WorkbenchNotFoundError("未找到可用的本地用户；当前版本不支持外部邀请")
                cursor.execute(
                    "SELECT role FROM workbench_project_members WHERE project_id = %s AND username = %s",
                    (project_id, member_username),
                )
                existing = cursor.fetchone()
                if existing and existing["role"] == "owner":
                    raise WorkbenchConflictError("不能通过成员编辑变更项目所有者")
                cursor.execute(
                    """INSERT INTO workbench_project_members (project_id, username, role)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE role = VALUES(role), updated_at = CURRENT_TIMESTAMP(6)""",
                    (project_id, member_username, role),
                )
                cursor.execute(
                    "UPDATE workbench_projects SET visibility = 'shared', updated_at = CURRENT_TIMESTAMP(6) WHERE id = %s",
                    (project_id,),
                )
            conn.commit()
        return next(
            member for member in self.list_project_members(username, project_id)
            if member["username"] == member_username
        )

    def remove_project_member(self, username: str, project_id: str, member_username: str) -> dict[str, bool]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                project = self._project_for_user(cursor, username, project_id)
                if not project:
                    raise WorkbenchNotFoundError("项目不存在或当前用户无权访问")
                self._require_project_owner(project)
                cursor.execute(
                    "SELECT role FROM workbench_project_members WHERE project_id = %s AND username = %s",
                    (project_id, member_username),
                )
                member = cursor.fetchone()
                if not member:
                    raise WorkbenchNotFoundError("项目成员不存在")
                if member["role"] == "owner":
                    raise WorkbenchConflictError("不能移除项目所有者")
                cursor.execute(
                    "DELETE FROM workbench_project_members WHERE project_id = %s AND username = %s",
                    (project_id, member_username),
                )
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM workbench_project_members WHERE project_id = %s AND role <> 'owner'",
                    (project_id,),
                )
                visibility = "shared" if cursor.fetchone()["cnt"] else "private"
                cursor.execute(
                    "UPDATE workbench_projects SET visibility = %s, updated_at = CURRENT_TIMESTAMP(6) WHERE id = %s",
                    (visibility, project_id),
                )
            conn.commit()
        return {"deleted": True}
