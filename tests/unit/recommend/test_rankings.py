"""排行榜编排单测（S3-3）：假 repository 注入，守塑形/脱敏/方向归一/空榜。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from backend.recommend.rankings import build_rankings


class FakeImportanceRepository:
    """按入参记录调用并返回预置行，行结构对齐 DictCursor。"""

    def __init__(self, *, top=None, positive=None, negative=None, factors=None, categories=None):
        self._top = top or []
        self._positive = positive or []
        self._negative = negative or []
        self._factors = factors or []
        self._categories = categories or []
        self.calls: list[tuple] = []

    def top_news(self, days, limit=10, direction=None):
        self.calls.append(("top_news", days, limit, direction))
        if direction == "positive":
            return self._positive
        if direction == "negative":
            return self._negative
        return self._top

    def hot_factors(self, days, limit=10):
        self.calls.append(("hot_factors", days, limit))
        return self._factors

    def category_distribution(self, days):
        self.calls.append(("category_distribution", days))
        return self._categories


def _news_row(**overrides):
    row = {
        "id": 1,
        "title": "央行降准释放长期流动性",
        "pub_time": datetime(2026, 11, 6, 9, 30, 0),
        "source": "wallstreetcn",
        "importance_score": Decimal("81.2500"),
        "final_score": Decimal("70.1234"),
        "best_direction": "利多",
        "top_category": "POLICY",
    }
    row.update(overrides)
    return row


class TestBuildRankings:
    def test_full_payload_shapes_and_masks_source(self):
        repo = FakeImportanceRepository(
            top=[_news_row()],
            positive=[_news_row(id=2, best_direction="bullish")],
            negative=[_news_row(id=3, source="yicai", best_direction="利空", final_score=Decimal("60.0000"))],
            factors=[{
                "id": 9, "name": "降准因子", "category": "POLICY",
                "news_count": 7, "hit_rate": Decimal("0.6200"),
            }],
            categories=[{"category": "POLICY", "news_count": 12, "share": 0.6}],
        )

        payload = build_rankings(7, repository=repo)

        assert payload["days"] == 7
        top = payload["top_news"][0]
        assert top["source_name"] == "数据源1"  # 脱敏，不得出现 wallstreetcn
        assert "wallstreetcn" not in str(top)
        assert top["direction"] == "positive"  # 中文方向词归一
        assert top["importance_score"] == 81.25
        assert top["final_score"] == 70.1234
        assert top["pub_time"] == "2026-11-06 09:30:00"
        assert top["top_category"] == "POLICY"

        assert payload["direction_board"]["positive"][0]["direction"] == "positive"
        neg = payload["direction_board"]["negative"][0]
        assert neg["direction"] == "negative"
        assert neg["source_name"] == "数据源2"

        factor = payload["hot_factors"][0]
        assert factor == {"id": 9, "name": "降准因子", "category": "POLICY",
                          "news_count": 7, "hit_rate": 0.62}
        assert payload["category_distribution"][0]["category"] == "POLICY"

    def test_direction_board_queries_each_side_with_limit_five(self):
        repo = FakeImportanceRepository()
        build_rankings(7, repository=repo)
        directional = [c for c in repo.calls if c[0] == "top_news" and c[3] is not None]
        assert ("top_news", 7, 5, "positive") in directional
        assert ("top_news", 7, 5, "negative") in directional

    def test_empty_boards_are_lists_not_errors(self):
        payload = build_rankings(7, repository=FakeImportanceRepository())
        assert payload == {
            "days": 7,
            "top_news": [],
            "hot_factors": [],
            "direction_board": {"positive": [], "negative": []},
            "category_distribution": [],
        }

    def test_unknown_direction_and_missing_hits_become_none(self):
        repo = FakeImportanceRepository(top=[
            _news_row(id=4, best_direction="看不懂", final_score=None),
        ], factors=[{
            "id": 10, "name": "无回测因子", "category": "SENTIMENT",
            "news_count": 1, "hit_rate": None,
        }])
        payload = build_rankings(30, repository=repo)
        assert payload["top_news"][0]["direction"] is None
        assert payload["top_news"][0]["final_score"] is None
        assert payload["hot_factors"][0]["hit_rate"] is None
