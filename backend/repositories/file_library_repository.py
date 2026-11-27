"""统一汇总当前用户可访问的产品文件元数据。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.config.config import API_PREFIX
from backend.repositories.base import BaseRepository
from backend.repositories.chat_attachment_repository import (
    CHAT_ATTACHMENT_EXTENSIONS,
    MAX_CHAT_ATTACHMENT_BYTES,
)
from backend.repositories.workbench_repository import WorkbenchNotFoundError

CHAT_MOUNT_FORMATS = {extension.removeprefix(".").upper() for extension in CHAT_ATTACHMENT_EXTENSIONS}


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value else None)


def _extension(filename: str) -> str:
    return Path(filename).suffix.removeprefix(".").upper() or "未知"


def _entry(
    *,
    file_id: str,
    name: str,
    source: str,
    source_key: str,
    source_ref: str,
    created_at: Any,
    kind: str,
    size_bytes: int | None = None,
    open_url: str | None = None,
    download_url: str | None = None,
    chat_mountable: bool = False,
) -> dict[str, Any]:
    return {
        "id": file_id,
        "name": name,
        "format": _extension(name),
        "source": source,
        "source_key": source_key,
        "source_ref": source_ref,
        "created_at": _iso(created_at),
        "kind": kind,
        "size_bytes": size_bytes,
        "open_url": open_url,
        "download_url": download_url,
        "chat_mountable": chat_mountable,
    }


def _owned_file(root: Path, relative_path: str) -> Path:
    base = root.resolve()
    path = (base / relative_path).resolve()
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise WorkbenchNotFoundError("文件不存在或无权访问") from exc
    if not path.is_file():
        raise WorkbenchNotFoundError("文件不存在或无权访问")
    return path


class FileLibraryRepository(BaseRepository):
    """从已有业务表聚合文件，不复制文件内容。"""

    def list_files(self, username: str) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []

        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT a.id, a.original_filename, a.size_bytes, a.created_at
                         FROM workbench_skill_attachments a
                         JOIN workbench_skills s ON s.id = a.skill_id
                        WHERE s.owner_type = 'user'
                          AND s.owner_username = %s
                          AND a.created_by = %s
                        ORDER BY a.created_at DESC, a.id DESC""",
                    (username, username),
                )
                for row in cursor.fetchall():
                    attachment_id = str(row["id"])
                    files.append(
                        _entry(
                            file_id=f"skill:{attachment_id}",
                            name=row["original_filename"],
                            source="Skills 附件",
                            source_key="skill_attachment",
                            source_ref=attachment_id,
                            created_at=row["created_at"],
                            kind="upload",
                            size_bytes=int(row["size_bytes"] or 0),
                            open_url="/custom/skills",
                            download_url=(
                                f"{API_PREFIX}/file-library/download?source=skill_attachment"
                                f"&record_id={attachment_id}"
                            ),
                            chat_mountable=(
                                _extension(row["original_filename"]) in CHAT_MOUNT_FORMATS
                                and int(row["size_bytes"] or 0) <= MAX_CHAT_ATTACHMENT_BYTES
                            ),
                        )
                    )

                cursor.execute(
                    """SELECT id, title, original_filename, created_at,
                              OCTET_LENGTH(full_text) AS text_bytes
                         FROM policy_document
                        WHERE owner_username = %s
                        ORDER BY created_at DESC, id DESC""",
                    (username,),
                )
                for row in cursor.fetchall():
                    document_id = str(row["id"])
                    name = row["original_filename"] or f"{row['title'] or '政策文件'}.pdf"
                    files.append(
                        _entry(
                            file_id=f"policy:{document_id}",
                            name=name,
                            source="政策文件分析",
                            source_key="policy_document",
                            source_ref=document_id,
                            created_at=row["created_at"],
                            kind="upload",
                            open_url=f"/computer/policy/{document_id}",
                            chat_mountable=bool(
                                row["text_bytes"] and row["text_bytes"] <= MAX_CHAT_ATTACHMENT_BYTES
                            ),
                        )
                    )

                cursor.execute(
                    """SELECT id, title, file_path, file_size_kb, status, created_at
                         FROM research_report
                        WHERE uploaded_by = %s
                        ORDER BY created_at DESC, id DESC""",
                    (username,),
                )
                report_rows = cursor.fetchall()
                for row in report_rows:
                    report_id = str(row["id"])
                    filename = f"{row['title'] or '研报'}.pdf"
                    files.append(
                        _entry(
                            file_id=f"research:{report_id}",
                            name=filename,
                            source="研报分析",
                            source_key="research_report",
                            source_ref=report_id,
                            created_at=row["created_at"],
                            kind="upload",
                            size_bytes=int(row["file_size_kb"] or 0) * 1024,
                            open_url=f"/computer/reports/library?reportId={report_id}",
                            download_url=(
                                f"{API_PREFIX}/file-library/download?source=research_report"
                                f"&record_id={report_id}"
                            ),
                            chat_mountable=(
                                int(row["file_size_kb"] or 0) * 1024 <= MAX_CHAT_ATTACHMENT_BYTES
                            ),
                        )
                    )

                if report_rows:
                    report_ids = [int(row["id"]) for row in report_rows]
                    placeholders = ",".join(["%s"] * len(report_ids))
                    cursor.execute(
                        f"""SELECT f.id, f.report_id, f.caption, f.page_number,
                                      f.figure_order, f.image_size_kb, f.created_at
                                 FROM report_figure f
                                 JOIN research_report r ON r.id = f.report_id
                                WHERE r.uploaded_by = %s
                                  AND f.report_id IN ({placeholders})
                                ORDER BY f.created_at DESC, f.id DESC""",
                        (username, *report_ids),
                    )
                    for row in cursor.fetchall():
                        figure_id = str(row["id"])
                        fallback = f"研报图表-第{row['page_number'] or 0}页-{row['figure_order'] or 0}"
                        filename = f"{row['caption'] or fallback}.png"
                        files.append(
                            _entry(
                                file_id=f"figure:{figure_id}",
                                name=filename,
                                source="研报抽取图表",
                                source_key="research_figure",
                                source_ref=figure_id,
                                created_at=row["created_at"],
                                kind="generated",
                                size_bytes=int(row["image_size_kb"] or 0) * 1024,
                                open_url=f"/computer/reports/library?reportId={row['report_id']}",
                                download_url=(
                                    f"{API_PREFIX}/file-library/download?source=research_figure"
                                    f"&record_id={figure_id}"
                                ),
                            )
                        )

        return sorted(files, key=lambda item: item["created_at"] or "", reverse=True)

    def read_for_chat(self, username: str, source_key: str, record_id: str) -> tuple[str, bytes]:
        """Read an owned library file for copying into one conversation message."""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                if source_key == "skill_attachment":
                    cursor.execute(
                        """SELECT a.skill_id, a.stored_filename, a.original_filename
                             FROM workbench_skill_attachments a
                             JOIN workbench_skills s ON s.id = a.skill_id
                            WHERE a.id = %s AND a.created_by = %s
                              AND s.owner_type = 'user' AND s.owner_username = %s""",
                        (record_id, username, username),
                    )
                elif source_key == "research_report":
                    cursor.execute(
                        """SELECT title, file_path FROM research_report
                            WHERE id = %s AND uploaded_by = %s""",
                        (record_id, username),
                    )
                elif source_key == "policy_document":
                    cursor.execute(
                        """SELECT title, original_filename, full_text FROM policy_document
                            WHERE id = %s AND owner_username = %s""",
                        (record_id, username),
                    )
                else:
                    raise ValueError("该文件类型不能挂载到对话")
                row = cursor.fetchone()
        if not row:
            raise WorkbenchNotFoundError("文件不存在或无权访问")

        if source_key == "policy_document":
            text = str(row["full_text"] or "").strip()
            if not text:
                raise ValueError("该政策文件尚无可用的解析文本")
            filename = f"{Path(row['original_filename'] or row['title'] or '政策文件').stem[:240]}.txt"
            content = text.encode("utf-8")
        else:
            if source_key == "skill_attachment":
                from backend.repositories.skill_repository import ATTACHMENT_ROOT

                filename = row["original_filename"]
                path = _owned_file(ATTACHMENT_ROOT, f"{row['skill_id']}/{row['stored_filename']}")
            else:
                from backend.research_report.constants import DATA_ROOT

                filename = f"{str(row['title'] or '研报')[:250]}.pdf"
                path = _owned_file(DATA_ROOT, row["file_path"])
            if path.stat().st_size > MAX_CHAT_ATTACHMENT_BYTES:
                raise ValueError("文件超过对话附件的 10 MB 限制")
            content = path.read_bytes()

        if Path(filename).suffix.lower() not in CHAT_ATTACHMENT_EXTENSIONS:
            raise ValueError("该文件格式不能挂载到对话")
        if len(content) > MAX_CHAT_ATTACHMENT_BYTES:
            raise ValueError("文件超过对话附件的 10 MB 限制")
        return filename, content
