"""
研报板块 API 路由
- GET /research/summary       顶部概览统计
- GET /research/list          研报列表（支持筛选 + 分页）
- GET /research/{id}          研报详情（含 AI 分析 + 图表列表）
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from backend.common.api_response import ok
from backend.common.database import get_db_connection
from backend.common.pagination import paginated_payload
from backend.config.config import ANALYSIS_MODEL_REGISTRY, API_PREFIX
from backend.report import export_service
from backend.repositories.research_report_repository import (
    ResearchReportConflictError,
    ResearchReportRepository,
)
from backend.research_report.constants import FIGURE_ROOT
from backend.research_report.llm import resolve_provider_model
from backend.research_report.parser import clean_display_text
from backend.research_report.service import ingest_uploaded_pdf, run_analysis_async

router = APIRouter(prefix=f"{API_PREFIX}/research", tags=["research"])

# /list 浏览器：关键词命中标题/机构/行业/正文/AI 摘要与要点（P2-10 检索增强）
_BROWSE_KEYWORD_COLUMNS = (
    "title",
    "institution",
    "industry",
    "ai_summary",
    "ai_key_points",
    "full_text",
)


def _validate_date_range(date_start: Optional[date], date_end: Optional[date]) -> None:
    if date_start and date_end and date_start > date_end:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")


class BatchReanalyzeRequest(BaseModel):
    institution: Optional[str] = None
    industry: Optional[str] = None
    market_view: Optional[str] = None
    keyword: Optional[str] = None
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    model: str = "glm"
_RESEARCH_LIST_COLUMNS = (
    "id",
    "title",
    "institution",
    "publish_date",
    "industry",
    "report_type",
    "ai_summary",
    "ai_market_view",
    "ai_view_strength",
    "ai_symbols",
    "ai_industries",
    "ai_key_points",
    "page_count",
    "file_size_kb",
    "status",
    "source",
    "created_at",
)


def _research_list_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "institution": row["institution"],
        "publish_date": str(row["publish_date"]) if row["publish_date"] else None,
        "industry": row["industry"],
        "report_type": row["report_type"],
        "ai_summary": row["ai_summary"],
        "ai_market_view": row["ai_market_view"],
        "ai_view_strength": (
            float(row["ai_view_strength"]) if row["ai_view_strength"] else None
        ),
        "ai_symbols": row["ai_symbols"],
        "ai_industries": row["ai_industries"],
        "ai_key_points": row["ai_key_points"],
        "page_count": row["page_count"],
        "file_size_kb": row["file_size_kb"],
        "status": row["status"],
        "source": row["source"],
        "created_at": str(row["created_at"]) if row["created_at"] else None,
    }


@router.get("/summary")
def get_summary():
    """顶部概览：研报总数、观点分布、机构数、时间范围"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM research_report")
            total = cur.fetchone()[0]

            cur.execute("""
                SELECT ai_market_view, COUNT(*) FROM research_report
                WHERE status='analyzed' GROUP BY ai_market_view
            """)
            views = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute("""
                SELECT COUNT(DISTINCT institution) FROM research_report
                WHERE institution IS NOT NULL AND institution != ''
            """)
            institutions = cur.fetchone()[0]

            cur.execute(
                "SELECT MIN(publish_date), MAX(publish_date) FROM research_report"
            )
            date_range = cur.fetchone()

        return ok({
            "total": total,
            "analyzed": views.get("bullish", 0)
            + views.get("bearish", 0)
            + views.get("neutral", 0),
            "bullish": views.get("bullish", 0),
            "bearish": views.get("bearish", 0),
            "neutral": views.get("neutral", 0),
            "institutions": institutions,
            "date_start": str(date_range[0]) if date_range[0] else None,
            "date_end": str(date_range[1]) if date_range[1] else None,
        })


