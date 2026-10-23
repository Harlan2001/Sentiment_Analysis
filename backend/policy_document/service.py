"""政策文件分析服务：上传 → 解析 → LLM 解读 → 入库。

与研报分析同构（上传/解析/分析/详情），差异在解析目标与输出字段（见 parser / llm）。
分析以线程方式后台执行，避免阻塞上传请求。
"""

from __future__ import annotations

import hashlib
import logging
import tempfile
import threading
from pathlib import Path
from typing import Any

from backend.policy_document.llm import analyze_policy_document
from backend.policy_document.parser import parse_policy_pdf
from backend.repositories.policy_document_repository import PolicyDocumentRepository

logger = logging.getLogger(__name__)

# 上传限制
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20MB


class PolicyDocumentError(RuntimeError):
    """上传/解析失败（路由映射为 4xx）。"""


def _sha256(data: bytes) -> str:
    """文件内容哈希（用于去重）。"""
    return hashlib.sha256(data).hexdigest()


def ingest_policy_pdf(
    pdf_bytes: bytes,
    original_filename: str,
    owner_username: str,
) -> dict[str, Any]:
    """接收上传的 PDF，完成去重、解析与入库（不含 LLM 分析）。

    返回 {document_id, title, status, is_duplicate}。
    """
    if not pdf_bytes:
        raise PolicyDocumentError("文件内容为空")
    if len(pdf_bytes) > MAX_FILE_BYTES:
        raise PolicyDocumentError(
            f"文件过大（{len(pdf_bytes) // 1024 // 1024}MB），上限 {MAX_FILE_BYTES // 1024 // 1024}MB"
        )

    repository = PolicyDocumentRepository.from_environment()
    file_hash = _sha256(pdf_bytes)

    existing = repository.find_by_hash(owner_username, file_hash)
    if existing:
        return {
            "document_id": existing["id"],
            "title": existing["title"],
            "status": existing["status"],
            "is_duplicate": True,
        }

    # 解析：写临时文件供 pymupdf 读取，解析后立即清理
    fallback_title = Path(original_filename).stem if original_filename else ""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            handle.write(pdf_bytes)
            temp_path = Path(handle.name)

        parsed = parse_policy_pdf(temp_path, fallback_title=fallback_title)
    except RuntimeError as exc:
        raise PolicyDocumentError(f"解析失败: {exc}") from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)

    if not parsed.full_text.strip():
        raise PolicyDocumentError("未能从文件中提取到文本，请确认是文本型 PDF（而非扫描件）")

    document_id = repository.create_document(
        owner_username,
        file_hash=file_hash,
        title=parsed.title,
        original_filename=original_filename,
        issuer=parsed.issuer,
        document_no=parsed.document_no,
        publish_date=parsed.publish_date,
        full_text=parsed.full_text,
        page_count=parsed.page_count,
    )

    return {
        "document_id": document_id,
        "title": parsed.title,
        "status": "uploaded",
        "is_duplicate": False,
        "issuer": parsed.issuer,
        "document_no": parsed.document_no,
        "publish_date": parsed.publish_date.isoformat() if parsed.publish_date else None,
        "page_count": parsed.page_count,
        "warnings": parsed.warnings,
    }


def run_analysis(document_id: int, owner_username: str) -> None:
    """同步执行分析（供后台线程调用）。

    失败时把状态置为 failed 并记录原因 —— 不静默失败。
    """
    repository = PolicyDocumentRepository.from_environment()
    document = repository.get_document(owner_username, document_id)
    if not document:
        logger.error("政策文件不存在: %s", document_id)
        return

    repository.set_status(document_id, "analyzing")
    try:
        # 分析需要全文，get_document 只返回预览，这里回查完整正文
        full_text = _load_full_text(repository, owner_username, document_id)
        analysis = analyze_policy_document(full_text)
        repository.save_analysis(document_id, owner_username, analysis)
        repository.set_status(document_id, "completed")
        logger.info("政策文件分析完成: id=%s 方向=%s", document_id, analysis.get("impact_direction"))
    except Exception as exc:
        logger.exception("政策文件分析失败: id=%s", document_id)
        repository.set_status(document_id, "failed", str(exc)[:500])


def _load_full_text(
    repository: PolicyDocumentRepository, owner_username: str, document_id: int
) -> str:
    """回查完整正文（详情接口只返回预览片段）。"""
    with repository._connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT full_text FROM policy_document WHERE id = %s AND owner_username = %s",
                (document_id, owner_username),
            )
            row = cursor.fetchone()
    return (row or {}).get("full_text") or ""


def start_analysis_async(document_id: int, owner_username: str) -> None:
    """后台线程执行分析，避免阻塞上传请求（与研报模块同做法）。"""
    thread = threading.Thread(
        target=run_analysis,
        args=(document_id, owner_username),
        name=f"policy-analysis-{document_id}",
        daemon=True,
    )
    thread.start()