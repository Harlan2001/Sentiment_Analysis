"""综合研报执行编排；HTTP 入口只入队，由统一调度器调用本模块。"""

from __future__ import annotations

import logging
from collections.abc import Callable

from backend.common.llm_logger import log_llm_usage
from backend.repositories.report_generation_repository import ReportGenerationRepository
from backend.research_report.llm import resolve_provider_model
from backend.research_report.synthesis import generate_research_synthesis

logger = logging.getLogger(__name__)

CALL_SOURCE = "report_generation"


def _run_report_generation(
    task_id: str,
    model: str | None = None,
    *,
    owner_username: str | None = None,
    lease_token: str | None = None,
    run_id: int | None = None,
    stage_callback: Callable[[str, str], None] | None = None,
) -> None:
    repository = ReportGenerationRepository.from_environment()
    if owner_username is not None:
        task = repository.get_task(owner_username, task_id)
    else:
        # 兼容旧内部调用；统一调度器不会重复 claim。
        task = repository.claim_task(task_id)
    if not task:
        raise RuntimeError("综合研报任务不存在或状态已变化")

    requested_model = model or task.get("requested_model")
    try:
        if stage_callback:
            stage_callback("loading", "正在读取来源研报与观点快照")
        sources = repository.load_sources([int(item) for item in task["report_ids_json"]])
        if stage_callback:
            stage_callback("generating", "正在生成综合研报")
        result, usage, provider_model = generate_research_synthesis(
            title=task["title"],
            requirement=task["requirement"],
            sources=sources,
            date_start=task.get("date_start"),
            date_end=task.get("date_end"),
            model=resolve_provider_model(requested_model) if requested_model else None,
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
        if stage_callback:
            stage_callback("saving", "综合研报已生成，正在保存结果")
        repository.finish_task_success(
            task_id,
            model_name=provider_model,
            result_markdown=result,
            lease_token=lease_token,
            run_id=run_id,
        )
        logger.info("研报生成完成: task_id=%s sources=%d", task_id, len(sources))
    except Exception as exc:
        logger.exception("研报生成失败: task_id=%s", task_id)
        log_llm_usage(
            call_source=CALL_SOURCE,
            model_name="research-default",
            provider_model="research-default",
            success=False,
            error_message=str(exc),
        )
        if lease_token is None:
            repository.finish_task_failed(task_id, f"生成失败：{exc}")
        else:
            raise


def start_report_generation(task_id: str, model: str | None = None) -> None:
    """兼容原入口：保留 queued 状态、保存模型选择并唤醒调度器。"""
    from backend.task_execution.dispatcher import wake_dispatcher
    from backend.task_execution.queue import AITaskQueue

    queued = AITaskQueue.from_environment().enqueue(
        "report_generation",
        task_id,
        allowed_statuses=("queued",),
        requested_model=model,
    )
    if queued:
        wake_dispatcher()
