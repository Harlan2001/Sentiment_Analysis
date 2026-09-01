"""复用真实新闻查询与既有 AI completion 生成按日新闻总结。"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import Any

from backend.common.llm_call import llm_chat_async
from backend.common.llm_logger import log_llm_usage
from backend.config.config import get_analysis_model_info, get_default_analysis_model_name
from backend.repositories.news_summary_repository import DailyNewsSummaryRepository
from backend.routers.news import get_news

logger = logging.getLogger(__name__)

MODEL_NAME = get_default_analysis_model_name()

CHUNK_SIZE = 80
MAX_REFERENCES = 500
MODEL_CALL_TIMEOUT_SECONDS = 90
SUMMARY_MAX_TOKENS = 4096
FINAL_CHUNK_CHARS = 1800
SYSTEM_PROMPT = """你是专业的中国债券市场新闻编辑。请只基于用户提供的真实新闻条目生成中文 Markdown 总结。
要求：归纳主题与因果链，不逐条堆砌；区分事实与判断；保留日期范围和来源统计；列出重要事件、利率债/信用债/宏观流动性影响、风险与后续关注；不得编造条目中没有的数据，不给出具体投资建议。"""


def _news_line(item: dict[str, Any]) -> str:
    reason = " ".join(str(item.get("reason") or "待分析").split())[:260]
    return (
        f"- [{item.get('id')}] {item.get('publish_time')} | {item.get('source')} | "
        f"{item.get('direction')}/{item.get('horizon')} | {item.get('title')} | {reason}"
    )


async def _complete(prompt: str, username: str, *, max_tokens: int) -> str:
    provider_model = get_analysis_model_info(MODEL_NAME)["provider_model"]
    try:
        content = await asyncio.wait_for(
            llm_chat_async(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model=MODEL_NAME,
                provider_model=provider_model,
                call_source="daily_news_summary",
                temperature=0.2,
                max_tokens=max_tokens,
                timeout=MODEL_CALL_TIMEOUT_SECONDS,
                retry=True,
            ),
            timeout=MODEL_CALL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        message = f"模型网关在 {MODEL_CALL_TIMEOUT_SECONDS} 秒内未返回"
        log_llm_usage(
            username=username,
            call_source="daily_news_summary",
            model_name=MODEL_NAME,
            provider_model=provider_model,
            success=False,
            error_message=message,
        )
        raise RuntimeError(message) from exc
    if not content.strip():
        message = "AI 未返回总结内容"
        log_llm_usage(
            username=username,
            call_source="daily_news_summary",
            model_name=MODEL_NAME,
            provider_model=provider_model,
            success=False,
            error_message=message,
        )
        raise RuntimeError(message)
    return content.strip()


async def generate_daily_news_summary(
    repository: DailyNewsSummaryRepository,
    owner_username: str,
    task_id: int,
) -> None:
    task = await asyncio.to_thread(repository.get_task, owner_username, task_id)
    if not task or not await asyncio.to_thread(
        repository.mark_running, owner_username, task_id
    ):
        return
    try:
        source_keys = task.get("sources_json") or []
        items = await asyncio.to_thread(
            get_news,
            date=None,
            start_date=task["start_date"],
            end_date=task["end_date"],
            source=",".join(source_keys) if source_keys else None,
            model=None,
            view="best",
        )
        source_stats = dict(
            Counter(str(item.get("source") or "数据源") for item in items)
        )
        references = [
            {
                "news_id": item.get("id"),
                "title": item.get("title"),
                "publish_time": item.get("publish_time"),
                "source": item.get("source"),
                "direction": item.get("direction"),
                "horizon": item.get("horizon"),
            }
            for item in items[:MAX_REFERENCES]
        ]
        if not items:
            await asyncio.to_thread(
                repository.complete_task,
                owner_username,
                task_id,
                status="empty",
                news_count=0,
                source_stats={},
                summary="该日期范围和来源下没有可总结的新闻，未调用 AI。",
                references=[],
            )
            return

        focus = str(task.get("focus") or "无额外关注重点")
        header = (
            f"日期范围：{task['start_date']} 至 {task['end_date']}\n"
            f"来源统计：{source_stats}\n关注重点：{focus}\n"
        )
        chunk_summaries: list[str] = []
        for index in range(0, len(items), CHUNK_SIZE):
            chunk = items[index : index + CHUNK_SIZE]
            prompt = (
                header
                + f"这是第 {index // CHUNK_SIZE + 1} 批，共 {len(items)} 条新闻中的 {len(chunk)} 条。"
                + "请生成可供最终汇总使用的分批摘要。\n\n"
                + "\n".join(_news_line(item) for item in chunk)
            )
            chunk_summaries.append(
                await _complete(
                    prompt, owner_username, max_tokens=SUMMARY_MAX_TOKENS
                )
            )

        if len(chunk_summaries) == 1:
            summary = chunk_summaries[0]
        else:
            final_material = "\n\n---\n\n".join(
                item[:FINAL_CHUNK_CHARS] for item in chunk_summaries
            )
            try:
                summary = await _complete(
                    header
                    + f"以下是 {len(items)} 条真实新闻的分批摘要。请合并去重，输出一份完整的每日新闻总结。"
                    + "开头注明共覆盖多少条新闻，并保留重要新闻编号引用。\n\n"
                    + final_material,
                    owner_username,
                    max_tokens=SUMMARY_MAX_TOKENS,
                )
            except RuntimeError as exc:
                logger.warning(
                    "Daily-news final merge timed out; storing completed batch summaries: %s",
                    exc,
                )
                summary = (
                    "# 每日新闻总结（分批结果）\n\n"
                    "> 自动合并未及时返回；以下为已经完成的分批 AI 摘要。\n\n"
                    + "\n\n---\n\n".join(
                        f"## 第 {index + 1} 批摘要\n\n{item}"
                        for index, item in enumerate(chunk_summaries)
                    )
                )
        await asyncio.to_thread(
            repository.complete_task,
            owner_username,
            task_id,
            status="succeeded",
            news_count=len(items),
            source_stats=source_stats,
            summary=summary,
            references=references,
        )
    except Exception as exc:
        logger.exception("Daily-news summary task %s failed", task_id)
        await asyncio.to_thread(
            repository.fail_task,
            owner_username,
            task_id,
            f"新闻总结生成失败：{str(exc)}",
        )
