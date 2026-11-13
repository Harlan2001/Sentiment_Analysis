from __future__ import annotations

from backend.business_mcp import service


def _calendar(diff_bp, news):
    return {
        "data": {
            "yields_by_date": {
                "2026-11-09": {
                    "10Y": {
                        "diff_bp": diff_bp,
                        "direction": "up" if diff_bp and diff_bp > 0 else "flat",
                    }
                }
            },
            "news_by_date": {"2026-11-09": news},
            "days": [{"date": "2026-11-09", "active_factors": []}],
        }
    }


def test_market_explanation_reuses_alignment_and_preserves_importance_order(monkeypatch):
    news = [
        {"id": 1, "title": "高分利空", "direction": "利空", "importance_score": 90},
        {"id": 2, "title": "高分利多", "direction": "利多", "importance_score": 85},
        {"id": 3, "title": "次分利空", "direction": "negative", "importance_score": 70},
        {"id": 4, "title": "中性", "direction": "中性", "importance_score": 60},
    ]
    monkeypatch.setattr(
        service,
        "returns_calendar",
        lambda **_kwargs: _calendar(2.0, news),
    )

    result = service.explain_bond_market_move("2026-11-09")

    assert [item["news_id"] for item in result["primary_drivers"]] == [1, 3]
    assert [item["news_id"] for item in result["contradicting_evidence"]] == [2]


def test_market_explanation_does_not_align_news_without_computable_change(monkeypatch):
    monkeypatch.setattr(
        service,
        "returns_calendar",
        lambda **_kwargs: _calendar(
            None,
            [{"id": 1, "title": "利多", "direction": "利多"}],
        ),
    )

    result = service.explain_bond_market_move("2026-11-09")

    assert result["primary_drivers"] == []
    assert result["contradicting_evidence"] == []
    assert result["unexplained"] is True
