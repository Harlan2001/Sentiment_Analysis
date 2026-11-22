"""基于 MySQL 持久化队列的有界 AI 任务调度器。"""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

from backend.config.config import (
    AI_TASK_DOMAIN_MAX_WORKERS,
    AI_TASK_HEARTBEAT_SECONDS,
    AI_TASK_LEASE_SECONDS,
    AI_TASK_MAX_WORKERS,
    AI_TASK_POLL_SECONDS,
)
from backend.task_execution.queue import AITaskQueue, TaskHandle

logger = logging.getLogger(__name__)
_default_dispatcher: AITaskDispatcher | None = None


class AITaskDispatcher:
    def __init__(
        self,
        *,
        queue: Any | None = None,
        max_workers: int = AI_TASK_MAX_WORKERS,
        domain_max_workers: int = AI_TASK_DOMAIN_MAX_WORKERS,
        poll_seconds: int = AI_TASK_POLL_SECONDS,
        lease_seconds: int = AI_TASK_LEASE_SECONDS,
        heartbeat_seconds: int = AI_TASK_HEARTBEAT_SECONDS,
    ) -> None:
        self.queue = queue or AITaskQueue.from_environment()
        self.max_workers = max(1, max_workers)
        self.domain_max_workers = max(1, domain_max_workers)
        self.poll_seconds = max(1, poll_seconds)
        self.lease_seconds = max(lease_seconds, heartbeat_seconds * 2, 10)
        self.heartbeat_seconds = max(1, heartbeat_seconds)
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="ai-task"
        )
        self._wake = asyncio.Event()
        self._poll_task: asyncio.Task | None = None
        self._active: dict[asyncio.Task, TaskHandle] = {}
        self._active_keys: set[tuple[str, str]] = set()
        self._domain_counts: dict[str, int] = {}
        self._stopping = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._next_recovery = 0.0

    @property
    def active_count(self) -> int:
        return len(self._active)

    async def start(self) -> None:
        if self._poll_task and not self._poll_task.done():
            return
        self._loop = asyncio.get_running_loop()
        self._stopping = False
        recovered = await asyncio.to_thread(self.queue.recover_interrupted)
        if recovered:
            logger.warning("已将 %s 个服务中断的 AI 任务标记为可重试失败", recovered)
        self._next_recovery = time.monotonic() + 30
        self._poll_task = asyncio.create_task(self._poll_loop(), name="ai-task-dispatcher")

    def wake(self) -> None:
        if self._loop and not self._stopping:
            self._loop.call_soon_threadsafe(self._wake.set)

    async def _poll_loop(self) -> None:
        while not self._stopping:
            try:
                if time.monotonic() >= self._next_recovery:
                    await asyncio.to_thread(self.queue.recover_interrupted)
                    self._next_recovery = time.monotonic() + 30
                queued = await asyncio.to_thread(self.queue.list_queued)
                for task_type, domain_id in queued:
                    if self._stopping or len(self._active) >= self.max_workers:
                        break
                    key = (task_type, domain_id)
                    if key in self._active_keys:
                        continue
                    if self._domain_counts.get(task_type, 0) >= self.domain_max_workers:
                        continue
                    handle = await asyncio.to_thread(
                        self.queue.claim, task_type, domain_id, lease_seconds=self.lease_seconds
                    )
                    if handle is None:
                        continue
                    self._active_keys.add(key)
                    self._domain_counts[task_type] = self._domain_counts.get(task_type, 0) + 1
                    task = asyncio.create_task(
                        self._execute(handle), name=f"ai-task-{task_type}-{domain_id}"
                    )
                    self._active[task] = handle
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("AI 任务调度轮询失败")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self.poll_seconds)
                self._wake.clear()
            except TimeoutError:
                pass

    async def _heartbeat(self, handle: TaskHandle) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            valid = await asyncio.to_thread(
                self.queue.heartbeat, handle, lease_seconds=self.lease_seconds
            )
            if not valid:
                logger.warning("AI 任务租约已失效: %s:%s", handle.task_type, handle.domain_id)
                return

    def _execute_sync(self, handle: TaskHandle) -> None:
        callback = partial(self.queue.update_stage, handle)
        if handle.task_type == "research_report":
            from backend.research_report.llm import resolve_provider_model
            from backend.research_report.service import _analyze_report_sync

            _analyze_report_sync(
                int(handle.domain_id),
                handle.requested_model or resolve_provider_model(),
                lease_token=handle.lease_token,
                run_id=handle.run_id,
                stage_callback=callback,
            )
        elif handle.task_type == "policy_document":
            from backend.policy_document.service import run_analysis

            run_analysis(
                int(handle.domain_id),
                handle.owner_username,
                lease_token=handle.lease_token,
                run_id=handle.run_id,
                stage_callback=callback,
            )
        elif handle.task_type == "report_generation":
            from backend.report.generation_service import _run_report_generation

            _run_report_generation(
                handle.domain_id,
                owner_username=handle.owner_username,
                lease_token=handle.lease_token,
                run_id=handle.run_id,
                stage_callback=callback,
            )
        else:
            raise RuntimeError(f"不支持的同步任务类型: {handle.task_type}")

    async def _execute(self, handle: TaskHandle) -> None:
        heartbeat = asyncio.create_task(self._heartbeat(handle))
        try:
            if handle.task_type == "daily_news":
                from backend.news_summary.service import generate_daily_news_summary
                from backend.repositories.news_summary_repository import (
                    DailyNewsSummaryRepository,
                )

                await generate_daily_news_summary(
                    DailyNewsSummaryRepository.from_environment(),
                    handle.owner_username,
                    int(handle.domain_id),
                    lease_token=handle.lease_token,
                    run_id=handle.run_id,
                    stage_callback=partial(self.queue.update_stage, handle),
                )
            else:
                await asyncio.get_running_loop().run_in_executor(
                    self._executor, self._execute_sync, handle
                )
        except asyncio.CancelledError:
            await asyncio.to_thread(self.queue.fail, handle, "服务中断，请确认后重试")
            raise
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            logger.exception("AI 任务失败: %s:%s", handle.task_type, handle.domain_id)
            await asyncio.to_thread(self.queue.fail, handle, message)
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            current = asyncio.current_task()
            if current in self._active:
                del self._active[current]
            self._active_keys.discard((handle.task_type, handle.domain_id))
            count = self._domain_counts.get(handle.task_type, 1) - 1
            self._domain_counts[handle.task_type] = max(0, count)
            self._wake.set()

    async def stop(self) -> None:
        self._stopping = True
        if self._poll_task:
            self._poll_task.cancel()
            await asyncio.gather(self._poll_task, return_exceptions=True)
            self._poll_task = None
        tasks = list(self._active)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._executor.shutdown(wait=False, cancel_futures=True)


async def start_dispatcher(app: Any) -> AITaskDispatcher:
    global _default_dispatcher
    dispatcher = AITaskDispatcher()
    app.state.ai_task_dispatcher = dispatcher
    _default_dispatcher = dispatcher
    await dispatcher.start()
    return dispatcher


async def stop_dispatcher(app: Any) -> None:
    global _default_dispatcher
    dispatcher = getattr(app.state, "ai_task_dispatcher", None)
    if dispatcher:
        await dispatcher.stop()
    if _default_dispatcher is dispatcher:
        _default_dispatcher = None


def wake_dispatcher() -> None:
    if _default_dispatcher:
        _default_dispatcher.wake()
