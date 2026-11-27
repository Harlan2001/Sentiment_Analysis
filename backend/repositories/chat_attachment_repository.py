"""Text evidence attached to an Agent conversation message."""

from __future__ import annotations

import logging
import re
import shutil
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from backend.repositories.workbench_repository import (
    WorkbenchConflictError,
    WorkbenchNotFoundError,
    WorkbenchRepository,
    _serialize_row,
)
from backend.services.skill_attachment_parser import parse_attachment

ATTACHMENT_ROOT = Path(__file__).resolve().parents[2] / "data" / "chat_attachments"
MAX_CHAT_ATTACHMENT_BYTES = 10 * 1024 * 1024
CHAT_ATTACHMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv"}
MAX_CONTEXT_CHARS = 24000
MAX_CONTEXT_CHUNKS = 16
logger = logging.getLogger(__name__)


def purge_conversation_files(conversation_id: str) -> None:
    """Remove attachment blobs after a conversation is permanently deleted."""
    root = ATTACHMENT_ROOT.resolve()
    folder = (root / uuid.uuid5(uuid.NAMESPACE_URL, conversation_id).hex).resolve()
    if folder.parent == root:
        try:
            shutil.rmtree(folder)
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning("Failed to remove chat attachment folder for %s", conversation_id, exc_info=True)


def select_chat_attachment_context(
    rows: list[dict[str, Any]], query: str, char_budget: int = MAX_CONTEXT_CHARS
) -> str:
    """Choose cited excerpts with both query relevance and broad file coverage."""
    if not rows or char_budget < 200:
        return ""
    terms = re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", query.lower())
    by_file: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        by_file.setdefault(str(row["attachment_id"]), []).append(index)

    priority: list[int] = []
    # A whole-document question needs evidence from more than the opening paragraph.
    for indices in by_file.values():
        for fraction in (0, 0.25, 0.5, 0.75, 1):
            priority.append(indices[round((len(indices) - 1) * fraction)])

    def relevance(index: int) -> tuple[int, int]:
        content = str(rows[index]["content"]).lower()
        return (sum(content.count(term) for term in terms), -index)

    priority.extend(sorted(range(len(rows)), key=relevance, reverse=True))
    selected: list[str] = []
    used_indices: set[int] = set()
    used_chars = 0
    for index in priority:
        if index in used_indices or len(selected) >= MAX_CONTEXT_CHUNKS:
            continue
        row = rows[index]
        block = f"[文件：{row['original_filename']}，{row['source_location']}]\n{row['content']}"
        if used_chars + len(block) + 2 > char_budget - 120:
            continue
        selected.append(block)
        used_indices.add(index)
        used_chars += len(block) + 2
    if not selected:
        return ""
    header = (
        f"[附件覆盖范围] 本次检索中已提供 {len(selected)}/{len(rows)} 个文本片段，"
        "仅依据提供的片段作答；未覆盖的页码、段落、图表和公式应标为待核实。"
    )
    return header + "\n\n" + "\n\n".join(selected)


