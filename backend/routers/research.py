"""
研报板块 API 路由
- GET /research/summary       顶部概览统计
- GET /research/list          研报列表（支持筛选 + 分页）
- GET /research/{id}          研报详情（含 AI 分析 + 图表列表）
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from backend.common.api_response import ok
from backend.common.database import get_db_connection
from backend.common.pagination import paginated_payload
from backend.config.config import ANALYSIS_MODEL_REGISTRY, API_PREFIX
from backend.repositories.research_report_repository import ResearchReportRepository
from backend.research_report.llm import resolve_provider_model
from backend.research_report.parser import clean_display_text
from backend.research_report.service import ingest_uploaded_pdf, run_analysis_async

router = APIRouter(prefix=f"{API_PREFIX}/research", tags=["research"])

# /list 浏览器：关键词命中标题/机构/行业；筛选面不带 status 约束
_BROWSE_KEYWORD_COLUMNS = ("title", "institution", "industry")
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
        None, description="标题/机构/行业关键词搜索"
    ),
    status: Optional[str] = Query(None, description="分析状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """研报列表，支持筛选 + 分页"""
    repository = ResearchReportRepository.from_environment()
    total = repository.count_reports(
        keyword=keyword,
        keyword_columns=_BROWSE_KEYWORD_COLUMNS,
        institution=institution,
        industry=industry,
        market_view=market_view,
        status=status,
    )
    rows = repository.query_reports(
        columns=_RESEARCH_LIST_COLUMNS,
        keyword=keyword,
        keyword_columns=_BROWSE_KEYWORD_COLUMNS,
        institution=institution,
        industry=industry,
        market_view=market_view,
        status=status,
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
                       ai_time_horizon, ai_evidence, ai_analyzed_at, ai_model, ai_raw_response,
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
            "ai_analyzed_at": str(row[21]) if row[21] else None,
            "ai_model": row[22],
            "ai_raw_response": row[23],
            "status": row[24],
            "source": row[25],
            "created_at": str(row[26]) if row[26] else None,
            "figures": figures,
        })


@router.post("/upload")
async def upload_research_pdf(
    file: UploadFile = File(...),
    uploaded_by: str = Form("web"),
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
            uploaded_by=uploaded_by,
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


@router.post("/{report_id}/analyze")
def trigger_analysis(
    report_id: int,
    model: str = Query(
        "glm", description="模型短名: glm / deepseek / qwen / kimi"
    ),
):
    """触发单份研报的 AI 分析（后台异步执行）。"""
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
        return ok({
            "report_id": report_id,
            "status": "analyzed",
            "message": "已完成分析，无需重复触发",
        })
    if current_status == "processing":
        return ok({
            "report_id": report_id,
            "status": "processing",
            "message": "正在分析中，请稍候",
        })

    if current_status not in ("parsed", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 '{current_status}' 不支持触发分析",
        )

    # 验证模型名
    if model not in ANALYSIS_MODEL_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的模型: {model}，可选: {', '.join(ANALYSIS_MODEL_REGISTRY)}",
        )

    # 启动后台分析
    run_analysis_async(report_id, resolve_provider_model(model))

    return ok({
        "report_id": report_id,
        "status": "processing",
        "message": "分析任务已提交",
    })
