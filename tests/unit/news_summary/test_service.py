"""news_summary/service：新闻行格式化的纯函数单测（不触 DB/LLM）。"""

from backend.news_summary.service import _news_line


class TestNewsLine:
    def _item(self, **overrides):
        item = {
            "id": 1,
            "publish_time": "2026-09-01",
            "source": "新华网",
            "direction": "positive",
            "horizon": "短期",
            "title": "央行降低存款准备金率",
            "reason": "释放流动性支持实体经济",
        }
        item.update(overrides)
        return item

    def test_full_line(self):
        out = _news_line(self._item())
        assert out == (
            "- [1] 2026-09-01 | 新华网 | positive/短期 | 央行降低存款准备金率 | 释放流动性支持实体经济"
        )

    def test_missing_reason_defaults_to_waiting(self):
        item = self._item()
        item.pop("reason", None)
        assert "待分析" in _news_line(item)

    def test_reason_truncated_and_collapsed(self):
        item = self._item(reason=" 长" + "字" * 500 + " 短")
        out = _news_line(item)
        reason_part = out.split(" | ")[-1]
        assert len(reason_part) <= 260

    def test_missing_title_ok(self):
        out = _news_line(self._item(title=""))
        assert out.startswith("- [1]")