class ChatAttachmentRepository(WorkbenchRepository):
    """Owns conversation files, their parsed excerpts and message binding."""

    def create_attachment(
        self, username: str, conversation_id: str, filename: str, content: bytes
    ) -> dict[str, Any]:
        clean_name = filename.replace("\\", "/").split("/")[-1].strip()
        suffix = Path(clean_name).suffix.lower()
        if not clean_name or len(clean_name) > 255 or suffix not in CHAT_ATTACHMENT_EXTENSIONS:
            raise ValueError("仅支持文件名不超过 255 字符的 PDF、DOCX、TXT、MD、CSV")
        if not content or len(content) > MAX_CHAT_ATTACHMENT_BYTES:
            raise ValueError("附件大小必须在 1 字节至 10 MB 之间")
        if suffix == ".pdf" and not content.startswith(b"%PDF-"):
            raise ValueError("文件内容不是有效 PDF")
        if suffix == ".docx":
            try:
                with zipfile.ZipFile(BytesIO(content)) as archive:
                    if archive.getinfo("word/document.xml").file_size > MAX_CHAT_ATTACHMENT_BYTES:
                        raise ValueError("DOCX 正文解压后超过 10 MB")
            except (zipfile.BadZipFile, KeyError) as exc:
                raise ValueError("文件内容不是有效 DOCX") from exc
        if suffix in {".txt", ".md", ".csv"} and b"\x00" in content:
            raise ValueError("文本附件包含二进制内容")

        with self._connection() as conn:
            with conn.cursor() as cursor:
                conversation = self._conversation_for_user(cursor, username, conversation_id)
        if not conversation:
            raise WorkbenchNotFoundError("会话不存在或当前用户无权访问")
        self._require_conversation_write(conversation, username)
        if conversation["status"] == "archived":
            raise WorkbenchConflictError("已归档会话不能上传附件")

        attachment_id = str(uuid.uuid4())
        path = ATTACHMENT_ROOT / uuid.uuid5(uuid.NAMESPACE_URL, conversation_id).hex / f"{attachment_id}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(content)
            parsed = parse_attachment(path, clean_name)
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """INSERT INTO workbench_chat_attachments
                           (id, conversation_id, owner_username, original_filename,
                            stored_filename, size_bytes, page_count)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (
                            attachment_id,
                            conversation_id,
                            username,
                            clean_name,
                            path.name,
                            len(content),
                            parsed.page_count,
                        ),
                    )
                    cursor.executemany(
                        """INSERT INTO workbench_chat_attachment_chunks
                           (attachment_id, chunk_index, source_location, content)
                           VALUES (%s, %s, %s, %s)""",
                        [
                            (
                                attachment_id,
                                chunk["chunk_index"],
                                chunk["source_location"],
                                chunk["content"],
                            )
                            for chunk in parsed.chunks
                        ],
                    )
                conn.commit()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return {
            "id": attachment_id,
            "original_filename": clean_name,
            "size_bytes": len(content),
            "page_count": parsed.page_count,
        }

    @staticmethod
    def bind_to_message(
        cursor: Any,
        username: str,
        conversation_id: str,
        message_id: str,
        attachment_ids: list[str],
    ) -> None:
        for attachment_id in attachment_ids:
            cursor.execute(
                """SELECT id, message_id FROM workbench_chat_attachments
                   WHERE id = %s AND owner_username = %s AND conversation_id = %s
                   FOR UPDATE""",
                (attachment_id, username, conversation_id),
            )
            row = cursor.fetchone()
            if not row:
                raise WorkbenchNotFoundError("附件不存在或当前用户无权使用")
            if row["message_id"] is not None:
                raise WorkbenchConflictError("附件已经绑定其他消息")
            cursor.execute(
                "UPDATE workbench_chat_attachments SET message_id = %s WHERE id = %s",
                (message_id, attachment_id),
            )

    def get_attachment_context(self, username: str, conversation_id: str, query: str) -> str:
        self.get_conversation(username, conversation_id)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT a.id AS attachment_id, a.original_filename, a.page_count,
                              c.chunk_index, c.source_location, c.content
                         FROM workbench_chat_attachments a
                         JOIN workbench_chat_attachment_chunks c ON c.attachment_id = a.id
                        WHERE a.conversation_id = %s AND a.message_id IS NOT NULL
                        ORDER BY a.created_at DESC, a.id DESC, c.chunk_index ASC
                        LIMIT 2000""",
                    (conversation_id,),
                )
                rows = cursor.fetchall()
        return select_chat_attachment_context(rows, query)

    @staticmethod
    def list_for_messages(cursor: Any, message_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not message_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(message_ids))
        cursor.execute(
            f"""SELECT id, message_id, original_filename, size_bytes, page_count
                 FROM workbench_chat_attachments WHERE message_id IN ({placeholders})
                 ORDER BY created_at ASC""",
            tuple(message_ids),
        )
        result: dict[str, list[dict[str, Any]]] = {}
        for row in cursor.fetchall():
            result.setdefault(row["message_id"], []).append(
                _serialize_row({key: value for key, value in row.items() if key != "message_id"}) or {}
            )
        return result
