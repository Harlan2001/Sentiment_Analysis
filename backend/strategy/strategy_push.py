from __future__ import annotations

import asyncio
import contextlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from openai import OpenAI

from backend.common.database import get_db_connection
from backend.config.config import ANALYSIS_MODEL_PRIORITY

STRATEGY_TZ = ZoneInfo("Asia/Shanghai")
STRATEGY_MODEL = os.getenv(
    "STRATEGY_MODEL", "aliyun/glm-5.2"
)


@dataclass
class StrategyRuntimeConfig:
    model: str = STRATEGY_MODEL
    tz: ZoneInfo = STRATEGY_TZ


class StrategyPushService:
    def __init__(
        self, llm_client: OpenAI, runtime_config: Optional[StrategyRuntimeConfig] = None
    ):
        self._llm_client = llm_client
        self._cfg = runtime_config or StrategyRuntimeConfig()

        self._subscribers: set[asyncio.Queue[str]] = set()
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._window_start: Optional[datetime] = None
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _slot_key(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M")

    def _compute_window_start(self, now: datetime) -> datetime:
        boundary = now.replace(hour=20, minute=30, second=0, microsecond=0)
        if now >= boundary:
            return boundary
        return boundary - timedelta(days=1)

    @staticmethod
    def _next_half_hour(now: datetime) -> datetime:
        this_hour_half = now.replace(minute=30, second=0, microsecond=0)
        if now < this_hour_half:
            return this_hour_half
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return next_hour.replace(minute=30)

    def _direction_normalized(self, direction: str) -> str:
        value = (direction or "").strip().lower()
        positive_alias = {
            "positive",
            "pos",
            "up",
            "bullish",
            "上涨",
            "利多",
            "看多",
            "正向",
        }
        negative_alias = {
            "negative",
            "neg",
            "down",
            "bearish",
            "下跌",
            "利空",
            "看空",
            "负向",
        }
        if value in positive_alias:
            return "positive"
        if value in negative_alias:
            return "negative"
        return ""

    def _delete_old_windows(self, window_start: datetime) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM strategy_push_history WHERE window_start < %s",
                    (window_start.replace(tzinfo=None),),
                )
            conn.commit()

    def _load_window_history(self, window_start: datetime) -> Dict[str, Dict[str, Any]]:
        snapshots: Dict[str, Dict[str, Any]] = {}
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT slot_time, window_start, window_end, status, strategy_text, news_count, error_message
                    FROM strategy_push_history
                    WHERE window_start = %s
                    ORDER BY slot_time ASC
                    """,
                    (window_start.replace(tzinfo=None),),
                )
                rows = cur.fetchall()

        for row in rows:
            slot_time = row[0]
            slot_dt = (
                slot_time.replace(tzinfo=self._cfg.tz)
                if isinstance(slot_time, datetime)
                else None
            )
            win_start_dt = (
                row[1].replace(tzinfo=self._cfg.tz)
                if isinstance(row[1], datetime)
                else window_start
            )
            win_end_dt = (
                row[2].replace(tzinfo=self._cfg.tz)
                if isinstance(row[2], datetime)
                else win_start_dt
            )
            if slot_dt is None:
                continue
            slot = self._slot_key(slot_dt)
            snapshots[slot] = {
                "slot": slot,
                "run_time": self._format_dt(slot_dt),
                "window_start": self._format_dt(win_start_dt),
                "window_end": self._format_dt(win_end_dt),
                "status": row[3],
                "strategy": row[4] or "",
                "news_count": row[5] or 0,
                "error": row[6],
            }
        return snapshots

    def _save_snapshot(self, snapshot: Dict[str, Any]) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO strategy_push_history (
                        slot_time, window_start, window_end, status, strategy_text, news_count, error_message
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        window_start = VALUES(window_start),
                        window_end = VALUES(window_end),
                        status = VALUES(status),
                        strategy_text = VALUES(strategy_text),
                        news_count = VALUES(news_count),
                        error_message = VALUES(error_message),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        datetime.strptime(snapshot["slot"], "%Y-%m-%d %H:%M"),
                        datetime.strptime(snapshot["window_start"], "%Y-%m-%d %H:%M"),
                        datetime.strptime(snapshot["window_end"], "%Y-%m-%d %H:%M"),
                        snapshot["status"],
                        snapshot["strategy"],
                        snapshot["news_count"],
                        snapshot["error"],
                    ),
                )
            conn.commit()

    def _query_news_with_reason(
        self, window_start: datetime, window_end: datetime
    ) -> List[Dict[str, Any]]:
        priority_cases = " ".join(
            [f"WHEN '{m}' THEN {i}" for i, m in enumerate(ANALYSIS_MODEL_PRIORITY)]
        )
        sql = f"""
            SELECT n.id, n.title, n.pub_time,
                   COALESCE(a.direction, '') AS direction,
                   COALESCE(a.reason, '') AS reason,
                   a.model
            FROM news n
            JOIN analysis a ON a.news_id = n.id
            WHERE n.pub_time >= %s
              AND n.pub_time <= %s
              AND a.reason IS NOT NULL
              AND TRIM(a.reason) <> ''
              AND a.model = (
                  SELECT a2.model
                  FROM analysis a2
                  WHERE a2.news_id = n.id
                  ORDER BY CASE a2.model
                      {priority_cases}
                      ELSE 999
                  END
                  LIMIT 1
              )
            ORDER BY n.pub_time ASC
        """

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        window_start.replace(tzinfo=None),
                        window_end.replace(tzinfo=None),
                    ),
                )
                rows = cur.fetchall()

        filtered: List[Dict[str, Any]] = []
        for row in rows:
            normalized = self._direction_normalized(row[3])
            if not normalized:
                continue
            filtered.append(
                {
                    "news_id": row[0],
                    "title": row[1],
                    "pub_time": row[2],
                    "direction": normalized,
                    "reason": row[4],
                    "model": row[5],
                }
            )
        return filtered

    def _build_reason_text(self, rows: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for idx, item in enumerate(rows, start=1):
            pub_time = item["pub_time"]
            if isinstance(pub_time, datetime):
                ts = pub_time.strftime("%Y-%m-%d %H:%M")
            else:
                ts = str(pub_time)
            lines.append(
                f"{idx}. 时间: {ts} | 方向: {item['direction']} | 标题: {item['title']} | 原因: {item['reason']}"
            )
        return "\n".join(lines)

    def _generate_strategy(
        self, rows: List[Dict[str, Any]], window_start: datetime, window_end: datetime
    ) -> str:
        if not rows:
            return "当前窗口内暂无可用于策略建议的有效新闻。"

        reason_text = self._build_reason_text(rows)
        prompt = f"""
