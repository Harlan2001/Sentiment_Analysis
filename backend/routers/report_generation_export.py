"""Download endpoints for completed report generations."""

from fastapi import APIRouter, HTTPException, Query, Request
from urllib.parse import quote

from fastapi.responses import Response

from backend.config.config import API_PREFIX
from backend.repositories.report_generation_repository import ReportGenerationRepository
from backend.services.report_export_service import export_filename, generate_docx, generate_pdf


router = APIRouter(prefix=f"{API_PREFIX}/report-generation", tags=["report-generation"])


@router.get("/tasks/{task_id}/export")
def export_report_generation_task(
    request: Request,
    task_id: str,
    format: str = Query(..., pattern="^(pdf|docx)$"),
):
    task = ReportGenerationRepository.from_environment().get_task(
        request.state.username, task_id
    )
    if not task:
        raise HTTPException(status_code=404, detail="Report generation task not found")
    if task["status"] != "completed" or not task.get("result_markdown"):
        raise HTTPException(status_code=409, detail="Only completed reports can be exported")
    try:
        content = (
            generate_pdf(task["title"], task["result_markdown"], task["source_snapshot_json"])
            if format == "pdf"
            else generate_docx(task["title"], task["result_markdown"], task["source_snapshot_json"])
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    media_type = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    filename = export_filename(task["title"], format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
