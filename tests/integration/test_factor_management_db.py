"""集成测试：factor_management 对真实测试库的因子新增/查询/分页/提示词。"""

import pytest

from backend.factor.factor_management import (
    add_new_factor,
    get_factor_prompt_text,
    get_factors_from_db,
    get_factors_paged,
)


@pytest.fixture(autouse=True)
def _clean(clean_tables):
    clean_tables("news_factor", "news", "factor")


class TestFactorManagementDb:
    def test_add_and_list(self):
        assert add_new_factor("MACRO", "RATE", "利率", "quantitative") is True
        factors = get_factors_from_db()
        assert any(f["code"] == "RATE" for f in factors)
        assert any(f["name"] == "利率" for f in factors)

    def test_duplicate_code_rejected(self):
        assert add_new_factor("MACRO", "DUPE", "甲", "quantitative") is True
        assert add_new_factor("MACRO", "DUPE", "甲", "quantitative") is False

    def test_paged_returns_rows_and_total(self):
        add_new_factor("MACRO", "A", "甲", "quantitative")
        add_new_factor("LIQUIDITY", "B", "乙", "conceptual")
        page = get_factors_paged(page=1, page_size=10)
        assert page["total"] == 2
        codes = {f["code"] for f in page["factors"]}
        assert codes == {"A", "B"}
        assert page["page"] == 1

    def test_prompt_text_mentions_factor(self):
        add_new_factor("MACRO", "RATE", "利率", "quantitative")
        text = get_factor_prompt_text()
        assert "RATE" in text
pytestmark = pytest.mark.integration
