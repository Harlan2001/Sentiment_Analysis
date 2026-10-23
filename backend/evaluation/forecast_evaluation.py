"""预测诊断：把历史预测与事后实际收益率对账，量化预测的准确性。

**本模块不新增任何表、不修改预测生成逻辑**，全部为只读查询 + 计算。

## 为什么需要它

预测报告生成完即归档，"上涨概率 0.55"是不可证伪的判断。本模块让
"预测准不准"第一次可被核查，并量化模型的系统性偏置。

## 两条必须遵守的口径

1. **对照基准是「多数类基准」，不是 50%**。方向预测的正确对照线是
   "无脑总是猜多数方向"的命中率（样本内事后可得）。只报命中率会让
   读者误读为"接近随机"，而真实问题往往是系统性偏置 —— 两者性质不同。

2. **按交易日对齐**。yield_data 的日期集合即中债估值发布日历（含调休
   补班日），T+N 按该序列的**序号**推进，不按自然日（否则跨周末的
   "T+1" 实际是 3 天后，结果系统性失真）。
"""

from __future__ import annotations

import bisect
import math
from datetime import date
from typing import Any

from backend.repositories.forecast_evaluation_repository import (
    EVALUATION_PERIOD,
    ForecastEvaluationRepository,
)

# 周期 → 交易日持有期（T+N）。与报告中的「日/周/月」预测节点对应。
HORIZONS: dict[str, int] = {"日": 1, "周": 5, "月": 20}

# 置信度分档下界（含）。分档样本不足时标记 sufficient=False，由前端决定隐藏。
CONFIDENCE_BUCKETS: list[tuple[str, float, float]] = [
    ("≥0.65", 0.65, float("inf")),
    ("0.50-0.65", 0.50, 0.65),
    ("<0.50", 0.0, 0.50),
]
# 分档展示所需的最小样本数
MIN_BUCKET_SAMPLES = 20


def _ratio(numerator: int, denominator: int) -> float | None:
    """安全比例；分母为 0 时返回 None（由调用方决定如何呈现）。"""
    return round(numerator / denominator, 4) if denominator else None


def _wilson_interval(hits: int, total: int, z: float = 1.96) -> list[float] | None:
    """命中率的 Wilson 置信区间（比正态近似更适合小样本与极端比例）。"""
    if total == 0:
        return None
    phat = hits / total
    denominator = 1 + z**2 / total
    center = (phat + z**2 / (2 * total)) / denominator
    margin = (
        z * math.sqrt(phat * (1 - phat) / total + z**2 / (4 * total**2)) / denominator
    )
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def _quality_label(
    hit_rate: float | None, majority_base: float | None, interval: list[float] | None
) -> str:
    """三档结论标签：直接回答"这个预测能不能用"。

    - ``effective`` 有效：置信区间整体高于基准
    - ``risk`` 风险：置信区间整体低于基准
    - ``noise`` 噪音：与基准无显著差异（或样本不足无法判断）
    """
    if hit_rate is None or majority_base is None or interval is None:
        return "noise"
    if interval[0] > majority_base:
        return "effective"
    if interval[1] < majority_base:
        return "risk"
    return "noise"


def _extract_node(prediction: dict[str, Any], horizon_key: str) -> dict[str, Any] | None:
    """从 prediction 中取某周期的预测节点；缺失/非 dict 返回 None。"""
    result = prediction.get("预测结果")
    if not isinstance(result, dict):
        return None
    node = result.get(horizon_key)
    return node if isinstance(node, dict) else None


def _as_float(value: Any) -> float | None:
    """转 float；None / 非数值 / NaN 返回 None。"""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if not math.isnan(number) else None


class _TradingCalendar:
    """交易日历：基于 yield_data 的日期序列，按序号推进 T+N。

    不引入节假日依赖 —— yield_data 的日期集合本身就是权威的中债估值
    发布日历（实测其中 50 个"周末日期"恰好是中国的调休补班日）。
    """

    def __init__(self, series: list[tuple[date, float]]):
        self._dates = [item[0] for item in series]
        self._values = [item[1] for item in series]

    def index_of(self, target: date) -> int | None:
        """该日期在序列中的序号；非交易日返回 None。"""
        position = bisect.bisect_left(self._dates, target)
        if position < len(self._dates) and self._dates[position] == target:
            return position
        return None

    def value_at_offset(self, index: int, offset: int) -> float | None:
        """从 index 起向后 offset 个交易日的收益率；越界返回 None。"""
        target = index + offset
        if target < 0 or target >= len(self._values):
            return None
        return self._values[target]


