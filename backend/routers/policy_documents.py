"""政策文件分析 API（工作流内）。

流程与研报分析一致：上传 PDF → 解析入库 → 触发 AI 解读 → 查看详情。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from backend.common.api_response import ok
from backend.common.pagination import paginated_payload
from backend.config.config import API_PREFIX
from backend.policy_document.service import (
    PolicyDocumentError,
    ingest_policy_pdf,
    start_analysis_async,
)
from backend.repositories.policy_document_repository import PolicyDocumentRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{API_PREFIX}/policy-documents", tags=["policy-documents"])


def _repository() -> PolicyDocumentRepository:
    return PolicyDocumentRepository.from_environment()


def _current_username(request: Request) -> str:
    return getattr(request.state, "username", None) or "admin"


@router.get("")
def list_documents(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """政策文件列表（含分析状态）。"""
    result = _repository().list_documents(
        _current_username(request),
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return ok(paginated_payload(result["items"], result["total"], page, page_size))


@router.get("/{document_id}")
def get_document(request: Request, document_id: int):
    """文件详情与 AI 解读结果。"""
    document = _repository().get_document(_current_username(request), document_id)
    if not document:
        raise HTTPException(status_code=404, detail="政策文件不存在")
    return ok(document)


@router.post("/upload")
async def upload_policy_pdf(request: Request, file: UploadFile = File(...)):
    """上传政策文件 PDF，自动解析并**立即触发 AI 解读**。

    与研报不同：政策文件通常只有一份，上传后直接分析更顺手，无需二次触发。
    """
    content_type = file.content_type or ""
    filename = (file.filename or "").lower()
    if not (content_type == "application/pdf" or filename.endswith(".pdf")):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    try:
        pdf_bytes = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="文件读取失败") from None

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="文件为空")
    # 与研报一致：校验 PDF 魔数，避免改扩展名的非 PDF 文件
    if pdf_bytes[:4] != b"%PDF":
        raise HTTPException(status_code=400, detail="不是合法的 PDF 文件")

    username = _current_username(request)
    try:
        result = ingest_policy_pdf(pdf_bytes, file.filename or "unknown.pdf", username)
    except PolicyDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 非重复文件才触发分析（重复文件可能已完成分析）
    if not result["is_duplicate"]:
        start_analysis_async(result["document_id"], username)

    return ok(result)


@router.post("/{document_id}/analyze")
def reanalyze(request: Request, document_id: int):
    """重新分析（用于失败重试或换模型复跑）。"""
    username = _current_username(request)
    if not _repository().get_document(username, document_id):
        raise HTTPException(status_code=404, detail="政策文件不存在")
    start_analysis_async(document_id, username)
    return ok({"document_id": document_id, "status": "analyzing"})


@router.delete("/{document_id}")
def delete_document(request: Request, document_id: int):
    """删除文件及其分析结果。"""
    if not _repository().delete_document(_current_username(request), document_id):
        raise HTTPException(status_code=404, detail="政策文件不存在")
    return ok({"deleted": True})