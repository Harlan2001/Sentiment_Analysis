"""研究组合 Decimal 指标、空组合语义与固定风险阈值。"""

from decimal import Decimal, localcontext

from backend.portfolio.metrics import calculate_portfolio_metrics

D = Decimal


def holding(code, weight, *, duration=None, yield_pct=None, category="利率债"):
    return {
        "bond_code": code,
        "bond_name": f"债券{code}",
        "asset_category": category,
        "weight_pct": D(str(weight)),
        "duration_years": D(str(duration)) if duration is not None else None,
        "yield_pct": D(str(yield_pct)) if yield_pct is not None else None,
    }


def risk_codes(metrics):
    return [risk["code"] for risk in metrics["risk_items"]]


def test_empty_portfolio_is_all_cash_with_clear_null_and_zero_semantics():
    metrics = calculate_portfolio_metrics(
        [], size_amount=D("123456.78"), target_duration=D("3")
    )

    assert metrics["invested_weight"] == D("0")
    assert metrics["cash_weight"] == D("100")
    assert metrics["weighted_duration"] is None
    assert metrics["weighted_yield"] is None
    assert metrics["duration_coverage"] == D("0")
    assert metrics["yield_coverage"] == D("0")
    assert metrics["max_holding_weight"] == D("0")
    assert metrics["max_holding_share_of_invested"] is None
    assert metrics["estimated_invested_amount"] == D("0.00")
    assert metrics["estimated_cash_amount"] == D("123456.78")
    assert metrics["asset_allocations"] == [
        {
            "category": "现金",
            "weight": D("100"),
            "estimated_amount": D("123456.78"),
            "is_cash": True,
        }
    ]
    assert metrics["risk_items"] == []
    assert "非市值" in metrics["amount_basis"]


def test_weighted_metrics_ignore_missing_values_instead_of_treating_them_as_zero():
    metrics = calculate_portfolio_metrics(
        [
            holding("A", 25, duration=2, yield_pct=None),
            holding("B", 25, duration=None, yield_pct=4),
            holding("C", 50, duration=4, yield_pct=2),
        ]
    )

    with localcontext() as context:
        context.prec = 40
        assert metrics["weighted_duration"] == D(250) / D(75)
        assert metrics["weighted_yield"] == D(200) / D(75)
    assert metrics["duration_coverage"] == D(75)
    assert metrics["yield_coverage"] == D(75)
    assert metrics["max_holding_weight"] == D(50)
    assert metrics["max_holding_share_of_invested"] == D(50)
    assert risk_codes(metrics) == [
        "SINGLE_HOLDING_OVER_20",
        "SINGLE_HOLDING_OVER_20",
        "SINGLE_HOLDING_OVER_20",
        "CASH_BELOW_3",
        "MISSING_DURATION",
        "MISSING_YIELD",
    ]


def test_allocations_use_total_portfolio_weight_and_separate_cash_and_concentration():
    metrics = calculate_portfolio_metrics(
        [
            holding("A", 20, duration=2, yield_pct=3, category="利率债"),
            holding("B", 30, duration=4, yield_pct=None, category="信用债"),
        ],
        size_amount=D("1000.00"),
    )

    assert metrics["invested_weight"] == D(30 + 20)
    assert metrics["cash_weight"] == D(50)
    assert metrics["weighted_duration"] == D("3.2")
    assert metrics["weighted_yield"] == D(3)
    assert metrics["yield_coverage"] == D(40)
    assert metrics["max_holding_weight"] == D(30)
    assert metrics["max_holding_share_of_invested"] == D(60)
    allocations = {item["category"]: item for item in metrics["asset_allocations"]}
    assert allocations["利率债"]["weight"] == D(20)
    assert allocations["利率债"]["estimated_amount"] == D("200.00")
    assert allocations["信用债"]["weight"] == D(30)
    assert allocations["现金"]["weight"] == D(50)
    assert allocations["现金"]["estimated_amount"] == D("500.00")
    assert allocations["现金"]["is_cash"] is True
    assert metrics["estimated_invested_amount"] == D("500.00")


def test_zero_duration_and_yield_are_valid_data_with_full_coverage():
    metrics = calculate_portfolio_metrics(
        [holding("ZERO", 10, duration=0, yield_pct=0)]
    )

    assert metrics["weighted_duration"] == D(0)
    assert metrics["weighted_yield"] == D(0)
    assert metrics["duration_coverage"] == D(100)
    assert metrics["yield_coverage"] == D(100)
    assert "MISSING_DURATION" not in risk_codes(metrics)
    assert "MISSING_YIELD" not in risk_codes(metrics)


def test_decimal_precision_is_not_reduced_by_tiny_coverage_or_float_rounding():
    metrics = calculate_portfolio_metrics(
        [
            holding("A", "33.333333", duration=None, yield_pct="1.234567"),
            holding("B", "0.000001", duration="1.2345", yield_pct=None),
        ]
    )

    assert metrics["invested_weight"] == D("33.333334")
    assert metrics["cash_weight"] == D("66.666666")
    assert metrics["weighted_duration"] == D("1.2345")
    assert metrics["weighted_yield"] == D("1.234567")
    assert isinstance(metrics["duration_coverage"], Decimal)
    expected_coverage = D("0.000001") / D("33.333334") * D(100)
    assert abs(metrics["duration_coverage"] - expected_coverage) < D("1e-27")


def test_risk_thresholds_are_strict_and_deterministic():
    at_boundaries = calculate_portfolio_metrics(
        [holding("A", 20, duration=3, yield_pct=2)],
        target_duration=D("2.5"),
    )
    assert risk_codes(at_boundaries) == []

    cash_at_boundary = calculate_portfolio_metrics(
        [holding("A", 97, duration=3, yield_pct=2)],
        target_duration=D("2.5"),
    )
    assert "CASH_BELOW_3" not in risk_codes(cash_at_boundary)
    assert "TARGET_DURATION_DEVIATION" not in risk_codes(cash_at_boundary)

    over_boundaries = calculate_portfolio_metrics(
        [holding("A", "97.000001", duration="3.5001", yield_pct=None)],
        target_duration=D("3"),
    )
    codes = risk_codes(over_boundaries)
    assert "SINGLE_HOLDING_OVER_20" in codes
    assert "CASH_BELOW_3" in codes
    assert "TARGET_DURATION_DEVIATION" in codes
    assert "MISSING_YIELD" in codes
    assert all("AI" not in risk["detail"] for risk in over_boundaries["risk_items"])
    assert all("人工智能" not in risk["detail"] for risk in over_boundaries["risk_items"])
    assert all(
        set(risk) == {"code", "level", "title", "detail"}
        for risk in over_boundaries["risk_items"]
    )
    assert all(
        risk["level"] in {"high", "medium", "low", "info"}
        for risk in over_boundaries["risk_items"]
    )
