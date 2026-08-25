"""Persistent user-defined Skills for the custom workspace module."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Optional

from backend.repositories.workbench_repository import (
    WorkbenchNotFoundError,
    WorkbenchPermissionError,
    WorkbenchRepository,
    _serialize_row,
)


class SkillRepository(WorkbenchRepository):
    def _get_accessible(self, cursor: Any, username: str, skill_id: str) -> Optional[dict[str, Any]]:
        cursor.execute(
            """SELECT * FROM workbench_skills
               WHERE id = %s AND (owner_type = 'system' OR owner_username = %s)""",
            (skill_id, username),
        )
        return cursor.fetchone()

    @staticmethod
    def _skill(row: Optional[dict[str, Any]]) -> dict[str, Any]:
        result = _serialize_row(row) or {}
        if isinstance(result.get("input_schema_json"), str):
            result["input_schema_json"] = json.loads(result["input_schema_json"])
        return result

    @staticmethod
    def _require_owner(skill: dict[str, Any], username: str) -> None:
        if skill.get("owner_type") != "user" or skill.get("owner_username") != username:
            raise WorkbenchPermissionError("Only the creator can modify this Skill")

    def list_skills(self, username: str, query: str = "", scope: str = "all", status: Optional[str] = None) -> list[dict[str, Any]]:
        clauses = ["(owner_type = 'system' OR owner_username = %s)"]
        params: list[Any] = [username]
        if scope == "mine":
            clauses.append("owner_username = %s")
            params.append(username)
        elif scope == "system":
            clauses.append("owner_type = 'system'")
        if status:
            clauses.append("status = %s")
            params.append(status)
        if query:
            clauses.append("(name LIKE %s OR description LIKE %s)")
            params.extend([f"%{query}%", f"%{query}%"])
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT * FROM workbench_skills WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC, id DESC",
                    tuple(params),
                )
                rows = cursor.fetchall()
        return [self._skill(row) for row in rows]

    def list_chat_skills(self, username: str, skill_ids: list[str]) -> list[dict[str, Any]]:
        """Return only the caller's published Skills selected for one message."""
        if not skill_ids:
            return []
        placeholders = ", ".join(["%s"] * len(skill_ids))
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT * FROM workbench_skills
                        WHERE id IN ({placeholders})
                          AND owner_type = 'user'
                          AND owner_username = %s
                          AND status = 'published'""",
                    (*skill_ids, username),
                )
                rows = cursor.fetchall()
        resolved = {row["id"]: self._skill(row) for row in rows}
        if len(resolved) != len(skill_ids):
            raise WorkbenchNotFoundError("Selected Skill is unavailable")
        return [resolved[skill_id] for skill_id in skill_ids]

    def get_skill(self, username: str, skill_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                skill = self._get_accessible(cursor, username, skill_id)
        if not skill:
            raise WorkbenchNotFoundError("Skill not found")
        result = self._skill(skill)
        result["attachments"] = self.list_attachments(username, skill_id)
        return result

    def list_attachments(self, username: str, skill_id: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                if not self._get_accessible(cursor, username, skill_id):
                    raise WorkbenchNotFoundError("Skill not found")
                cursor.execute("SELECT id, original_filename, content_type, size_bytes, created_at FROM workbench_skill_attachments WHERE skill_id = %s ORDER BY created_at ASC", (skill_id,))
                rows = cursor.fetchall()
        return [_serialize_row(row) or {} for row in rows]

    def create_attachment(self, username: str, skill_id: str, filename: str, content_type: str | None, content: bytes) -> dict[str, Any]:
        attachment_id, suffix = str(uuid.uuid4()), Path(filename).suffix.lower()
        stored_name = f"{attachment_id}{suffix}"
        with self._connection() as conn:
            with conn.cursor() as cursor:
                skill = self._get_accessible(cursor, username, skill_id)
                if not skill:
                    raise WorkbenchNotFoundError("Skill not found")
                self._require_owner(skill, username)
                cursor.execute("INSERT INTO workbench_skill_attachments (id, skill_id, original_filename, stored_filename, content_type, size_bytes, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s)", (attachment_id, skill_id, filename, stored_name, content_type, len(content), username))
            conn.commit()
        folder = Path(__file__).resolve().parents[2] / "data" / "skill_attachments" / skill_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / stored_name).write_bytes(content)
        return {"id": attachment_id, "original_filename": filename, "content_type": content_type, "size_bytes": len(content)}

    def delete_attachment(self, username: str, skill_id: str, attachment_id: str) -> dict[str, bool]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                skill = self._get_accessible(cursor, username, skill_id)
                if not skill:
                    raise WorkbenchNotFoundError("Skill not found")
                self._require_owner(skill, username)
                cursor.execute("SELECT stored_filename FROM workbench_skill_attachments WHERE id = %s AND skill_id = %s", (attachment_id, skill_id))
                attachment = cursor.fetchone()
                if not attachment:
                    raise WorkbenchNotFoundError("Attachment not found")
                cursor.execute("DELETE FROM workbench_skill_attachments WHERE id = %s", (attachment_id,))
            conn.commit()
        path = Path(__file__).resolve().parents[2] / "data" / "skill_attachments" / skill_id / attachment["stored_filename"]
        path.unlink(missing_ok=True)
        return {"deleted": True}

    def create_skill(self, username: str, payload: dict[str, Any]) -> dict[str, Any]:
        skill_id = str(uuid.uuid4())
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO workbench_skills
                       (id, owner_username, owner_type, name, description, instructions, input_schema_json, output_format, status)
                       VALUES (%s, %s, 'user', %s, %s, %s, %s, %s, %s)""",
                    (skill_id, username, payload["name"], payload["description"], payload["instructions"],
                     json.dumps(payload.get("input_schema", []), ensure_ascii=False), payload["output_format"], payload["status"]),
                )
                self._snapshot(cursor, skill_id, 1, payload, username)
            conn.commit()
        return self.get_skill(username, skill_id)

    def _snapshot(self, cursor: Any, skill_id: str, version: int, payload: dict[str, Any], username: str) -> None:
        cursor.execute(
            """INSERT INTO workbench_skill_versions
                 (skill_id, version_no, name, description, instructions, input_schema_json, output_format, status, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (skill_id, version, payload["name"], payload["description"], payload["instructions"],
             json.dumps(payload.get("input_schema", []), ensure_ascii=False), payload["output_format"], payload["status"], username),
        )

    def update_skill(self, username: str, skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                skill = self._get_accessible(cursor, username, skill_id)
                if not skill:
                    raise WorkbenchNotFoundError("Skill not found")
                self._require_owner(skill, username)
                version = int(skill["version_no"]) + 1
                cursor.execute(
                    """UPDATE workbench_skills SET name=%s, description=%s, instructions=%s, input_schema_json=%s,
                       output_format=%s, status=%s, version_no=%s, archived_at=IF(%s='archived', NOW(6), NULL), updated_at=NOW(6)
                       WHERE id=%s""",
                    (payload["name"], payload["description"], payload["instructions"], json.dumps(payload.get("input_schema", []), ensure_ascii=False),
                     payload["output_format"], payload["status"], version, payload["status"], skill_id),
                )
                self._snapshot(cursor, skill_id, version, payload, username)
            conn.commit()
        return self.get_skill(username, skill_id)

    def archive_skill(self, username: str, skill_id: str) -> dict[str, Any]:
        skill = self.get_skill(username, skill_id)
        return self.update_skill(username, skill_id, {**skill, "input_schema": skill.get("input_schema_json", []), "status": "archived"})

    def activate_skill(self, username: str, skill_id: str) -> dict[str, Any]:
        """Restore an archived personal Skill as a published, usable version."""
        skill = self.get_skill(username, skill_id)
        return self.update_skill(username, skill_id, {**skill, "input_schema": skill.get("input_schema_json", []), "status": "published"})

    def delete_skill(self, username: str, skill_id: str) -> dict[str, bool]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                skill = self._get_accessible(cursor, username, skill_id)
                if not skill:
                    raise WorkbenchNotFoundError("Skill not found")
                self._require_owner(skill, username)
                if skill.get("status") != "archived":
                    raise WorkbenchPermissionError("Only archived Skills can be deleted")
                cursor.execute("DELETE FROM workbench_skills WHERE id = %s", (skill_id,))
            conn.commit()
        return {"deleted": True}
