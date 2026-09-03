"""
预测报告 PDF 文件下载路由。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.config.config import API_PREFIX

router = APIRouter(prefix=f"{API_PREFIX}/report", tags=["report"])

# ========== PDF 存储目录 ==========

PDF_STORAGE_FOLDER = Path(__file__).parent.parent / "data" / "pdf"


def _ensure_pdf_storage() -> Path:
    """确保 PDF 存储目录存在，延迟创建避免模块导入时的 I/O 副作用。"""
    PDF_STORAGE_FOLDER.mkdir(parents=True, exist_ok=True)
    return PDF_STORAGE_FOLDER


# ========== PDF 文件下载接口（外部可访问） ==========


@router.get("/files/{filename}")
def get_pdf_file(filename: str):
    """获取PDF文件，外部可访问链接"""
    storage = _ensure_pdf_storage()

    # 防路径穿越：仅允许纯文件名（拒绝路径分隔符 / 相对路径 / 上层目录）
    if Path(filename).name != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法的文件名")

    file_path = storage / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="PDF 文件不存在")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=filename,
    )