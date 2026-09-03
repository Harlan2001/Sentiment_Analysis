"""
研报管道模块 — 上传入库 + 异步 AI 分析
========================================
整合研报解析/分析逻辑，提供 API 可调用的服务函数。
数据访问统一收敛到 ResearchReportRepository，本层只保留业务编排与磁盘 IO。
"""

import hashlib
import logging
import threading
import time
import traceback
from datetime import datetime

from backend.common.llm_logger import log_llm_usage
from backend.config.config import BASE_DIR
from backend.repositories.research_report_repository import ResearchReportRepository
from backend.research_report.constants import FIGURE_MAX_PER_REPORT
from backend.research_report.llm import (
    analyze_report,
    get_research_model_name,
    resolve_provider_model,
)
from backend.research_report.parser import ParseResult, parse_pdf

logger = logging.getLogger(__name__)

DATA_ROOT = BASE_DIR / "data"
FIGURE_ROOT = DATA_ROOT / "pdf" / "research"
PDF_ROOT = DATA_ROOT / "pdf" / "research" / "original"


# ========================================================================
# 辅助函数
# ========================================================================


def _infer_report_type(industry: list[str], title: str) -> str:
    """从行业和标题推断报告类型"""
    t = " ".join(industry) + title
    if any(kw in t for kw in ["固收", "债券", "国债", "债市", "宏观", "GDP"]):
        return "macro"
    if any(kw in t for kw in ["策略", "周报", "晨会", "日报"]):
        return "strategy"
    if any(kw in t for kw in ["公司", "深度"]):
        return "company"
    return "industry"


def _compute_hash_from_bytes(data: bytes) -> str:
    """计算 PDF bytes 的 SHA-256 前 16 字符"""
    return hashlib.sha256(data).hexdigest()[:16]


def _write_figures(figures: list[dict], file_hash: str) -> list[dict]:
    """将图片 bytes 写入磁盘，返回写入后的 figure 字典列表（含 image_path）"""
    hash_dir = FIGURE_ROOT / "figure" / file_hash
    if hash_dir.exists():
        import shutil

        shutil.rmtree(hash_dir)
    hash_dir.mkdir(parents=True, exist_ok=True)

    result = []
    for fig in figures:
        img_bytes = fig.pop("bytes")
        fig.pop("width", None)
        fig.pop("height", None)
        fig_path = hash_dir / f'p{fig["page_number"]}_f{fig["figure_order"]}.png'
        fig_path.write_bytes(img_bytes)
        fig["image_path"] = str(fig_path.relative_to(FIGURE_ROOT))
        fig["image_size_kb"] = len(img_bytes) // 1024
        result.append(fig)
    return result


# ========================================================================
# 上传入库
# ========================================================================


def ingest_uploaded_pdf(
    pdf_bytes: bytes,
    original_filename: str,
    uploaded_by: str = "web",
    source: str = "web_upload",
) -> dict:
    """
    接收上传的 PDF bytes，完成：哈希计算、查重、存盘、解析、入库、图片写入。

    参数:
        pdf_bytes: PDF 文件原始字节
        original_filename: 原始文件名（用于日志）
        uploaded_by: 上传者标识
        source: 来源标签

    返回:
        {"report_id": int, "title": str, "status": str, "is_duplicate": bool}
    """
    repository = ResearchReportRepository.from_environment()

    # 计算哈希 + 查重
    file_hash = _compute_hash_from_bytes(pdf_bytes)
    existing = repository.find_by_hash(file_hash)

    if existing:
        logger.info("重复文件: hash=%s existing_id=%d", file_hash, existing["id"])
        return {
            "report_id": existing["id"],
            "title": existing["title"],
            "status": existing["status"],
            "is_duplicate": True,
        }

    # 存盘：按月份归档
    archive_month = datetime.now().strftime("%Y/%m")
    dest_dir = PDF_ROOT / archive_month
    dest_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = dest_dir / f"{file_hash}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    logger.info(
        "PDF 已保存: %s (%d KB)", original_filename[:60], len(pdf_bytes) // 1024
    )

    # 解析 PDF
    try:
        result: ParseResult = parse_pdf(pdf_path)
    except Exception as e:
        # 清理遗留文件
        if pdf_path.exists():
            pdf_path.unlink()
        raise RuntimeError(f"PDF 解析失败: {e}")

    if len(result.full_text) < 50:
        logger.warning("全文过短(%d字): %s", len(result.full_text), original_filename)

    # 推断类型
    report_type = _infer_report_type(result.industry, result.title)

    # 写入图片到磁盘
    figures = _write_figures(result.figures, result.file_hash)

    # 计算相对路径
    try:
        rel_path = str(pdf_path.relative_to(DATA_ROOT))
    except ValueError:
        rel_path = str(pdf_path)

    # 入库（研报 + 图表，单事务）
    report_id = repository.ingest_report(
        {
            "title": result.title[:512],
            "institution": result.institution,
            "analyst": ", ".join(result.analyst) if result.analyst else None,
            "publish_date": result.publish_date,
            "industry": ", ".join(result.industry) if result.industry else None,
            "symbols": ", ".join(result.symbols) if result.symbols else None,
            "report_type": report_type,
            "rel_path": rel_path[:512],
            "file_hash": result.file_hash,
            "file_size_kb": result.file_size_kb,
            "page_count": result.page_count,
            "full_text": result.full_text,
            "source": source,
            "uploaded_by": uploaded_by,
        },
        figures,
    )

    inst = result.institution or "-"
    logger.info(
        "入库完成: id=%d | %s | %s | %d图 | %d页",
        report_id,
        inst,
        result.title[:40],
        len(figures),
        result.page_count,
    )
    return {
        "report_id": report_id,
        "title": result.title,
        "status": "parsed",
        "is_duplicate": False,
    }


