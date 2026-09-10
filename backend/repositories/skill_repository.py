"""Persistent user-defined Skills for the custom workspace module."""

from __future__ import annotations

import json
import logging
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from backend.repositories.workbench_repository import (
    WorkbenchConflictError,
    WorkbenchNotFoundError,
    WorkbenchPermissionError,
    WorkbenchRepository,
    _serialize_row,
)
from backend.services.skill_attachment_parser import AttachmentParseError, parse_attachment

logger = logging.getLogger(__name__)
ATTACHMENT_LIMIT = 8
ATTACHMENT_ROOT = Path(__file__).resolve().parents[2] / "data" / "skill_attachments"
MAX_SELECTED_SKILLS = 3
MAX_SKILL_INSTRUCTION_CHARS = 4000
MAX_SELECTED_INSTRUCTION_CHARS = 8000
MAX_ATTACHMENT_CONTEXT_CHARS = 12000
MAX_ATTACHMENT_CONTEXT_CHUNKS = 8
MAX_CONTEXT_CHUNKS_PER_ATTACHMENT = 3


class SkillRepository(WorkbenchRepository):
    """用户自定义 Skill 与其附件的持久化访问。"""

    def _get_accessible(
        self,
        cursor: Any,
        username: str,
        skill_id: str,
        *,
        for_update: bool = False,
    ) -> dict[str, Any] | None:
        cursor.execute(
            """SELECT * FROM workbench_skills
               WHERE id = %s
                 AND ((owner_type = 'system' AND status = 'published') OR owner_username = %s)"""
            + (" FOR UPDATE" if for_update else ""),
            (skill_id, username),
        )
        return cursor.fetchone()

    @staticmethod
    def _skill(row: dict[str, Any] | None) -> dict[str, Any]:
        """序列化技能行（``input_schema_json`` 已由 ``serialize_row`` 解析为结构）。"""
        return _serialize_row(row) or {}

    @staticmethod
    def _require_owner(skill: dict[str, Any], username: str) -> None:
        if skill.get("owner_type") != "user" or skill.get("owner_username") != username:
            raise WorkbenchPermissionError("Only the creator can modify this Skill")

    def list_skills(self, username: str, query: str = "", scope: str = "all", status: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope == "mine":
            clauses.append("s.owner_type = 'user' AND s.owner_username = %s")
            params.append(username)
        elif scope == "system":
            clauses.append("s.owner_type = 'system' AND s.status = 'published'")
        else:
            clauses.append("((s.owner_type = 'system' AND s.status = 'published') OR (s.owner_type = 'user' AND s.owner_username = %s))")
            params.append(username)
        if status:
            clauses.append("s.status = %s")
            params.append(status)
        if query:
            clauses.append("(s.name LIKE %s OR s.description LIKE %s)")
            params.extend([f"%{query}%", f"%{query}%"])
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT s.*,
                               CASE
                                   WHEN s.owner_type = 'system' THEN CASE WHEN uss.username IS NULL THEN 0 ELSE 1 END
                                   WHEN s.status = 'published' THEN 1
                                   ELSE 0
                               END AS is_enabled
                          FROM workbench_skills s
                          LEFT JOIN workbench_user_system_skills uss
                            ON uss.skill_id = s.id AND uss.username = %s
                         WHERE {' AND '.join(clauses)}
                         ORDER BY s.updated_at DESC, s.id DESC""",
                    (username, *params),
                )
                rows = cursor.fetchall()
        return [self._skill(row) for row in rows]

    def list_chat_options(self, username: str) -> list[dict[str, Any]]:
        """Return the caller's currently usable system and personal Skills."""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT s.*,
                              1 AS is_enabled
                         FROM workbench_skills s
                        WHERE s.status = 'published'
                          AND (
                              (s.owner_type = 'user' AND s.owner_username = %s)
                              OR (
                                  s.owner_type = 'system'
                                  AND EXISTS (
                                      SELECT 1 FROM workbench_user_system_skills uss
                                       WHERE uss.username = %s AND uss.skill_id = s.id
                                  )
                              )
                          )
                        ORDER BY s.owner_type ASC, s.updated_at DESC, s.id DESC""",
                    (username, username),
                )
                rows = cursor.fetchall()
        return [self._skill(row) for row in rows]

    def list_chat_skills(self, username: str, skill_ids: list[str]) -> list[dict[str, Any]]:
        """Resolve and revalidate Skills selected for one message."""
        if not skill_ids:
            return []
        if len(skill_ids) > MAX_SELECTED_SKILLS:
            raise WorkbenchConflictError(f"单条消息最多选择 {MAX_SELECTED_SKILLS} 个 Skill")
        placeholders = ", ".join(["%s"] * len(skill_ids))
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT * FROM workbench_skills
                        WHERE id IN ({placeholders})
                          AND status = 'published'
                          AND (
                              (owner_type = 'user' AND owner_username = %s)
                              OR (
                                  owner_type = 'system'
                                  AND EXISTS (
                                      SELECT 1 FROM workbench_user_system_skills uss
                                       WHERE uss.username = %s AND uss.skill_id = workbench_skills.id
                                  )
                              )
                          )""",
                    (*skill_ids, username, username),
                )
                rows = cursor.fetchall()
        resolved = {row["id"]: self._skill(row) for row in rows}
        if len(resolved) != len(skill_ids):
            raise WorkbenchNotFoundError("所选 Skill 不存在、未启用或当前用户不可用")
        selected = [resolved[skill_id] for skill_id in skill_ids]
        if len({skill["output_format"] for skill in selected}) > 1:
            raise WorkbenchConflictError("Markdown 与纯文本 Skill 不能在同一条消息中混用")
        if any(len(str(skill.get("instructions") or "")) > MAX_SKILL_INSTRUCTION_CHARS for skill in selected):
            raise WorkbenchConflictError(f"单个 Skill 的指令不能超过 {MAX_SKILL_INSTRUCTION_CHARS} 个字符")
        if sum(len(str(skill.get("instructions") or "")) for skill in selected) > MAX_SELECTED_INSTRUCTION_CHARS:
            raise WorkbenchConflictError(f"所选 Skill 的指令合计不能超过 {MAX_SELECTED_INSTRUCTION_CHARS} 个字符")
        return selected

    def enable_system_skill(self, username: str, skill_id: str) -> dict[str, Any]:
        skill = self.get_skill(username, skill_id)
        if skill.get("owner_type") != "system" or skill.get("status") != "published":
            raise WorkbenchNotFoundError("系统 Skill 不存在或未启用")
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO workbench_user_system_skills (username, skill_id)
                       VALUES (%s, %s)
                       ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP(6)""",
                    (username, skill_id),
                )
            conn.commit()
        return {**skill, "is_enabled": True}

    def disable_system_skill(self, username: str, skill_id: str) -> dict[str, bool]:
        skill = self.get_skill(username, skill_id)
        if skill.get("owner_type") != "system":
            raise WorkbenchNotFoundError("系统 Skill 不存在")
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM workbench_user_system_skills WHERE username = %s AND skill_id = %s",
                    (username, skill_id),
                )
            conn.commit()
        return {"disabled": True}

    def get_skill(self, username: str, skill_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                skill = self._get_accessible(cursor, username, skill_id)
                is_enabled = False
                if skill and skill.get("owner_type") == "system":
                    cursor.execute(
                        "SELECT 1 FROM workbench_user_system_skills WHERE username = %s AND skill_id = %s",
                        (username, skill_id),
                    )
                    is_enabled = cursor.fetchone() is not None
        if not skill:
            raise WorkbenchNotFoundError("Skill not found")
        result = self._skill(skill)
        result["is_enabled"] = is_enabled if result.get("owner_type") == "system" else result.get("status") == "published"
        result["attachments"] = self.list_attachments(username, skill_id)
        return result

    def list_attachments(self, username: str, skill_id: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                if not self._get_accessible(cursor, username, skill_id):
                    raise WorkbenchNotFoundError("Skill not found")
                cursor.execute(
                    """SELECT id, original_filename, content_type, size_bytes, parse_status,
                              parse_error, page_count, parsed_at, created_at
                       FROM workbench_skill_attachments WHERE skill_id = %s ORDER BY created_at ASC""",
                    (skill_id,),
                )
                rows = cursor.fetchall()
        return [_serialize_row(row) or {} for row in rows]

    def create_attachment(self, username: str, skill_id: str, filename: str, content_type: str | None, content: bytes) -> dict[str, Any]:
        attachment_id, suffix = str(uuid.uuid4()), Path(filename).suffix.lower()
        stored_name = f"{attachment_id}{suffix}"
        folder = ATTACHMENT_ROOT / skill_id
        path = folder / stored_name
        file_written = False
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    skill = self._get_accessible(cursor, username, skill_id, for_update=True)
                    if not skill:
                        raise WorkbenchNotFoundError("Skill not found")
                    self._require_owner(skill, username)
                    cursor.execute(
                        "SELECT COUNT(*) AS count FROM workbench_skill_attachments WHERE skill_id = %s",
                        (skill_id,),
                    )
                    if int(cursor.fetchone()["count"]) >= ATTACHMENT_LIMIT:
                        raise WorkbenchConflictError(f"每个 Skill 最多上传 {ATTACHMENT_LIMIT} 个附件")
                    folder.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                    file_written = True
                    cursor.execute(
                        """INSERT INTO workbench_skill_attachments
                           (id, skill_id, original_filename, stored_filename, content_type, size_bytes, parse_status, created_by)
                           VALUES (%s,%s,%s,%s,%s,%s,'pending',%s)""",
                        (attachment_id, skill_id, filename, stored_name, content_type, len(content), username),
                    )
                conn.commit()
        except BaseException:
            if file_written:
                path.unlink(missing_ok=True)
            raise
        self._parse_attachment(attachment_id, skill_id, path, filename)
        return next(item for item in self.list_attachments(username, skill_id) if item["id"] == attachment_id)

    def _parse_attachment(self, attachment_id: str, skill_id: str, path: Path, filename: str) -> None:
        """Parse a saved attachment and persist chunks; upload remains successful on parse failure."""
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE workbench_skill_attachments SET parse_status='parsing', parse_error=NULL WHERE id=%s",
                        (attachment_id,),
                    )
                conn.commit()
            parsed = parse_attachment(path, filename)
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM workbench_skill_attachment_chunks WHERE attachment_id=%s", (attachment_id,))
                    for chunk in parsed.chunks:
                        cursor.execute(
                            """INSERT INTO workbench_skill_attachment_chunks
                               (attachment_id, skill_id, source_location, chunk_index, content)
                               VALUES (%s,%s,%s,%s,%s)""",
                            (
                                attachment_id,
                                skill_id,
                                chunk["source_location"],
                                chunk["chunk_index"],
                                chunk["content"],
                            ),
                        )
                    cursor.execute(
                        """UPDATE workbench_skill_attachments
                           SET parse_status='ready', parse_error=NULL, page_count=%s, parsed_at=NOW(6)
                           WHERE id=%s""",
                        (parsed.page_count, attachment_id),
                    )
                conn.commit()
        except Exception as exc:
            message = str(exc) if isinstance(exc, AttachmentParseError) else f"附件解析失败：{type(exc).__name__}"
            logger.warning("Skill attachment parsing failed for %s: %s", attachment_id, message)
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """UPDATE workbench_skill_attachments
                           SET parse_status='failed', parse_error=%s, page_count=NULL, parsed_at=NOW(6)
                           WHERE id=%s""",
                        (message[:1000], attachment_id),
                    )
                conn.commit()

    @staticmethod
    def _query_terms(query: str) -> list[str]:
        lowered = query.lower()
        terms = re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", lowered)
        expanded: list[str] = []
        for term in terms:
            expanded.append(term)
            if re.fullmatch(r"[\u4e00-\u9fff]+", term) and len(term) > 2:
                expanded.extend(term[index : index + 2] for index in range(len(term) - 1))
        return list(dict.fromkeys(expanded))

    def get_attachment_context(
        self,
        username: str,
        selected_skills: list[dict[str, Any]],
        query: str,
        char_budget: int = MAX_ATTACHMENT_CONTEXT_CHARS,
    ) -> str:
        """Select a small, relevant set of parsed chunks for the chosen personal Skills."""
        personal_ids = [skill["id"] for skill in selected_skills if skill.get("owner_type") == "user"]
        if not personal_ids or char_budget <= 0:
            return ""
        placeholders = ", ".join(["%s"] * len(personal_ids))
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT c.attachment_id, c.chunk_index, c.source_location, c.content,
                               a.original_filename, a.parse_status
                          FROM workbench_skill_attachments a
                          JOIN workbench_skills s ON s.id = a.skill_id
                          LEFT JOIN workbench_skill_attachment_chunks c ON c.attachment_id = a.id
                         WHERE a.skill_id IN ({placeholders})
                           AND s.owner_type = 'user' AND s.owner_username = %s
                         ORDER BY a.id, c.chunk_index""",
                    (*personal_ids, username),
                )
                rows = cursor.fetchall()
        rows = [row for row in rows if row.get("content")]
        if not rows:
            return "[附件状态] 所选个人 Skill 的附件尚无可用解析内容，本次回答仅使用 Skill 指令。"
        terms = self._query_terms(query)

        def relevance(row: dict[str, Any]) -> tuple[int, int]:
            content = str(row.get("content") or "").lower()
            score = sum((3 if len(term) > 2 else 1) * content.count(term) for term in terms)
            return score, -int(row.get("chunk_index") or 0)

        ranked = sorted(rows, key=relevance, reverse=True)
        selected: list[str] = []
        seen: set[str] = set()
        per_attachment: dict[str, int] = {}
        used = 0
        for row in ranked:
            attachment_id = str(row["attachment_id"])
            content = str(row.get("content") or "").strip()
            if not content or content in seen or per_attachment.get(attachment_id, 0) >= MAX_CONTEXT_CHUNKS_PER_ATTACHMENT:
                continue
            block = f"[文件：{row['original_filename']}，{row['source_location']}]\n{content}"
            remaining = char_budget - used
            if remaining <= 0 or len(selected) >= MAX_ATTACHMENT_CONTEXT_CHUNKS:
                break
            if len(block) > remaining:
                if remaining < 200:
                    break
                block = block[:remaining].rstrip() + "…"
            selected.append(block)
            seen.add(content)
            per_attachment[attachment_id] = per_attachment.get(attachment_id, 0) + 1
            used += len(block) + 2
        return "\n\n".join(selected)

    def delete_attachment(self, username: str, skill_id: str, attachment_id: str) -> dict[str, bool]:
        trashed_path: Path | None = None
        original_path: Path | None = None
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    skill = self._get_accessible(cursor, username, skill_id, for_update=True)
                    if not skill:
                        raise WorkbenchNotFoundError("Skill not found")
                    self._require_owner(skill, username)
                    cursor.execute(
                        "SELECT stored_filename FROM workbench_skill_attachments WHERE id = %s AND skill_id = %s",
                        (attachment_id, skill_id),
                    )
                    attachment = cursor.fetchone()
                    if not attachment:
                        raise WorkbenchNotFoundError("Attachment not found")
                    original_path = ATTACHMENT_ROOT / skill_id / attachment["stored_filename"]
                    if original_path.exists():
                        trash = ATTACHMENT_ROOT / ".trash"
                        trash.mkdir(parents=True, exist_ok=True)
                        trashed_path = trash / f"{attachment_id}-{uuid.uuid4().hex}"
                        original_path.replace(trashed_path)
                    cursor.execute("DELETE FROM workbench_skill_attachments WHERE id = %s", (attachment_id,))
                conn.commit()
        except BaseException:
            if trashed_path and trashed_path.exists() and original_path:
                original_path.parent.mkdir(parents=True, exist_ok=True)
                trashed_path.replace(original_path)
            raise
        if trashed_path:
            trashed_path.unlink(missing_ok=True)
        folder = ATTACHMENT_ROOT / skill_id
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()
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
        folder = ATTACHMENT_ROOT / skill_id
        trashed_folder: Path | None = None
        try:
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    skill = self._get_accessible(cursor, username, skill_id, for_update=True)
                    if not skill:
                        raise WorkbenchNotFoundError("Skill not found")
                    self._require_owner(skill, username)
                    if skill.get("status") != "archived":
                        raise WorkbenchPermissionError("Only archived Skills can be deleted")
                    if folder.exists():
                        trash = ATTACHMENT_ROOT / ".trash"
                        trash.mkdir(parents=True, exist_ok=True)
                        trashed_folder = trash / f"{skill_id}-{uuid.uuid4().hex}"
                        folder.replace(trashed_folder)
                    cursor.execute("DELETE FROM workbench_skills WHERE id = %s", (skill_id,))
                conn.commit()
        except BaseException:
            if trashed_folder and trashed_folder.exists():
                folder.parent.mkdir(parents=True, exist_ok=True)
                trashed_folder.replace(folder)
            raise
        if trashed_folder:
            try:
                shutil.rmtree(trashed_folder)
            except OSError:
                logger.exception("Failed to purge deleted Skill attachment folder: %s", trashed_folder)
        return {"deleted": True}
