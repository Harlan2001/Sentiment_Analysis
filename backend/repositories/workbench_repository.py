"""工作台项目、会话与消息持久化。"""

from __future__ import annotations

import base64
import json
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, Optional

import pymysql
from pymysql.cursors import DictCursor

from backend.config.config import MYSQL_CONFIG


class WorkbenchNotFoundError(RuntimeError):
    """资源不存在或当前用户无权访问。"""


class WorkbenchPermissionError(RuntimeError):
    """当前用户缺少写入权限。"""


class WorkbenchConflictError(RuntimeError):
    """会话状态或幂等键冲突。"""


class WorkbenchCursorError(ValueError):
    """分页游标格式无效。"""


def _serialize_row(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    result: dict[str, Any] = {}
    for key, value in row.items():
        result[key] = value.isoformat() if isinstance(value, (datetime, date)) else value
    return result


def _encode_cursor(sort_value: Any, item_id: str) -> str:
    if isinstance(sort_value, (datetime, date)):
        sort_value = sort_value.isoformat()
    raw = json.dumps([sort_value, item_id], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: Optional[str]) -> Optional[tuple[str, str]]:
    if not cursor:
        return None
    try:
        value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode())
        if not isinstance(value, list) or len(value) != 2 or not all(isinstance(item, str) for item in value):
            raise ValueError
        return value[0], value[1]
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkbenchCursorError("分页游标无效") from exc