def _evaluate_reports(
    reports: list[dict[str, Any]], calendar: _TradingCalendar
) -> dict[str, list[dict[str, Any]]]:
    """对每份报告、每个周期做一次对账，返回 {周期: [逐条记录]}。

    逐条记录含实际基点、预测方向是否命中、预测基点、绝对误差、置信度。
    """
    per_horizon: dict[str, list[dict[str, Any]]] = {key: [] for key in HORIZONS}

    for report in reports:
        trade_date = report["trade_date"]
        index = calendar.index_of(trade_date)
        if index is None:
            # 报告日期无行情（异常数据），跳过而不猜测
            continue
        base_value = calendar.value_at_offset(index, 0)
        if base_value is None:
            continue

        for horizon_key, offset in HORIZONS.items():
            node = _extract_node(report["prediction"], horizon_key)
            if node is None:
                continue
            future_value = calendar.value_at_offset(index, offset)
            if future_value is None:
                # 尚未到期（如最新报告），无法评估
                continue

            up_probability = _as_float(node.get("上涨概率"))
            down_probability = _as_float(node.get("下跌概率"))
            if up_probability is None and down_probability is None:
                continue

            predicted_up = (up_probability or 0.0) >= (down_probability or 0.0)
            predicted_bp = _as_float(
                node.get("上涨基点") if predicted_up else node.get("下跌基点")
            )
            actual_bp = round((future_value - base_value) * 100, 4)
            actual_up = actual_bp > 0

            per_horizon[horizon_key].append(
                {
                    "trade_date": trade_date.isoformat()
                    if isinstance(trade_date, date)
                    else str(trade_date),
                    "prompt_version": report["prompt_version"],
                    "model_name": report["model_name"],
                    "predicted_up": predicted_up,
                    "predicted_bp": predicted_bp,
                    "actual_bp": actual_bp,
                    "hit": predicted_up == actual_up,
                    "abs_error_bp": (
                        round(abs(actual_bp - predicted_bp), 4)
                        if predicted_bp is not None
                        else None
                    ),
                    "confidence": _as_float(node.get("置信度")),
                }
            )

    return per_horizon


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总单个周期的诊断指标。"""
    total = len(records)
    if total == 0:
        return {
            "sample_size": 0,
            "hit_count": 0,
            "hit_rate": None,
            "majority_base": None,
            "delta": None,
            "avg_abs_error_bp": None,
            "predicted_up_share": None,
            "actual_up_share": None,
            "confidence_interval": None,
            "quality": "noise",
        }

    hit_count = sum(1 for item in records if item["hit"])
    up_count = sum(1 for item in records if item["actual_bp"] > 0)
    predicted_up_count = sum(1 for item in records if item["predicted_up"])
    errors = [item["abs_error_bp"] for item in records if item["abs_error_bp"] is not None]

    hit_rate = _ratio(hit_count, total)
    # 多数类基准：事后"总是猜样本内多数方向"的命中率。这是方向预测的正确对照线。
    majority_base = _ratio(max(up_count, total - up_count), total)
    interval = _wilson_interval(hit_count, total)

    return {
        "sample_size": total,
        "hit_count": hit_count,
        "hit_rate": hit_rate,
        "majority_base": majority_base,
        "delta": (
            round(hit_rate - majority_base, 4)
            if hit_rate is not None and majority_base is not None
            else None
        ),
        "avg_abs_error_bp": (
            round(sum(errors) / len(errors), 2) if errors else None
        ),
        "predicted_up_share": _ratio(predicted_up_count, total),
        "actual_up_share": _ratio(up_count, total),
        "confidence_interval": interval,
        "quality": _quality_label(hit_rate, majority_base, interval),
    }


def _confidence_buckets(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按置信度分档统计实际表现：验证"模型说有把握时是否真的更准"。"""
    buckets: list[dict[str, Any]] = []
    for label, lower, upper in CONFIDENCE_BUCKETS:
        subset = [
            item
            for item in records
            if item["confidence"] is not None and lower <= item["confidence"] < upper
        ]
        summary = _summarize(subset) if subset else None
        buckets.append(
            {
                "label": label,
                "sample_size": len(subset),
                # 样本不足的分档不展示统计量，避免小样本误导
                "sufficient": len(subset) >= MIN_BUCKET_SAMPLES,
                "hit_rate": summary["hit_rate"] if summary else None,
                "majority_base": summary["majority_base"] if summary else None,
                "avg_abs_error_bp": summary["avg_abs_error_bp"] if summary else None,
            }
        )
    return buckets


def _calibration_series(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按月汇总"预测看涨占比 vs 实际上涨占比"，供校准度双折线图。

    两条线长期背离即说明模型存在系统性方向偏置。
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        month = item["trade_date"][:7]
        grouped.setdefault(month, []).append(item)

    series: list[dict[str, Any]] = []
    for month in sorted(grouped):
        subset = grouped[month]
        predicted_up = sum(1 for item in subset if item["predicted_up"])
        actual_up = sum(1 for item in subset if item["actual_bp"] > 0)
        series.append(
            {
                "month": month,
                "sample_size": len(subset),
                "predicted_up_share": _ratio(predicted_up, len(subset)),
                "actual_up_share": _ratio(actual_up, len(subset)),
            }
        )
    return series


def build_forecast_diagnosis() -> dict[str, Any]:
    """构建完整预测诊断结果（三周期指标 + 校准度序列 + 置信度分档）。"""
    repository = ForecastEvaluationRepository.from_environment()
    calendar = _TradingCalendar(repository.list_yield_series())
    reports = repository.list_full_reports()
    per_horizon = _evaluate_reports(reports, calendar)

    horizons = []
    for horizon_key, offset in HORIZONS.items():
        records = per_horizon[horizon_key]
        horizons.append(
            {
                "horizon": horizon_key,
                "holding_days": offset,
                **(_summarize(records)),
                "confidence_buckets": _confidence_buckets(records),
                "calibration": _calibration_series(records),
            }
        )

    return {
        "period": EVALUATION_PERIOD,
        "report_count": len(reports),
        "horizons": horizons,
        "generated_at": date.today().isoformat(),
    }