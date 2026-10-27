"""统一汇总当前用户可访问的产品文件元数据。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.config.config import API_PREFIX
from backend.repositories.base import BaseRepository


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
    }


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
                        )
                    )

                cursor.execute(
                    """SELECT id, title, original_filename, created_at
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
                        )
                    )

                cursor.execute(
                    """SELECT id, title, file_path, file_size_kb, status, ai_analyzed_at,
                              (ai_deep_markdown IS NOT NULL AND ai_deep_markdown <> '') AS has_deep_analysis,
                              created_at
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
                        )
                    )
                    if row["status"] == "analyzed" and row["has_deep_analysis"]:
                        for extension in ("pdf", "docx"):
                            files.append(
                                _entry(
                                    file_id=f"research-export:{report_id}:{extension}",
                                    name=f"{row['title'] or '研报'}_深度分析.{extension}",
                                    source="研报分析导出",
                                    source_key="research_export",
                                    source_ref=report_id,
                                    created_at=row["ai_analyzed_at"] or row["created_at"],
                                    kind="generated",
                                    open_url=f"/computer/reports/library?reportId={report_id}",
                                    download_url=(
                                        f"{API_PREFIX}/file-library/download?source=research_export"
                                        f"&record_id={report_id}&format={extension}"
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

                cursor.execute(
                    """SELECT id, title, OCTET_LENGTH(result_markdown) AS result_size_bytes,
                              COALESCE(finished_at, updated_at) AS file_date
                         FROM report_generation_tasks
                        WHERE owner_username = %s
                          AND deleted_at IS NULL
                          AND status = 'completed'
                          AND result_markdown IS NOT NULL
                        ORDER BY COALESCE(finished_at, updated_at) DESC, id DESC""",
                    (username,),
                )
                for row in cursor.fetchall():
                    task_id = str(row["id"])
                    title = row["title"] or "研报"
                    detail_url = f"/computer/reports/{task_id}"
                    files.append(
                        _entry(
                            file_id=f"report:{task_id}:md",
                            name=f"{title}.md",
                            source="研报生成",
                            source_key="report_generation",
                            source_ref=task_id,
                            created_at=row["file_date"],
                            kind="generated",
                            size_bytes=int(row["result_size_bytes"] or 0),
                            open_url=detail_url,
                            download_url=(
                                f"{API_PREFIX}/file-library/download?source=report_generation"
                                f"&record_id={task_id}"
                            ),
                        )
                    )
                    for extension in ("pdf", "docx"):
                        files.append(
                            _entry(
                                file_id=f"report:{task_id}:{extension}",
                                name=f"{title}.{extension}",
                                source="研报生成",
                                source_key="report_generation",
                                source_ref=task_id,
                                created_at=row["file_date"],
                                kind="generated",
                                open_url=detail_url,
                                download_url=(
                                    f"{API_PREFIX}/report-generation/tasks/{task_id}/export"
                                    f"?format={extension}"
                                ),
                            )
                        )

        return sorted(files, key=lambda item: item["created_at"] or "", reverse=True)

    def get_owned_generated_report(self, username: str, task_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT title, result_markdown
                         FROM report_generation_tasks
                        WHERE id=%s AND owner_username=%s
                          AND deleted_at IS NULL AND status='completed'
                          AND result_markdown IS NOT NULL""",
                    (task_id, username),
                )
                return cursor.fetchone()