class WorkbenchRepository:
    """新版工作台仓储，仅操作 workbench_* 表。"""

    @classmethod
    def from_environment(cls) -> "WorkbenchRepository":
        return cls(dict(MYSQL_CONFIG))

    def __init__(self, settings: dict[str, Any]):
        self._settings = settings

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        connection = pymysql.connect(**{**self._settings, "autocommit": False}, cursorclass=DictCursor)
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ensure_tables(self) -> None:
        """启动时应用工作台自己的迁移，不影响旧表。按文件顺序执行所有迁移。"""
        migration_dir = Path(__file__).resolve().parents[2] / "sql"
        # 飞书 OAuth 仍保留为未来真实接入的代码雏形，但当前 MCP 页面不使用它；
        # 因此不应在切换生产库时自动创建 OAuth 状态、令牌或审计表。
        script_paths = [
            path for path in sorted(migration_dir.glob("*_workbench_*.sql"))
            if path.name != "005_workbench_feishu_mcp.sql"
        ]
        with self._connection() as conn:
            with conn.cursor() as cursor:
                for script_path in script_paths:
                    text = script_path.read_text(encoding="utf-8")
                    statements = [item.strip() for item in text.split(";") if item.strip()]
                    for statement in statements:
                        upper = statement.upper()
                        if upper.startswith("ALTER TABLE") and "ADD COLUMN" in upper:
                            table_end = upper.find("ADD COLUMN")
                            table_part = upper[len("ALTER TABLE "):table_end].strip().split()[0]
                            col_start = upper.find("ADD COLUMN") + len("ADD COLUMN ")
                            col_name = upper[col_start:].split()[0].strip()
                            cursor.execute(
                                """SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.COLUMNS
                                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
                                (table_part, col_name),
                            )
                            if cursor.fetchone()["cnt"] > 0:
                                continue
                        try:
                            cursor.execute(statement)
                        except pymysql.err.OperationalError:
                            # 列/表已存在（幂等）
                            pass
            conn.commit()

    @staticmethod
    def _project_for_user(cursor, username: str, project_id: str) -> Optional[dict[str, Any]]:
        cursor.execute(
            """SELECT p.*, pm.role
               FROM workbench_projects p
               INNER JOIN workbench_project_members pm ON pm.project_id = p.id
               WHERE p.id = %s AND pm.username = %s AND p.deleted_at IS NULL""",
            (project_id, username),
        )
        return cursor.fetchone()

    @staticmethod
    def _conversation_for_user(cursor, username: str, conversation_id: str) -> Optional[dict[str, Any]]:
        cursor.execute(
            """SELECT c.*, pm.role AS project_role
               FROM workbench_conversations c
               LEFT JOIN workbench_project_members pm
                 ON pm.project_id = c.project_id AND pm.username = %s
               WHERE c.id = %s
                 AND c.deleted_at IS NULL
                 AND ((c.project_id IS NULL AND c.owner_username = %s)
                      OR (c.project_id IS NOT NULL AND pm.username IS NOT NULL))""",
            (username, conversation_id, username),
        )
        return cursor.fetchone()

    @staticmethod
    def _require_project_write(project: dict[str, Any]) -> None:
        if project.get("role") not in {"owner", "editor"}:
            raise WorkbenchPermissionError("当前用户没有项目写入权限")

    @staticmethod
    def _require_conversation_write(conversation: dict[str, Any], username: str) -> None:
        if conversation.get("project_id") and conversation.get("project_role") not in {"owner", "editor"}:
            raise WorkbenchPermissionError("当前用户没有项目会话写入权限")
        if not conversation.get("project_id") and conversation.get("owner_username") != username:
            raise WorkbenchPermissionError("当前用户没有会话写入权限")

    def create_project(self, username: str, name: str, description: Optional[str]) -> dict[str, Any]:
        project_id = str(uuid.uuid4())
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO workbench_projects (id, owner_username, name, description, visibility)
                       VALUES (%s, %s, %s, %s, 'private')""",
                    (project_id, username, name, description),
                )
                cursor.execute(
                    """INSERT INTO workbench_project_members (project_id, username, role)
                       VALUES (%s, %s, 'owner')""",
                    (project_id, username),
                )
            conn.commit()
        return self.get_project(username, project_id)

    def get_project(self, username: str, project_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                project = self._project_for_user(cursor, username, project_id)
        if not project:
            raise WorkbenchNotFoundError("项目不存在或当前用户无权访问")
        project["unread_count"] = 0
        return _serialize_row(project) or {}

    def list_projects(self, username: str, limit: int, cursor: Optional[str] = None) -> dict[str, Any]:
        decoded = _decode_cursor(cursor)
        params: list[Any] = [username]
        page_sql = ""
        if decoded:
            page_sql = "AND (p.updated_at < %s OR (p.updated_at = %s AND p.id < %s))"
            params.extend([decoded[0], decoded[0], decoded[1]])
        params.append(limit + 1)
        with self._connection() as conn:
            with conn.cursor() as db_cursor:
                db_cursor.execute(
                    f"""SELECT p.*, pm.role
                         FROM workbench_projects p
                         INNER JOIN workbench_project_members pm ON pm.project_id = p.id
                         WHERE pm.username = %s AND p.deleted_at IS NULL {page_sql}
                         ORDER BY p.updated_at DESC, p.id DESC
                         LIMIT %s""",
                    tuple(params),
                )
                rows = db_cursor.fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        for row in rows:
            row["unread_count"] = 0
        return {
            "items": [_serialize_row(row) for row in rows],
            "next_cursor": _encode_cursor(rows[-1]["updated_at"], rows[-1]["id"]) if has_more and rows else None,
        }

    def update_project(self, username: str, project_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                project = self._project_for_user(cursor, username, project_id)
                if not project:
                    raise WorkbenchNotFoundError("项目不存在或当前用户无权访问")
                self._require_project_write(project)
                fields = []
                params: list[Any] = []
                for field in ("name", "description"):
                    if field in changes:
                        fields.append(f"{field} = %s")
                        params.append(changes[field])
                fields.append("updated_at = CURRENT_TIMESTAMP(6)")
                params.append(project_id)
                cursor.execute(f"UPDATE workbench_projects SET {', '.join(fields)} WHERE id = %s", tuple(params))
            conn.commit()
        return self.get_project(username, project_id)

    def soft_delete_project(self, username: str, project_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                project = self._project_for_user(cursor, username, project_id)
                if not project:
                    raise WorkbenchNotFoundError("项目不存在或当前用户无权访问")
                if project.get("role") != "owner":
                    raise WorkbenchPermissionError("只有项目所有者才能删除项目")
                cursor.execute(
                    "UPDATE workbench_projects SET deleted_at = NOW(6) WHERE id = %s",
                    (project_id,),
                )
                cursor.execute(
                    """UPDATE workbench_conversations
                         SET deleted_at = NOW(6)
                       WHERE project_id = %s AND deleted_at IS NULL""",
                    (project_id,),
                )
            conn.commit()
        return {"deleted": True}

    def restore_project(self, username: str, project_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT p.*, pm.role
                       FROM workbench_projects p
                       INNER JOIN workbench_project_members pm ON pm.project_id = p.id
                       WHERE p.id = %s AND pm.username = %s AND p.deleted_at IS NOT NULL""",
                    (project_id, username),
                )
                project = cursor.fetchone()
                if not project:
                    raise WorkbenchNotFoundError("项目不存在或当前用户无权访问")
                if project.get("role") != "owner":
                    raise WorkbenchPermissionError("只有项目所有者才能恢复项目")
                cursor.execute(
                    "UPDATE workbench_projects SET deleted_at = NULL WHERE id = %s",
                    (project_id,),
                )
                cursor.execute(
                    """UPDATE workbench_conversations
                         SET deleted_at = NULL
                       WHERE project_id = %s""",
                    (project_id,),
                )
            conn.commit()
        return self.get_project(username, project_id)

    def permanently_delete_project(self, username: str, project_id: str) -> dict[str, bool]:
        """Permanently remove a project already placed in the recycle bin."""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT p.id, pm.role FROM workbench_projects p
                       INNER JOIN workbench_project_members pm ON pm.project_id = p.id
                       WHERE p.id = %s AND pm.username = %s AND p.deleted_at IS NOT NULL""",
                    (project_id, username),
                )
                project = cursor.fetchone()
                if not project:
                    raise WorkbenchNotFoundError("项目不存在或不在最近删除中")
                if project.get("role") != "owner":
                    raise WorkbenchPermissionError("只有项目所有者才能永久删除项目")
                # The conversation FK is RESTRICT, while messages cascade from conversations.
                cursor.execute("DELETE FROM workbench_conversations WHERE project_id = %s", (project_id,))
                cursor.execute("DELETE FROM workbench_project_memories WHERE project_id = %s", (project_id,))
                cursor.execute("DELETE FROM workbench_projects WHERE id = %s", (project_id,))
            conn.commit()
        return {"deleted": True}

    def create_conversation(self, username: str, project_id: Optional[str], title: Optional[str], source: str) -> dict[str, Any]:
        conversation_id = str(uuid.uuid4())
        with self._connection() as conn:
            with conn.cursor() as cursor:
                if project_id:
                    project = self._project_for_user(cursor, username, project_id)
                    if not project:
                        raise WorkbenchNotFoundError("项目不存在或当前用户无权访问")
                    self._require_project_write(project)
                cursor.execute(
                    """INSERT INTO workbench_conversations
                         (id, owner_username, project_id, title, module_type, source, status)
                       VALUES (%s, %s, %s, %s, 'chat', %s, 'active')""",
                    (conversation_id, username, project_id, title, source),
                )
                if project_id:
                    cursor.execute("UPDATE workbench_projects SET updated_at = CURRENT_TIMESTAMP(6) WHERE id = %s", (project_id,))
            conn.commit()
        return self.get_conversation(username, conversation_id)

    def get_conversation(self, username: str, conversation_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                conversation = self._conversation_for_user(cursor, username, conversation_id)
        if not conversation:
            raise WorkbenchNotFoundError("会话不存在或当前用户无权访问")
        conversation.pop("project_role", None)
        return _serialize_row(conversation) or {}