你是中国债券市场策略分析师。

请基于以下时间窗口内的新闻分析理由（analysis.reason）生成一段“交易策略建议”。

要求：
1. 输出中文，控制在120-220字。
2. 只给一段可执行的方向性建议，不给具体买卖点位。
3. 必须体现风险提示。
4. 不要输出JSON，不要分点。

时间窗口：{self._format_dt(window_start)} 到 {self._format_dt(window_end)}
新闻条数：{len(rows)}

材料：
{reason_text}
"""

        response = self._llm_client.chat.completions.create(
            model=self._cfg.model,
            messages=[
                {
                    "role": "system",
                    "content": "你是专业、克制、客观的债券交易策略助手。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )
        content = response.choices[0].message.content or ""
        return content.strip() or "当前窗口内新闻已分析，但未生成有效策略建议。"

    def _run_snapshot_sync(
        self, slot_time: datetime, window_start: datetime
    ) -> Dict[str, Any]:
        rows = self._query_news_with_reason(
            window_start=window_start, window_end=slot_time
        )
        strategy_text = self._generate_strategy(
            rows, window_start=window_start, window_end=slot_time
        )
        return {
            "slot": self._slot_key(slot_time),
            "run_time": self._format_dt(slot_time),
            "window_start": self._format_dt(window_start),
            "window_end": self._format_dt(slot_time),
            "status": "success",
            "strategy": strategy_text,
            "news_count": len(rows),
            "error": None,
        }

    async def _run_snapshot(
        self, slot_time: datetime, window_start: datetime
    ) -> Dict[str, Any]:
        try:
            return await asyncio.to_thread(
                self._run_snapshot_sync, slot_time, window_start
            )
        except Exception as exc:
            return {
                "slot": self._slot_key(slot_time),
                "run_time": self._format_dt(slot_time),
                "window_start": self._format_dt(window_start),
                "window_end": self._format_dt(slot_time),
                "status": "failed",
                "strategy": "",
                "news_count": 0,
                "error": str(exc),
            }

    async def _build_payload_dict(self) -> Dict[str, Any]:
        async with self._lock:
            sorted_items = sorted(self._snapshots.values(), key=lambda x: x["slot"])
            return {
                "type": "strategy_full_snapshot",
                "generated_at": self._format_dt(datetime.now(self._cfg.tz)),
                "window_start": (
                    self._format_dt(self._window_start) if self._window_start else None
                ),
                "items": [
                    {
                        "run_time": item["run_time"],
                        "window_start": item["window_start"],
                        "window_end": item["window_end"],
                        "status": item["status"],
                        "news_count": item["news_count"],
                        "strategy": item["strategy"],
                        "error": item["error"],
                        "display_text": (
                            f"{item['run_time']} 交易策略建议：{item['strategy']}"
                            if item["status"] == "success"
                            else f"{item['run_time']} 交易策略建议生成失败：{item['error']}"
                        ),
                    }
                    for item in sorted_items
                ],
            }

    async def build_payload_json(self) -> str:
        payload = await self._build_payload_dict()
        return json.dumps(payload, ensure_ascii=False)

    async def get_snapshot(self) -> Dict[str, Any]:
        return await self._build_payload_dict()

    async def _broadcast_full_snapshot(self):
        payload = await self.build_payload_json()
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def _switch_window_if_needed(self, window_start: datetime) -> None:
        need_reload = False
        async with self._lock:
            if self._window_start != window_start:
                self._window_start = window_start
                self._snapshots = {}
                need_reload = True
        if need_reload:
            self._delete_old_windows(window_start)
            loaded = self._load_window_history(window_start)
            async with self._lock:
                self._snapshots = loaded

    async def _run_cycle(self, slot_time: datetime):
        window_start = self._compute_window_start(slot_time)
        await self._switch_window_if_needed(window_start)

        async with self._lock:
            failed_slots = [
                key
                for key, value in self._snapshots.items()
                if value.get("status") == "failed"
            ]

        for failed_slot in failed_slots:
            retry_time = datetime.strptime(failed_slot, "%Y-%m-%d %H:%M").replace(
                tzinfo=self._cfg.tz
            )
            retry_result = await self._run_snapshot(retry_time, window_start)
            self._save_snapshot(retry_result)
            async with self._lock:
                self._snapshots[failed_slot] = retry_result

        current_slot = self._slot_key(slot_time)
        current_result = await self._run_snapshot(slot_time, window_start)
        self._save_snapshot(current_result)
        async with self._lock:
            self._snapshots[current_slot] = current_result

        await self._broadcast_full_snapshot()

    async def trigger_now(self) -> Dict[str, Any]:
        now = datetime.now(self._cfg.tz).replace(second=0, microsecond=0)
        await self._run_cycle(now)
        return await self.get_snapshot()

    async def _scheduler_loop(self):
        while True:
            now = datetime.now(self._cfg.tz)
            next_run = self._next_half_hour(now)
            wait_seconds = max((next_run - now).total_seconds(), 0.0)
            await asyncio.sleep(wait_seconds)
            await self._run_cycle(next_run)

    async def start(self):
        current_window = self._compute_window_start(datetime.now(self._cfg.tz))
        await self._switch_window_if_needed(current_window)

        async with self._lock:
            if self._task and not self._task.done():
                return
            self._task = asyncio.create_task(
                self._scheduler_loop(), name="strategy-sse-scheduler"
            )

    async def stop(self):
        task: Optional[asyncio.Task] = None
        async with self._lock:
            if self._task:
                task = self._task
                self._task = None

        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=20)
        async with self._lock:
            self._subscribers.add(queue)
        queue.put_nowait(await self.build_payload_json())
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[str]):
        async with self._lock:
            self._subscribers.discard(queue)


_service_instance: Optional[StrategyPushService] = None


def get_strategy_push_service(llm_client: OpenAI) -> StrategyPushService:
    global _service_instance
    if _service_instance is None:
        _service_instance = StrategyPushService(llm_client=llm_client)
    return _service_instance
