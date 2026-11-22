"""研究组合的确定性 Decimal 指标与阈值风险规则。"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any, Iterable

ZERO = Decimal("0")
HUNDRED = Decimal("100")
CENT = Decimal("0.01")
CASH_WARNING_THRESHOLD = Decimal("3")
SINGLE_HOLDING_WARNING_THRESHOLD = Decimal("20")
DURATION_DEVIATION_THRESHOLD = Decimal("0.5")


def _decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    """配置金额仅为研究规模估算，统一按人民币分展示。"""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _display(value: Decimal) -> str:
    return format(value.normalize(), "f")


def calculate_portfolio_metrics(
    holdings: Iterable[dict[str, Any]],
    *,
    size_amount: Decimal | int | str = ZERO,
    target_duration: Decimal | int | str | None = None,
) -> dict[str, Any]:
    """计算组合指标；所有中间运算均使用 Decimal，缺失值不按零处理。

    加权久期/收益率只使用对应值非空的持仓，分母为那些持仓的有效权重。
    覆盖率也是百分数。空组合没有持仓集中度和加权指标，因此最大持仓权重为 0、
    最大持仓占已配置权重比例为 null，两个覆盖率均为 0。
    """
    rows = list(holdings)
    size = _decimal(size_amount)
    target = _decimal(target_duration) if target_duration is not None else None

    with localcontext() as context:
        context.prec = 40
        invested_weight = sum((_decimal(row["weight_pct"]) for row in rows), ZERO)
        cash_weight = HUNDRED - invested_weight

        duration_rows = [row for row in rows if row.get("duration_years") is not None]
        yield_rows = [row for row in rows if row.get("yield_pct") is not None]
        duration_weight = sum(
            (_decimal(row["weight_pct"]) for row in duration_rows), ZERO
        )
        yield_weight = sum((_decimal(row["weight_pct"]) for row in yield_rows), ZERO)

        weighted_duration = (
            sum(
                (
                    _decimal(row["weight_pct"]) * _decimal(row["duration_years"])
                    for row in duration_rows
                ),
                ZERO,
            )
            / duration_weight
            if duration_weight > ZERO
            else None
        )
        weighted_yield = (
            sum(
                (
                    _decimal(row["weight_pct"]) * _decimal(row["yield_pct"])
                    for row in yield_rows
                ),
                ZERO,
            )
            / yield_weight
            if yield_weight > ZERO
            else None
        )
        duration_coverage = (
            duration_weight / invested_weight * HUNDRED if invested_weight > ZERO else ZERO
        )
        yield_coverage = (
            yield_weight / invested_weight * HUNDRED if invested_weight > ZERO else ZERO
        )

        allocation_weights: dict[str, Decimal] = {}
        for row in rows:
            category = str(row["asset_category"])
            allocation_weights[category] = allocation_weights.get(category, ZERO) + _decimal(
                row["weight_pct"]
            )
        asset_allocations = [
            {
                "category": category,
                "weight": weight,
                "estimated_amount": _money(size * weight / HUNDRED),
                "is_cash": False,
            }
            for category, weight in sorted(allocation_weights.items())
        ]
        asset_allocations.append(
            {
                "category": "现金",
                "weight": cash_weight,
                "estimated_amount": _money(size * cash_weight / HUNDRED),
                "is_cash": True,
            }
        )

        max_holding_weight = max(
            (_decimal(row["weight_pct"]) for row in rows), default=ZERO
        )
        max_holding_share = (
            max_holding_weight / invested_weight * HUNDRED
            if invested_weight > ZERO
            else None
        )

        risk_items: list[dict[str, str]] = []
        if (
            target is not None
            and weighted_duration is not None
            and abs(weighted_duration - target) > DURATION_DEVIATION_THRESHOLD
        ):
            risk_items.append(
                {
                    "code": "TARGET_DURATION_DEVIATION",
                    "level": "medium",
                    "title": "目标久期偏离",
                    "detail": (
                        f"加权久期与目标久期的偏离超过 {_display(DURATION_DEVIATION_THRESHOLD)} 年："
                        f"当前 {_display(weighted_duration)} 年，目标 {_display(target)} 年"
                    ),
                }
            )
        for row in rows:
            weight = _decimal(row["weight_pct"])
            if weight > SINGLE_HOLDING_WARNING_THRESHOLD:
                risk_items.append(
                    {
                        "code": "SINGLE_HOLDING_OVER_20",
                        "level": "high",
                        "title": "单券权重超过 20%",
                        "detail": (
                            f"单券 {row['bond_code']}（{row['bond_name']}）权重 "
                            f"{_display(weight)}%，超过 20% 阈值"
                        ),
                    }
                )
        if cash_weight < CASH_WARNING_THRESHOLD:
            risk_items.append(
                {
                    "code": "CASH_BELOW_3",
                    "level": "medium",
                    "title": "现金权重低于 3%",
                    "detail": f"现金权重 {_display(cash_weight)}%，低于 3% 阈值",
                }
            )

        missing_duration = [str(row["bond_code"]) for row in rows if row.get("duration_years") is None]
        missing_yield = [str(row["bond_code"]) for row in rows if row.get("yield_pct") is None]
        if missing_duration:
            risk_items.append(
                {
                    "code": "MISSING_DURATION",
                    "level": "info",
                    "title": "部分持仓缺少久期",
                    "detail": "以下持仓缺少久期，未纳入加权久期：" + "、".join(missing_duration),
                }
            )
        if missing_yield:
            risk_items.append(
                {
                    "code": "MISSING_YIELD",
                    "level": "info",
                    "title": "部分持仓缺少收益率",
                    "detail": "以下持仓缺少收益率，未纳入加权收益率：" + "、".join(missing_yield),
                }
            )

        return {
            "invested_weight": invested_weight,
            "cash_weight": cash_weight,
            "weighted_duration": weighted_duration,
            "weighted_yield": weighted_yield,
            "duration_coverage": duration_coverage,
            "yield_coverage": yield_coverage,
            "max_holding_weight": max_holding_weight,
            "max_holding_share_of_invested": max_holding_share,
            "estimated_invested_amount": _money(size * invested_weight / HUNDRED),
            "estimated_cash_amount": _money(size * cash_weight / HUNDRED),
            "amount_basis": "研究规模估算（人民币元，非市值）",
            "asset_allocations": asset_allocations,
            "risk_items": risk_items,
        }
