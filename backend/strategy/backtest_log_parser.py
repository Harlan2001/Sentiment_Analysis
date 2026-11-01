"""回测日志 STATISTICS 结构化（B2 / S2-4）。

ksquant-piloppolicy 的回测日志里只有 ``STATISTICS:: <Label> <Value>`` 这一段
是可机读的结构化结果（S0 已确认逐笔成交不回传，曲线/成交只能走 160055）。
本模块负责：

1. 把 STATISTICS 行解析成 ``{key,label,value,tier}`` 指标列表，未知指标保留；
2. 按结果页口径分四层：核心 / 收益质量 / 风险 / 其他；
3. 识别"除式爆炸"类计算异常（S0 真实样本：Sharpe -42182、波动率 0），
   异常只标注、不洗绿，绝不伪造或修改数值。
"""

from __future__ import annotations

import re
from typing import Any

# 核心（英雄区大字）：回答"有没有成交、赚不赚钱、回撤多大"。
TIER_CORE = "core"
# 收益质量：盈亏的结构，而不只是最终收益。
TIER_QUALITY = "quality"
# 风险：风险调整指标与波动；这一层最容易除式爆炸。
TIER_RISK = "risk"
# 其他：工程/容量/哈希等，结果页默认折叠。
TIER_OTHER = "other"

_TIER_BY_LABEL: dict[str, str] = {
    "Total Orders": TIER_CORE,
    "Compounding Annual Return": TIER_CORE,
    "Drawdown": TIER_CORE,
    "Win Rate": TIER_CORE,
    "Net Profit": TIER_CORE,
    "Profit-Loss Ratio": TIER_QUALITY,
    "Expectancy": TIER_QUALITY,
    "Average Win": TIER_QUALITY,
    "Average Loss": TIER_QUALITY,
    "Total Fees": TIER_QUALITY,
    "Loss Rate": TIER_QUALITY,
    "Sharpe Ratio": TIER_RISK,
    "Sortino Ratio": TIER_RISK,
    "Probabilistic Sharpe Ratio": TIER_RISK,
    "Annual Standard Deviation": TIER_RISK,
    "Annual Variance": TIER_RISK,
    "Tracking Error": TIER_RISK,
}

# 多词指标必须按整名前缀匹配，否则 "Total Fees" 会被 "Total" 之类截断。
_KNOWN_STATISTIC_NAMES = (
    "Total Orders",
    "Average Win",
    "Average Loss",
    "Compounding Annual Return",
    "Drawdown",
    "Expectancy",
    "Start Equity",
    "End Equity",
    "Net Profit",
    "Sharpe Ratio",
    "Sortino Ratio",
    "Probabilistic Sharpe Ratio",
    "Loss Rate",
    "Win Rate",
    "Profit-Loss Ratio",
    "Alpha",
    "Beta",
    "Annual Standard Deviation",
    "Annual Variance",
    "Information Ratio",
    "Tracking Error",
    "Treynor Ratio",
    "Total Fees",
    "Estimated Strategy Capacity",
    "Lowest Capacity Asset",
    "Portfolio Turnover",
    "Drawdown Recovery",
    "OrderListHash",
)

_RATIO_EXPLOSION_THRESHOLD = 10.0
_RISK_RATIO_KEYS = ("sharpe_ratio", "sortino_ratio")


def parse_metric_number(value: str) -> float | None:
    """把 ``"2.1%"``、``"$1,000.24"``、``"-42182.563"`` 解析成 float。

    非数值（容量标的、哈希）返回 None；解析不出不造数。
    """
    text = str(value or "").strip().replace(",", "").replace("$", "")
    if not text:
        return None
    try:
        return float(text.rstrip("%"))
    except ValueError:
        return None


def _metric_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def parse_statistics(backtest_log: str) -> list[dict[str, Any]]:
    """提取所有 STATISTICS 行，保留对端原值并附 tier/numeric。

    已知指标按完整多词名匹配；对端新版本多出的指标走宽松解析，
    无法切分标签和值时整条以原值保留，不静默丢弃。
    """
    metrics: list[dict[str, Any]] = []
    for line in str(backtest_log or "").splitlines():
        if "STATISTICS::" not in line:
            continue
        statistic = line.split("STATISTICS::", 1)[1].strip()
        label = value = ""
        for known in _KNOWN_STATISTIC_NAMES:
            if statistic == known or statistic.startswith(f"{known} "):
                label = known
                value = statistic[len(known):].strip()
                break
        if not label:
            matched = re.match(r"^(.*?)(?:\s*[:=]\s*|\s{2,})(.+)$", statistic)
            if matched:
                label, value = (part.strip() for part in matched.groups())
            else:
                label, value = statistic, ""
        if not label:
            continue
        metrics.append(
            {
                "key": _metric_key(label),
                "label": label,
                "value": value,
                "tier": _TIER_BY_LABEL.get(label, TIER_OTHER),
                "numeric": parse_metric_number(value),
            }
        )
    return metrics


def detect_metric_anomalies(
    metrics: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """标注风险调整指标的计算异常（S0 实证：波动率趋零导致的除式爆炸）。

    - |Sharpe|/|Sortino| > 10：超出任何可信区间，通常是样本极少/趋零波动；
    - 有订单但年化波动率为 0：比率分母为 0，Sharpe/Sortino 无意义。
    只标注，不改变验收结论（废单判定在 backtest_validation）。
    """
    by_key = {item.get("key"): item for item in metrics}

    def _num(key: str) -> float | None:
        item = by_key.get(key)
        return item.get("numeric") if item else None

    orders = _num("total_orders")
    volatility = _num("annual_standard_deviation")
    zero_volatility_with_orders = bool(
        orders and orders > 0 and volatility is not None and volatility == 0
    )

    anomalies: list[dict[str, str]] = []
    for key in _RISK_RATIO_KEYS:
        item = by_key.get(key)
        if not item:
            continue
        number = item.get("numeric")
        reason = ""
        if number is not None and abs(number) > _RATIO_EXPLOSION_THRESHOLD:
            reason = (
                f"数值 {item.get('value')} 绝对值超过 10，"
                "疑似样本过少/趋零波动导致的除式爆炸，不能据此评价风险收益"
            )
        elif zero_volatility_with_orders:
            reason = (
                "有订单但年化波动率为 0，风险调整比率的分母趋零，"
                "该指标无参考意义（请以成交与权益曲线为准）"
            )
        if reason:
            item["anomaly"] = reason
            anomalies.append(
                {"key": key, "label": str(item.get("label") or key), "reason": reason}
            )
    return anomalies


def parse_backtest_metrics(backtest_log: str) -> dict[str, Any]:
    """一次解析出指标（含 tier/anomaly 标注）与异常清单。"""
    metrics = parse_statistics(backtest_log)
    anomalies = detect_metric_anomalies(metrics)
    return {"metrics": metrics, "anomalies": anomalies}
