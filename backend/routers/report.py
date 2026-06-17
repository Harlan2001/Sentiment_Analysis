from __future__ import annotations

from fastapi.responses import FileResponse
from fastapi import HTTPException, Query, APIRouter
from pathlib import Path
from datetime import date
from backend.common.database import get_db_connection
from backend.push.pdf_generator import generate_prediction_pdf
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/report", tags=["report"])

# ========== PDF 存储目录 ==========

PDF_STORAGE_FOLDER = Path(__file__).parent.parent / "data" / "pdf"


def _ensure_pdf_storage() -> Path:
    """确保 PDF 存储目录存在，延迟创建避免模块导入时的 I/O 副作用。"""
    PDF_STORAGE_FOLDER.mkdir(parents=True, exist_ok=True)
    return PDF_STORAGE_FOLDER


# ========== PDF 生成接口 ==========


@router.post("/generate-prediction")
async def api_generate_prediction_pdf(
    report_date: str = Query(None, description="报告日期 (YYYY-MM-DD)，不传则使用数据库中最新报告日期"),
    frontend_url: str = Query(None, description="前端地址，默认使用环境变量 FRONTEND_BASE_URL"),
):
    """
    生成指定日期的预测报告 PDF 并保存到 data/pdf/ 目录。

    参数:
        report_date: 报告日期 (YYYY-MM-DD)，不传则从数据库查询最新报告日期
        frontend_url: 前端基地址，不传则使用环境变量 FRONTEND_BASE_URL 或默认值
    """
    try:
        parsed_date: date | None = None

        if report_date:
            try:
                parsed_date = date.fromisoformat(report_date)
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail=f"日期格式错误: {report_date}，请使用 YYYY-MM-DD 格式")

        # 未传日期时从数据库查询最新报告日期
        if parsed_date is None:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT MAX(trade_date) FROM forecast_report")
                row = cur.fetchone()
                if row and row[0]:
                    parsed_date = row[0] if isinstance(row[0], date) else row[0]
                    logger.info("从数据库获取最新报告日期: %s", parsed_date)
                else:
                    raise HTTPException(
                        status_code=404,
                        detail="forecast_report 表为空，无法确定报告日期，请手动指定 report_date 参数",
                    )

        # 生成 PDF，返回 (文件路径, 页面实际日期)
        pdf_path, actual_trade_date = await generate_prediction_pdf(
            report_date=parsed_date,
            frontend_url=frontend_url,
        )

        return {
            "success": True,
            "message": "预测报告 PDF 生成成功",
            "data": {
                "report_date": actual_trade_date,
                "file_path": str(pdf_path),
                "file_name": pdf_path.name,
                "file_size_bytes": pdf_path.stat().st_size,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("PDF 生成 API 异常: %s", e)
        raise HTTPException(status_code=500, detail=f"PDF 生成失败: {str(e)}")


# ========== PDF 文件下载接口（外部可访问） ==========


@router.get("/files/{filename}")
def get_pdf_file(filename: str):
    """获取PDF文件，外部可访问链接"""
    storage = _ensure_pdf_storage()
    file_path = storage / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="PDF 文件不存在")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=filename,
    )
