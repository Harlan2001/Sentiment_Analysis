"""研报生成异步编排，复用既有研报读取与 AI 客户端。"""

from __future__ import annotations

import logging
import threading

from backend.common.llm_logger import log_llm_usage
from backend.repositories.report_generation_repository import ReportGenerationRepository
from backend.research_report.llm import resolve_provider_model
from backend.research_report.synthesis import generate_research_synthesis

logger = logging.getLogger(__name__)

CALL_SOURCE = "report_generation"


def _run_report_generation(task_id: str, model: str | None = None) -> None:
    repository = ReportGenerationRepository.from_environment()
    task = repository.claim_task(task_id)
    if not task:
        return

    try:
        sources = repository.load_sources([int(item) for item in task["report_ids_json"]])
        result, usage, provider_model = generate_research_synthesis(
            title=task["title"],
            requirement=task["requirement"],
            sources=sources,
            date_start=task.get("date_start"),
            date_end=task.get("date_end"),
            model=resolve_provider_model(model) if model else None,
        )
        log_llm_usage(
            call_source=CALL_SOURCE,
            model_name=provider_model,
            provider_model=provider_model,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            success=True,
            latency_ms=usage["latency_ms"],
        )
        repository.finish_task_success(
            task_id, model_name=provider_model, result_markdown=result
        )
        logger.info("研报生成完成: task_id=%s sources=%d", task_id, len(sources))
    except Exception as exc:
        logger.exception("研报生成失败: task_id=%s", task_id)
        # log_llm_usage 内部已吞掉写库异常（llm_logger），失败日志无需再套 try/except
        log_llm_usage(
            call_source=CALL_SOURCE,
            model_name="research-default",
            provider_model="research-default",
            success=False,
            error_message=str(exc),
        )
        repository.finish_task_failed(task_id, f"生成失败：{exc}")


def start_report_generation(task_id: str, model: str | None = None) -> None:
    """后台启动综合研报生成。``model`` 为模型短名（None 用默认模型）。"""
    thread = threading.Thread(
        target=_run_report_generation,
        args=(task_id, model),
        name=f"report-generation-{task_id[:8]}",
        daemon=True,
    )
    thread.start()
