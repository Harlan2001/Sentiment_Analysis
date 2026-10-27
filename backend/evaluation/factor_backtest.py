"""因子事件研究（回测仿真）。

用 ``news_factor`` 做事件研究：某因子在 t 时刻出现（带 direction），
观察之后 T+N 个交易日的 10Y 国债收益率变动。

## 两条硬纪律

1. **严格防未来函数** —— 信号日 t 只用 t 及之前的数据；收益从 t+1 起算。
   这是最容易出错、也最容易让结果虚好的地方，有专门测试覆盖。
2. **按交易日对齐** —— 用 yield_data 的日期序列推进 T+N，不按自然日。
   该日期集合即中债估值发布日历（含调休补班日），无需引入节假日依赖。

## 方向语义

``positive``（利多债券）→ 收益率下行记为命中；``negative`` 反之。
``neutral`` 不参与命中率统计（无方向可判）。

## 展示口径

同时给出**多数类基准**（事后无脑猜多数方向的命中率）—— 方向命中率的
正确对照线不是 50%，而是这个。基准与命中率同屏，由用户自行判断，
不对因子下"有效/无效"的结论。
"""

from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from backend.repositories.forecast_evaluation_repository import (
    EVALUATION_PERIOD,
    ForecastEvaluationRepository,
)

logger = logging.getLogger(__name__)

# 持有期（交易日）
HOLDING_DAYS: tuple[int, ...] = (1, 5, 20)
# 进入统计的最小样本数（低于此仍计算，但前端会标注样本不足）
MIN_SAMPLES = 20


@dataclass
class EventRow:
    """单条因子事件。"""

    pub_time: datetime
    direction: str


class _Calendar:
    """交易日历：基于 yield_data 的日期序列按序号推进 T+N。"""

    def __init__(self, series: list[tuple[date, float]]):
        self.dates = [item[0] for item in series]
        self.values = [item[1] for item in series]

    def index_of(self, target: date) -> int | None:
        """交易日序号；非交易日返回 None。"""
        position = bisect.bisect_left(self.dates, target)
        if position < len(self.dates) and self.dates[position] == target:
            return position
        return None

    def value_at(self, index: int, offset: int) -> float | None:
        """从 index 起向后 offset 个交易日的收益率。"""
        target = index + offset
        if target < 0 or target >= len(self.values):
            return None
        return self.values[target]


def _to_date(value: Any) -> date | None:
    """归一为 date；datetime 取日期部分。"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def evaluate_factor(
    events: list[EventRow], calendar: _Calendar, holding_days: int
) -> dict[str, Any]:
    """对一批事件做单持有期的事件研究。

    返回样本数、命中数、命中率、多数类基准、平均/中位数变动、区间。
    样本为空时各统计量为 None（不臆断）。
    """
    moves: list[float] = []
    hits = 0
    counted = 0
    span_start: date | None = None
    span_end: date | None = None

    for event in events:
        event_date = _to_date(event.pub_time)
        if event_date is None:
            continue
        index = calendar.index_of(event_date)
        if index is None:
            continue
        base = calendar.value_at(index, 0)
        future = calendar.value_at(index, holding_days)
        if base is None or future is None:
            continue

        move_bp = (future - base) * 100
        moves.append(move_bp)
        if span_start is None or event_date < span_start:
            span_start = event_date
        if span_end is None or event_date > span_end:
            span_end = event_date

        direction = (event.direction or "").strip().lower()
        if direction == "neutral":
            continue
        # positive = 利多债券 → 收益率下行才算命中
        expect_down = direction == "positive"
        hit = (move_bp < 0) if expect_down else (move_bp > 0)
        hits += 1 if hit else 0
        counted += 1

    if counted == 0:
        return {
            "sample_size": 0,
            "hit_count": 0,
            "hit_rate": None,
            "majority_base": None,
            "avg_move_bp": None,
            "median_move_bp": None,
            "period_start": None,
            "period_end": None,
        }

    down = sum(1 for move in moves if move < 0)
    total = len(moves)
    majority_base = max(down, total - down) / total
    ordered = sorted(moves)
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2
    )

    return {
        "sample_size": counted,
        "hit_count": hits,
        "hit_rate": round(hits / counted, 4),
        "majority_base": round(majority_base, 4),
        "avg_move_bp": round(sum(moves) / total, 4),
        "median_move_bp": round(median, 4),
        "period_start": span_start,
        "period_end": span_end,
    }


def build_event_rows(rows: list[tuple[Any, str]]) -> list[EventRow]:
    """把仓储返回的 (pub_time, direction) 元组转为事件对象。"""
    return [EventRow(pub_time=pub, direction=dir_) for pub, dir_ in rows]


def trading_calendar() -> _Calendar:
    """构建交易日历（复用预测诊断的收益率序列读取）。"""
    repository = ForecastEvaluationRepository.from_environment()
    return _Calendar(repository.list_yield_series(EVALUATION_PERIOD))