@router.get("/list")
def get_research_list(
    institution: Optional[str] = Query(None, description="机构筛选"),
    industry: Optional[str] = Query(None, description="行业筛选"),
    market_view: Optional[str] = Query(
        None, description="情感筛选：bullish/bearish/neutral"
    ),
    keyword: Optional[str] = Query(
        None, description="标题/机构/行业/正文/AI 观点关键词搜索"
    ),
    status: Optional[str] = Query(None, description="分析状态筛选"),
    date_start: Optional[date] = Query(None, description="发布日期起（含）"),
    date_end: Optional[date] = Query(None, description="发布日期止（含）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """研报列表，支持筛选 + 分页"""
    _validate_date_range(date_start, date_end)
    repository = ResearchReportRepository.from_environment()
    total = repository.count_reports(
        keyword=keyword,
        keyword_columns=_BROWSE_KEYWORD_COLUMNS,
        institution=institution,
        industry=industry,
        market_view=market_view,
        status=status,
        date_start=date_start,
        date_end=date_end,
    )
    rows = repository.query_reports(
        columns=_RESEARCH_LIST_COLUMNS,
        keyword=keyword,
        keyword_columns=_BROWSE_KEYWORD_COLUMNS,
        institution=institution,
        industry=industry,
        market_view=market_view,
        status=status,
        date_start=date_start,
        date_end=date_end,
        limit=page_size,
        offset=(page - 1) * page_size,
        order_by="publish_date DESC, created_at DESC",
    )
    payload = paginated_payload(
        [_research_list_item(row) for row in rows], total, page, page_size
    )
    payload["filters"] = repository.get_filter_facets()
    return ok(payload)


@router.get("/{report_id}")
def get_research_detail(report_id: int):
    """研报详情：正文 + AI 分析 + 图表"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, institution, analyst, publish_date, industry,
                       symbols, report_type, file_path, file_hash, file_size_kb,
                       page_count, full_text, ai_summary, ai_key_points, ai_symbols,
                       ai_industries, ai_market_view, ai_view_strength,
                       ai_time_horizon, ai_evidence, ai_deep_markdown,
                       ai_analyzed_at, ai_model, ai_raw_response,
                       status, source, created_at
                FROM research_report WHERE id = %s
            """,
                (report_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="研报不存在")

            cur.execute(
                """
                SELECT id, page_number, figure_order, figure_type, caption,
                       image_path, image_size_kb
                FROM report_figure WHERE report_id = %s
                ORDER BY page_number, figure_order
            """,
                (report_id,),
            )
            figs = cur.fetchall()

        figures = []
        for f in figs:
            figures.append(
                {
                    "id": f[0],
                    "page_number": f[1],
                    "figure_order": f[2],
                    "figure_type": f[3],
                    "caption": f[4],
                    "image_path": f[5],
                    "image_size_kb": f[6],
                }
            )

        return ok({
            "id": row[0],
            "title": row[1],
            "institution": row[2],
            "analyst": row[3],
            "publish_date": str(row[4]) if row[4] else None,
            "industry": row[5],
            "symbols": row[6],
            "report_type": row[7],
            "file_path": row[8],
            "file_hash": row[9],
            "file_size_kb": row[10],
            "page_count": row[11],
            "full_text": clean_display_text(row[12] or ""),
            "ai_summary": row[13],
            "ai_key_points": row[14],
            "ai_symbols": row[15],
            "ai_industries": row[16],
            "ai_market_view": row[17],
            "ai_view_strength": float(row[18]) if row[18] else None,
            "ai_time_horizon": row[19],
            "ai_evidence": row[20],
            "ai_deep_markdown": row[21],
            "ai_analyzed_at": str(row[22]) if row[22] else None,
            "ai_model": row[23],
            "ai_raw_response": row[24],
            "status": row[25],
            "source": row[26],
            "created_at": str(row[27]) if row[27] else None,
            "figures": figures,
        })


@router.post("/upload")
async def upload_research_pdf(
    request: Request,
    file: UploadFile = File(...),
):
    """上传研报 PDF，自动解析入库。

    返回 report_id，后续需调用 /{report_id}/analyze 触发 AI 分析。
    """
    # 校验文件类型
    content_type = file.content_type or ""
    filename = (file.filename or "").lower()
    is_pdf = content_type == "application/pdf" or filename.endswith(".pdf")
    if not is_pdf:
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    # 读取文件内容
    try:
        pdf_bytes = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="文件读取失败")

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="文件为空")

    # 校验 PDF 魔数
    if pdf_bytes[:4] != b"%PDF":
        raise HTTPException(status_code=400, detail="不是合法的 PDF 文件")

    # 入库
    try:
        result = ingest_uploaded_pdf(
            pdf_bytes=pdf_bytes,
            original_filename=file.filename or "unknown.pdf",
            uploaded_by=getattr(request.state, "username", None) or "admin",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"入库失败: {e}")

    return ok({
        "report_id": result["report_id"],
        "title": result["title"],
        "status": result["status"],
        "is_duplicate": result["is_duplicate"],
    })


def _start_analysis(report_id: int, model: str) -> None:
    """校验模型短名并启动后台分析线程。"""
    if model not in ANALYSIS_MODEL_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的模型: {model}，可选: {', '.join(ANALYSIS_MODEL_REGISTRY)}",
        )
    run_analysis_async(report_id, resolve_provider_model(model))


@router.post("/reanalyze/batch")
def reanalyze_batch(payload: BatchReanalyzeRequest):
    """按机构/行业/观点/关键词/发布日期筛选，批量重跑已分析研报（P0-3）。

    只重跑 status='analyzed' 的研报；逐份重置后排队，正在分析中的计入 skipped。
    """
    _validate_date_range(payload.date_start, payload.date_end)
    repository = ResearchReportRepository.from_environment()
    rows = repository.query_reports(
        columns=("id", "status"),
        status="analyzed",
        institution=payload.institution,
        industry=payload.industry,
        market_view=payload.market_view,
        keyword=payload.keyword,
        keyword_columns=_BROWSE_KEYWORD_COLUMNS,
        date_start=payload.date_start,
        date_end=payload.date_end,
        limit=500,
        order_by="publish_date DESC, id DESC",
    )

    triggered: list[int] = []
    skipped: list[int] = []
    for row in rows:
        report_id = int(row["id"])
        try:
            repository.reset_for_reanalysis(report_id)
        except ResearchReportConflictError:
            skipped.append(report_id)
            continue
        _start_analysis(report_id, payload.model)
        triggered.append(report_id)

    return ok({
        "triggered": len(triggered),
        "skipped": len(skipped),
        "report_ids": triggered,
    })


@router.post("/{report_id}/analyze")
def trigger_analysis(
    report_id: int,
    model: str = Query(
        "glm", description="模型短名: glm / deepseek / qwen / kimi"
    ),
    force: bool = Query(False, description="对已分析研报强制重新分析"),
):
    """触发单份研报的 AI 分析（后台异步执行）。

    force=true 时允许对 analyzed 研报重新分析（旧结果保留至新分析成功才覆盖）。
    """
    # 校验报告存在
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status FROM research_report WHERE id=%s",
                (report_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="研报不存在")

    current_status = row[1]
    if current_status == "analyzed":
        if not force:
            return ok({
                "report_id": report_id,
                "status": "analyzed",
                "message": "已完成分析，无需重复触发（force=true 可重新分析）",
            })
        try:
            ResearchReportRepository.from_environment().reset_for_reanalysis(report_id)
        except ResearchReportConflictError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc))
    elif current_status == "processing":
        return ok({
            "report_id": report_id,
            "status": "processing",
            "message": "正在分析中，请稍候",
        })
    elif current_status not in ("parsed", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 '{current_status}' 不支持触发分析",
        )

    _start_analysis(report_id, model)

    return ok({
        "report_id": report_id,
        "status": "processing",
        "message": "分析任务已提交",
    })


# ── 单篇深度拆解导出（P1-5） ─────────────────────────────────────────────

_EXPORT_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/{report_id}/export")
def export_report(report_id: int, format: str = Query("pdf", description="pdf / docx")):
    """导出单份研报的深度拆解 Markdown 为 PDF/DOCX。"""
    fmt = format.lower()
    if fmt not in _EXPORT_MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="仅支持导出 pdf 或 docx 格式")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, status, ai_deep_markdown FROM research_report WHERE id=%s",
                (report_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="研报不存在")
    title, status, markdown = row
    if status != "analyzed" or not markdown:
        raise HTTPException(status_code=409, detail="该研报尚未生成深度拆解，无法导出")

    if fmt == "pdf":
        content = export_service.generate_pdf(title, markdown, [])
    else:
        content = export_service.generate_docx(title, markdown, [])

    filename = export_service.export_filename(title, fmt)
    return Response(
        content=content,
        media_type=_EXPORT_MEDIA_TYPES[fmt],
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@router.get("/{report_id}/figures/{figure_id}/image")
def get_figure_image(report_id: int, figure_id: int):
    """提供研报图表图片（P1-4 原文对照），禁止路径越界。"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT image_path FROM report_figure WHERE id=%s AND report_id=%s",
                (figure_id, report_id),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="图表不存在")

    image_path = (row[0] or "").replace("\\", "/")
    target = (FIGURE_ROOT / image_path).resolve()
    root = FIGURE_ROOT.resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="图表文件不存在")

    return FileResponse(target)