# ========================================================================
# 异步 AI 分析
# ========================================================================


def run_analysis_async(report_id: int, model: str | None = None):
    """
    在后台线程中启动 AI 分析，立即返回。

    参数:
        report_id: 研报 ID
        model: provider model 全名，默认取研报默认模型
    """
    model = model or resolve_provider_model()

    def _run():
        _analyze_report_sync(report_id, model)

    t = threading.Thread(
        target=_run,
        name=f"research-analyze-{report_id}",
        daemon=True,
    )
    t.start()
    logger.info("后台分析已启动: report_id=%d model=%s", report_id, model)


def _analyze_report_sync(report_id: int, model: str):
    """同步执行 AI 分析（在后台线程中调用）"""
    repository = ResearchReportRepository.from_environment()
    model_short = get_research_model_name()
    t_start = time.time()
    try:
        # 1. 抢占任务锁
        if not repository.claim_for_analysis(report_id):
            logger.warning(
                "抢占失败 report_id=%d（可能已被处理或状态不合法）", report_id
            )
            return

        # 2. 加载研报数据与图表
        analysis_input = repository.get_analysis_input(
            report_id, figure_limit=FIGURE_MAX_PER_REPORT
        )
        if analysis_input is None:
            logger.error("研报不存在 report_id=%d", report_id)
            return
        title, full_text, image_paths = analysis_input
        figure_paths = []
        for p in image_paths:
            fp = DATA_ROOT / p
            if fp.exists():
                figure_paths.append(fp)

        # 3. LLM 分析
        parsed, raw, usage = analyze_report(
            full_text,
            figure_paths=figure_paths if figure_paths else None,
            model=model,
        )
        elapsed = time.time() - t_start

        if "error" in parsed:
            logger.warning(
                "LLM 解析警告 report_id=%d: %s", report_id, parsed["error"][:100]
            )

        # 4. 写入分析结果
        repository.finish_analysis(
            report_id, model_name=model_short, parsed=parsed, raw=raw
        )

        # 5. 记录 LLM 用量
        log_llm_usage(
            call_source="research",
            model_name=model_short,
            provider_model=model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            success=True,
        )

        logger.info(
            "分析完成 report_id=%d [%s] view=%s tokens=%d elapsed=%.1fs",
            report_id,
            title[:40],
            parsed.get("market_view", "?"),
            usage.get("total_tokens", 0),
            elapsed,
        )

    except Exception as e:
        err = str(e)[:500]
        logger.error(
            "分析失败 report_id=%d: %s\n%s", report_id, err, traceback.format_exc()
        )

        try:
            repository.mark_analysis_failed(report_id, err)
        except Exception:
            logger.error("写入失败状态时出错", exc_info=True)

        log_llm_usage(
            call_source="research",
            model_name=model_short,
            provider_model=model,
            success=False,
            error_message=err,
        )