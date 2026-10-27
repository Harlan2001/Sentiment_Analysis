"""当前用户的文件库 API。"""

from __future__ import annotations

import mimetypes
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response

from backend.common.api_response import ok
from backend.config.config import API_PREFIX
from backend.report.export_service import export_filename, generate_docx, generate_pdf
from backend.repositories.file_library_repository import FileLibraryRepository

router = APIRouter(prefix=f"{API_PREFIX}/file-library", tags=["file-library"])


def _repository() -> FileLibraryRepository:
    return FileLibraryRepository.from_environment()


def _owned_path(root: Path, relative_path: str) -> Path:
    base = root.resolve()
    candidate = (base / relative_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="文件不存在") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return candidate


@router.get("")
def list_file_library(
    request: Request,
    source: str | None = None,
    format: str | None = None,
    date_start: date | None = None,
    date_end: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    if date_start and date_end and date_start > date_end:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    username = getattr(request.state, "username", None) or "admin"
    files = _repository().list_files(username)
    sources = sorted({item["source"] for item in files})
    formats = sorted({item["format"] for item in files})
    format_counts = Counter(item["format"] for item in files)
    summary_formats = sorted(format_counts.items(), key=lambda item: (-item[1], item[0]))
    summary = {
        "total": len(files),
        "uploaded": sum(item["kind"] == "upload" for item in files),
        "generated": sum(item["kind"] == "generated" for item in files),
        "formats": [
            {"format": file_format, "count": count}
            for file_format, count in summary_formats
        ],
    }

    filtered = files
    if source:
        filtered = [item for item in filtered if item["source"] == source]
    if format:
        selected_format = format.upper().lstrip(".")
        filtered = [item for item in filtered if item["format"] == selected_format]
    if date_start:
        filtered = [
            item for item in filtered
            if item["created_at"] and item["created_at"][:10] >= date_start.isoformat()
        ]
    if date_end:
        filtered = [
            item for item in filtered
            if item["created_at"] and item["created_at"][:10] <= date_end.isoformat()
        ]

    total = len(filtered)
    offset = (page - 1) * page_size
    return ok({
        "items": filtered[offset:offset + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "sources": sources,
        "formats": formats,
        "summary": summary,
    })


@router.get("/download")
def download_file(
    request: Request,
    source: str = Query(...),
    record_id: str = Query(...),
    format: str | None = Query(None, pattern="^(pdf|docx)$"),
):
    """下载已有个人文件；所有路径都先从当前用户拥有的记录解析。"""
    from backend.repositories.skill_repository import ATTACHMENT_ROOT
    from backend.research_report.constants import DATA_ROOT, FIGURE_ROOT

    username = getattr(request.state, "username", None) or "admin"
    repository = _repository()

    if source == "report_generation":
        task = repository.get_owned_generated_report(username, record_id)
        if not task:
            raise HTTPException(status_code=404, detail="文件不存在或无权访问")
        filename = (task["title"] or "研报") + ".md"
        return Response(
            content=task["result_markdown"] or "",
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}"},
        )

    if source == "research_export":
        if not format:
            raise HTTPException(status_code=400, detail="请选择导出格式")
        with repository._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT title, status, ai_deep_markdown
                         FROM research_report
                        WHERE id=%s AND uploaded_by=%s""",
                    (record_id, username),
                )
                report = cursor.fetchone()
        if not report or report["status"] != "analyzed" or not report["ai_deep_markdown"]:
            raise HTTPException(status_code=404, detail="文件不存在或无权访问")
        title = report["title"] or "研报"
        markdown = report["ai_deep_markdown"]
        try:
            content = generate_pdf(title, markdown, []) if format == "pdf" else generate_docx(title, markdown, [])
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        filename = export_filename(title + "_深度分析", format)
        media_type = (
            "application/pdf"
            if format == "pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}"},
        )

    with repository._connection() as conn:
        with conn.cursor() as cursor:
            if source == "research_report":
                cursor.execute(
                    "SELECT title, file_path FROM research_report WHERE id=%s AND uploaded_by=%s",
                    (record_id, username),
                )
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="文件不存在或无权访问")
                path = _owned_path(DATA_ROOT, row["file_path"])
                filename = f"{row['title'] or '研报'}.pdf"
                media_type = "application/pdf"
            elif source == "research_figure":
                cursor.execute(
                    """SELECT f.image_path, f.caption, f.page_number, f.figure_order
                         FROM report_figure f
                         JOIN research_report r ON r.id = f.report_id
                        WHERE f.id=%s AND r.uploaded_by=%s""",
                    (record_id, username),
                )
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="文件不存在或无权访问")
                path = _owned_path(FIGURE_ROOT, row["image_path"])
                fallback = f"研报图表-{row['page_number'] or 0}-{row['figure_order'] or 0}"
                filename = f"{row['caption'] or fallback}.png"
                media_type = "image/png"
            elif source == "skill_attachment":
                cursor.execute(
                    """SELECT a.skill_id, a.stored_filename, a.original_filename, a.content_type
                         FROM workbench_skill_attachments a
                         JOIN workbench_skills s ON s.id = a.skill_id
                        WHERE a.id=%s AND a.created_by=%s
                          AND s.owner_type='user' AND s.owner_username=%s""",
                    (record_id, username, username),
                )
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="文件不存在或无权访问")
                path = _owned_path(ATTACHMENT_ROOT, f"{row['skill_id']}/{row['stored_filename']}")
                filename = row["original_filename"]
                media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            else:
                raise HTTPException(status_code=404, detail="文件不存在或无权访问")

    return FileResponse(path, filename=filename, media_type=media_type)
