"""change/change_service：快照对比/格式化的纯函数单测（不触 DB）。

覆盖: _fmt 格式化 / _row_to_dict 行转字典(含 JSON 字段解析) / _build_reason_text 摘要组装 /
_diff_items 通用增删改对比 / compute_diff 标的+策略快照 diff。
"""

from datetime import datetime

from backend.change.change_service import (
    _build_reason_text,
    _diff_items,
    _fmt,
    _row_to_dict,
    compute_diff,
)


class TestFmt:
    def test_none(self):
        assert _fmt(None) is None

    def test_datetime_formats(self):
        assert _fmt(datetime(2026, 9, 1, 8, 5, 0)) == "2026-09-01 08:05:00"

    def test_plain_passthrough(self):
        assert _fmt(42) == "42"


class TestRowToDict:
    def _row(self):
        return (
            1, datetime(2026, 9, 1), datetime(2026, 8, 31), datetime(2026, 9, 1),
            10, 3, 1, '{"a": 1}', "plain-string", None, 1, datetime(2026, 9, 1, 0, 0),
        )

    def test_maps_columns(self):
        d = _row_to_dict(self._row())
        assert d["id"] == 1
        assert d["news_total"] == 10
        assert d["news_added_count"] == 3
        assert d["version_time"] == "2026-09-01 00:00:00"

    def test_parses_json_fields(self):
        d = _row_to_dict(self._row())
        assert d["stock_recommend"] == {"a": 1}
        assert d["summary_stats"] is None

    def test_keeps_unparseable_json_as_is(self):
        row = self._row()
        row_ = row[:8] + ("{broken",) + row[9:]
        d = _row_to_dict(row_)
        assert d["strategy_recommend"] == "{broken"


class TestBuildReasonText:
    def test_formats_lines(self):
        rows = [
            {
                "pub_time": datetime(2026, 9, 1, 9, 0),
                "direction": "positive",
                "title": "央行降准",
                "reason": "释放流动性",
            }
        ]
        out = _build_reason_text(rows)
        assert "1. 时间: 2026-09-01 09:00 | 方向: positive | 标题: 央行降准 | 摘要: 释放流动性" in out

    def test_unanalyzed_uses_content_preview(self):
        rows = [
            {
                "pub_time": "2026-09-01",
                "direction": "neutral",
                "title": "某新闻",
                "content": "长" * 300,
            }
        ]
        out = _build_reason_text(rows)
        assert "【未分析】" in out
        assert len(out.split("摘要: ")[1]) <= 200 + len("…【未分析】")

    def test_no_rows(self):
        assert _build_reason_text([]) == "当前窗口内暂无有效新闻。"


class TestDiffItems:
    def test_add_remove_modify(self):
        old = [
            {"code": "A", "name": "甲", "rating": "买入", "weight": 0.8},
            {"code": "B", "name": "乙", "rating": "增持", "weight": 0.5},
        ]
        new = [
            {"code": "A", "name": "甲", "rating": "持有", "weight": 0.6},
            {"code": "C", "name": "丙", "rating": "买入", "weight": 0.9},
        ]
        added, removed, modified = _diff_items(
            old, new,
            id_key="code", name_field="name", removed_field="rating",
            removed_default="",
            modified_fields={"rating": "", "weight": 0},
        )
        assert [i["code"] for i in added] == ["C"]
        assert removed == [{"code": "B", "name": "乙", "prev_rating": "增持"}]
        assert len(modified) == 1
        assert modified[0]["code"] == "A"
        assert modified[0]["old_rating"] == "买入"
        assert modified[0]["new_weight"] == 0.6

    def test_empty_inputs(self):
        added, removed, modified = _diff_items(
            [], [], id_key="code", name_field="name", removed_field="rating",
            removed_default="", modified_fields={"rating": ""},
        )
        assert (added, removed, modified) == ([], [], [])


class TestComputeDiff:
    def _snapshot(self, **overrides):
        base = {
            "version_time": datetime(2026, 9, 1),
            "window_start": datetime(2026, 8, 31),
            "window_end": datetime(2026, 9, 1),
            "news_added_count": 3,
            "news_removed_count": 1,
            "stock_recommend": [
                {"code": "A", "name": "甲", "rating": "买入", "weight": 0.8},
            ],
            "strategy_recommend": [
                {"id": 1, "name": "策略一", "priority": 2, "weight": 0.5, "trigger_logic": "x"},
            ],
        }
        base.update(overrides)
        return base

    def test_diff_summary_counts(self):
        old_s = self._snapshot()
        new_s = self._snapshot(
            stock_recommend=[
                {"code": "A", "name": "甲", "rating": "持有", "weight": 0.5},
                {"code": "D", "name": "丁", "rating": "增持", "weight": 0.3},
            ],
            strategy_recommend=[],
        )
        out = compute_diff(old_s, new_s)
        assert out["diff_summary"]["new_stocks"] == 1
        assert out["diff_summary"]["rating_changes"] == 1
        assert out["diff_summary"]["strategy_changes"] == 1  # 移除的策略

    def test_base_info_carried(self):
        out = compute_diff(self._snapshot(), self._snapshot())
        assert out["base_info"]["news_diff"] == {"added_count": 3, "removed_count": 1}

    def test_empty_snapshots(self):
        out = compute_diff({}, {})
        assert out["stock_changes"]["added"] == []
        assert out["strategy_changes"]["removed"] == []