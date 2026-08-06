"""策略每日定时自动生成模块（轻量 asyncio 后台任务，无需额外调度依赖）。

按配置的触发时间（STRATEGY_AUTO_CRON，取小时字段）每日自动调用
get_or_create_recommendation 生成当日 AI 策略推荐并入库。
"""

import asyncio
import logging
from datetime import datetime, timedelta

from backend.config.config import STRATEGY_AUTO_CRON, STRATEGY_AUTO_ENABLED
from backend.strategy.strategy_recommendation import get_or_create_recommendation

logger = logging.getLogger(__name__)

_scheduler_task: "asyncio.Task | None" = None


def _parse_hour(cron: str) -> int:
    """从 'M H * * *' / 'H * * * *' 解析小时字段，默认 9。"""
    try:
        parts = cron.strip().split()
        if len(parts) >= 2:
            return int(parts[1]) % 24
    except (ValueError, IndexError):
        pass
    return 9


async def _run_daily() -> None:
    hour = _parse_hour(STRATEGY_AUTO_CRON)
    logger.info("策略自动生成任务已启动，每日 %02d:00 运行", hour)
    while True:
        now = datetime.now()
        next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        delay = (next_run - now).total_seconds()
        logger.info("策略自动生成将在 %.1f 秒后（%s）执行", delay, next_run.isoformat())
        await asyncio.sleep(delay)
        try:
            logger.info("开始自动生成当日 AI 策略推荐...")
            await get_or_create_recommendation(target_date=None, force_refresh=False)
            logger.info("当日 AI 策略推荐自动生成完成")
        except Exception as exc:
            logger.exception("自动生成 AI 策略推荐失败: %s", exc)


def start_strategy_scheduler() -> None:
    """启动每日自动生成后台任务（幂等）。"""
    global _scheduler_task
    if not STRATEGY_AUTO_ENABLED:
        logger.info("STRATEGY_AUTO_ENABLED=false，跳过策略自动生成任务")
        return
    if _scheduler_task and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(_run_daily())


def stop_strategy_scheduler() -> None:
    """停止自动生成后台任务。"""
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
