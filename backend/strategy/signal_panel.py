"""策略生成的因子信号面板。

从 381 个非结构化因子里筛出"经历史检验过关"的那一小批，算出当前方向与强度，
序列化成可注入 DreamStrategy 提示词、也可直接给前端展示的结构。

三条硬规则（与需求文档 FR-1 一致）：
1. 事件研究样本量 ``sample_size >= MIN_SAMPLE_SIZE``，样本太少的统计不可信；
2. 命中率必须跑赢多数类基准 ``hit_rate > majority_base``，跑不赢"无脑猜"就不该进面板；
3. 排除已知脏数据 code。

方向口径：全部是中国国债口径，positive = 利多债券 = 收益率下行。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from backend.common.database import build_in_placeholders, get_repo_connection
from backend.config.config import get_default_analysis_model_name

# 面板最多展示的因子数量：受提示词 token 预算约束（见 PANEL_TOKEN_BUDGET）。
DEFAULT_PANEL_SIZE = 8
# 事件研究的基准持有期，本期固定 T+5（T+1 仅 2 个因子过关、T+20 为 17 个）。
DEFAULT_HOLDING_DAYS = 5
# 样本量门槛：低于此值的命中率不足以支撑决策。
MIN_SAMPLE_SIZE = 20
# 信号衰减系数与时域阈值，沿用 /sapi/macro/signal 的口径，避免两套算法打架。
DEFAULT_DECAY_LAMBDA = 0.1
DIRECTIONAL_THRESHOLD = 0.3
# 窗口回退：近 7 天候选不足时放宽到 30 天。
PRIMARY_WINDOW_DAYS = 7
FALLBACK_WINDOW_DAYS = 30
# 近 7 天窗口至少要有这么多候选才用 7 天，否则回退。
MIN_CANDIDATES_FOR_PRIMARY_WINDOW = 3
# 已知模型违规占位 code，文档明确建议过滤。
EXCLUDED_FACTOR_CODES = ("NEW_FACTOR", "NEW_FACTOR_1")


@dataclass(frozen=True)
class FactorSignal:
    """一个过关因子在当前窗口下的状态摘要。"""

    code: str
    name: str
    category: str
    factor_type: str
    direction: str  # positive = 利多债券（收益率下行）
    signal_score: float  # [-1, 1]，时间衰减加权后的方向净值
    confidence: float
    event_count: int
    positive_count: int
    negative_count: int
    hit_rate: float | None
    majority_base: float | None
    sample_size: int
    holding_days: int
    latest_event_time: datetime | None

    @property
    def direction_label(self) -> str:
        return {"positive": "多", "negative": "空"}.get(self.direction, "中性")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "category": self.category,
            "factor_type": self.factor_type,
            "direction": self.direction,
            "direction_label": self.direction_label,
            "signal_score": round(self.signal_score, 4),
            "confidence": round(self.confidence, 4),
            "event_count": self.event_count,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "hit_rate": self.hit_rate,
            "majority_base": self.majority_base,
            "sample_size": self.sample_size,
            "holding_days": self.holding_days,
            "latest_event_time": (
                self.latest_event_time.isoformat()
                if self.latest_event_time
                else None
            ),
            # 口径标注：历史命中率来自全部模型混合的事件研究，不是单一模型。
            "caliber": "all_models",
        }


def _qualifying_factors(
    cursor, holding_days: int, min_samples: int
) -> dict[str, dict[str, Any]]:
    """取出同时满足样本量与跑赢基准的因子，附带命中率信息。"""
    placeholders = build_in_placeholders(EXCLUDED_FACTOR_CODES)
    cursor.execute(
        f"""SELECT s.factor_code, s.sample_size, s.hit_rate, s.majority_base,
                   f.id, f.name, f.category, f.factor_type
              FROM factor_event_study s
              JOIN factor f ON f.code = s.factor_code
             WHERE s.period_label = 'all'
               AND s.holding_days = %s
               AND s.sample_size >= %s
               AND s.hit_rate > s.majority_base
               AND f.code NOT IN ({placeholders})""",
        (holding_days, min_samples, *EXCLUDED_FACTOR_CODES),
    )
    qualified: dict[str, dict[str, Any]] = {}
    for row in cursor.fetchall():
        qualified[row["factor_code"]] = {
            "factor_id": row["id"],
            "name": (row["name"] or row["factor_code"]).strip(),
            "category": row["category"] or "",
            "factor_type": row["factor_type"] or "",
            "sample_size": int(row["sample_size"] or 0),
            "hit_rate": float(row["hit_rate"]) if row["hit_rate"] is not None else None,
            "majority_base": (
                float(row["majority_base"]) if row["majority_base"] is not None else None
            ),
        }
    return qualified


def _events_in_window(
    cursor,
    factor_ids: list[int],
    start_time: datetime,
    end_time: datetime,
    model_name: str,
) -> dict[int, list[tuple[str, datetime]]]:
    """窗口内每个因子的事件（方向, 发布时间）。

    固定单一 model：三个历史抽取模型的方向口径并不一致，混在一起算出的
    信号没有意义（对接文档 §9-1）。
    """
    if not factor_ids:
        return {}
    placeholders = build_in_placeholders(factor_ids)
    cursor.execute(
        f"""SELECT nf.factor_id AS factor_id,
                   LOWER(COALESCE(nf.direction, 'neutral')) AS direction,
                   nf.pub_time AS pub_time
              FROM news_factor nf
             WHERE nf.model = %s
               AND nf.factor_id IN ({placeholders})
               AND nf.pub_time > %s
               AND nf.pub_time <= %s
             ORDER BY nf.pub_time ASC""",
        (model_name, *factor_ids, start_time, end_time),
    )
    grouped: dict[int, list[tuple[str, datetime]]] = {}
    for row in cursor.fetchall():
        grouped.setdefault(row["factor_id"], []).append(
            (row["direction"], row["pub_time"])
        )
    return grouped


def _directional_score(
    events: list[tuple[str, datetime]],
    end_time: datetime,
    decay_lambda: float,
) -> tuple[float, float]:
    """时间衰减加权的方向净值与置信度（与 macro_signal 同一算法）。"""
    if not events:
        return 0.0, 0.0
    weighted_sum = weight_total = 0.0
    for direction, pub_time in events:
        delta_days = max((end_time - pub_time).total_seconds() / 86400.0, 0.0)
        weight = math.exp(-decay_lambda * delta_days)
        score = {"positive": 1.0, "negative": -1.0}.get(direction, 0.0)
        weighted_sum += score * weight
        weight_total += weight
    if weight_total <= 0:
        return 0.0, 0.0
    return weighted_sum / weight_total, min(weight_total / len(events), 1.0)


def _score_to_direction(score: float) -> str:
    if score >= DIRECTIONAL_THRESHOLD:
        return "positive"
    if score <= -DIRECTIONAL_THRESHOLD:
        return "negative"
    return "neutral"


def build_factor_signal_panel(
    reference_time: Optional[datetime] = None,
    model_name: Optional[str] = None,
    panel_size: int = DEFAULT_PANEL_SIZE,
    holding_days: int = DEFAULT_HOLDING_DAYS,
    min_samples: int = MIN_SAMPLE_SIZE,
    decay_lambda: float = DEFAULT_DECAY_LAMBDA,
) -> dict[str, Any]:
    """构造因子信号面板。

    :param reference_time: 情报锚点；早于它的数据才可用（防未来函数）。
    :param model_name: 固定使用的事件抽取模型，默认取配置中的在线模型。
    :return: ``{"items": [...], "window_days": 7, "model_name": "glm", ...}``
    """
    selected_model = model_name or get_default_analysis_model_name()

    with get_repo_connection() as conn:
        cursor = conn.cursor()
        if reference_time is None:
            reference_time = _resolve_reference_time(cursor, selected_model)

        qualified = _qualifying_factors(cursor, holding_days, min_samples)
        items, window_days = _build_items_with_fallback(
            cursor,
            qualified,
            reference_time,
            selected_model,
            panel_size,
            decay_lambda,
            holding_days,
        )

    return {
        "items": [item.to_dict() for item in items],
        "count": len(items),
        "window_days": window_days,
        "model_name": selected_model,
        "holding_days": holding_days,
        "min_samples": min_samples,
        "caliber": "all_models",
        "reference_time": reference_time.isoformat() if reference_time else None,
    }


def _resolve_reference_time(cursor, model_name: str) -> datetime:
    """情报锚点：优先用该模型最新的新闻发布时间，退化为当前时间。"""
    cursor.execute(
        "SELECT MAX(pub_time) AS latest FROM news_factor WHERE model = %s",
        (model_name,),
    )
    row = cursor.fetchone()
    latest_value = row["latest"] if row else None
    return latest_value or datetime.now()


def _build_items_with_fallback(
    cursor,
    qualified: dict[str, dict[str, Any]],
    reference_time: datetime,
    model_name: str,
    panel_size: int,
    decay_lambda: float,
    holding_days: int,
) -> tuple[list[FactorSignal], int]:
    """按 7 天 → 30 天回退取窗口，候选够用即停，不硬凑。"""
    if not qualified:
        return [], PRIMARY_WINDOW_DAYS

    factor_ids = [info["factor_id"] for info in qualified.values()]
    items: list[FactorSignal] = []
    window_days = PRIMARY_WINDOW_DAYS
    for candidate_days in (PRIMARY_WINDOW_DAYS, FALLBACK_WINDOW_DAYS):
        start_time = reference_time - timedelta(days=candidate_days)
        grouped = _events_in_window(
            cursor, factor_ids, start_time, reference_time, model_name
        )
        items = _assemble_items(
            qualified, grouped, reference_time, decay_lambda, holding_days
        )
        window_days = candidate_days
        if len(items) >= MIN_CANDIDATES_FOR_PRIMARY_WINDOW:
            break

    return _rank_and_trim(items, panel_size), window_days


def _assemble_items(
    qualified: dict[str, dict[str, Any]],
    grouped: dict[int, list[tuple[str, datetime]]],
    reference_time: datetime,
    decay_lambda: float,
    holding_days: int,
) -> list[FactorSignal]:
    """把窗口内的事件聚合成因子信号；窗口内无事件的因子不进入面板。"""
    items: list[FactorSignal] = []
    for code, info in qualified.items():
        events = grouped.get(info["factor_id"]) or []
        if not events:
            continue
        score, confidence = _directional_score(events, reference_time, decay_lambda)
        direction = _score_to_direction(score)
        if direction == "neutral":
            # 方向不明确就不是"信号"，放进去只会让模型为难。
            continue
        positive_count = sum(1 for d, _ in events if d == "positive")
        negative_count = sum(1 for d, _ in events if d == "negative")
        items.append(
            FactorSignal(
                code=code,
                name=info["name"],
                category=info["category"],
                factor_type=info["factor_type"],
                direction=direction,
                signal_score=score,
                confidence=confidence,
                event_count=len(events),
                positive_count=positive_count,
                negative_count=negative_count,
                hit_rate=info["hit_rate"],
                majority_base=info["majority_base"],
                sample_size=info["sample_size"],
                holding_days=holding_days,
                latest_event_time=max(pub for _, pub in events),
            )
        )
    return items


def _rank_and_trim(items: list[FactorSignal], panel_size: int) -> list[FactorSignal]:
    """按 |信号强度| × 命中率 排序取前 N，命中率缺失时退化为只看信号强度。"""
    def sort_key(item: FactorSignal) -> tuple[float, int]:
        strength = abs(item.signal_score) * (item.hit_rate or 0.5)
        return (strength, item.sample_size)

    return sorted(items, key=sort_key, reverse=True)[:panel_size]


def format_signal_panel(panel: dict[str, Any]) -> str:
    """把面板渲染成提示词里的固定表格，供 DreamStrategy 用户消息使用。

    输出为纯文本表格，控制在约 8 行数据量（受 4000 汉字预算约束）。
    """
    items = panel.get("items") or []
    if not items:
        return "【因子信号面板】当前窗口内无通过历史检验的因子信号，本轮不做情绪门控。"

    header = (
        f"【因子信号面板】窗口 {panel.get('window_days')} 天；"
        f"抽取模型 {panel.get('model_name')}；方向为债市口径（多=收益率下行）。"
        "命中率为全模型混合口径，仅供参考。"
    )
    lines = [
        header,
        "因子(代码) | 方向 | 信号分 | 命中率(基准) | 样本量 | 近窗口事件 | 最近触发",
    ]
    for item in items:
        hit = item.get("hit_rate")
        base = item.get("majority_base")
        hit_text = (
            f"{hit:.2f}({base:.2f})" if hit is not None and base is not None else "—"
        )
        lines.append(
            f"{item['name']}({item['code']}) | {item['direction_label']} | "
            f"{item['signal_score']:+.2f} | {hit_text} | {item['sample_size']} | "
            f"{item['event_count']}条 | {(item.get('latest_event_time') or '')[:10]}"
        )
    lines.append(
        "使用方式：仅在因子方向与技术信号同向时允许开仓；"
        "多空因子数量相当或方向冲突时不新增仓位。因子不单独触发交易。"
    )
    return "\n".join(lines)