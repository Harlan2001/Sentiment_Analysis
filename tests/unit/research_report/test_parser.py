"""research_report/parser：研报解析纯函数单测（不触 PDF/文件 IO）。

覆盖: 文本规整/表格行判定/中文计数/展示文本清洗/标题提取与元数据解析/
行业提取/标代码提取/图表类型推导。
"""

from datetime import date

from backend.research_report.parser import (
    _cjk_count,
    _extract_industries,
    _extract_meta_from_text,
    _extract_symbols,
    _extract_title,
    _extract_title_from_text,
    _infer_figure_type,
    _is_table_row,
    _parse_metadata_from_title,
    clean_display_text,
    normalize_text,
)


class TestNormalizeText:
    def test_unifies_newlines(self):
        assert normalize_text("a\r\nb\rc") == "a\nb\nc"

    def test_collapses_excess_blank_lines(self):
        assert normalize_text("a\n\n\n\n\nb") == "a\n\nb"

    def test_collapses_spaces(self):
        assert normalize_text("a  b\t\tc") == "a b c"

    def test_strips_edges(self):
        assert normalize_text("  x  ") == "x"


class TestIsTableRow:
    def test_empty_line_is_table_row(self):
        assert _is_table_row("") is True

    def test_numeric_dense_line(self):
        assert _is_table_row("1.50 2.30 2.10") is True

    def test_chinese_text_false(self):
        assert _is_table_row("央行全面降准释放长期资金") is False


class TestCjkCount:
    def test_counts_chinese_only(self):
        assert _cjk_count("中文abc") == 2

    def test_empty(self):
        assert _cjk_count("") == 0


class TestExtractTitle:
    def test_strips_pdf_extension(self):
        assert _extract_title("某某公司深度报告.pdf", "f.pdf") == "某某公司深度报告"

    def test_hash_placeholder_uses_filename(self):
        # hash 占位 → 改用文件名, 但仍然去除 .pdf 扩展名
        assert _extract_title("a1b2c3d4e5f6", "real_report.pdf") == "real_report"

    def test_strips_index_prefix(self):
        assert _extract_title("1-深度报告", "x.pdf") == "深度报告"


class TestExtractTitleFromText:
    def test_returns_first_chinese_candidate(self):
        text = "\n".join(["证券研究报告", "央行降准深度研究：流动性宽松周期开启", "分析师：张三"])
        out = _extract_title_from_text(text)
        assert out is not None
        assert "央行降准深度研究" in out

    def test_no_candidate_returns_none(self):
        assert _extract_title_from_text("\n".join(["证券分析师：张三", "执业证书编号", ""])) is None


class TestCleanDisplayText:
    def test_skips_footer_and_table_rows(self):
        text = "\n".join(
            [
                "本报告不构成投资建议",
                "引言部分",
                "1.50 2.30",
                "总之供给与需求保持均衡",
            ]
        )
        out = clean_display_text(text)
        assert "引言部分" in out
        assert "1.50 2.30" not in out

    def test_truncates_over_max(self):
        text = "好段\n\n" + "字" * 5000
        out = clean_display_text(text, max_chars=100)
        assert len(out) < 150


class TestExtractIndustries:
    def test_deduped_preserving_order(self):
        text = "银行业绩回暖 银行与券商板块表现突出 医药领涨"
        out = _extract_industries(text, 1000)
        assert out == list(dict.fromkeys(out))  # 保序去重
        assert "银行" in out

    def test_respects_max_chars(self):
        out = _extract_industries("银行", 1)  # 只给 1 字符, 关键词不命中
        assert "银行" not in out


class TestExtractSymbols:
    def test_dot_format(self):
        assert _extract_symbols("推荐601318.SH") == ["601318.SH"]

    def test_sh_prefix_format(self):
        assert _extract_symbols("关注sh600000") == ["SH600000"]

    def test_bracket_format(self):
        assert _extract_symbols("（601318）") == ["601318"]

    def test_dedup_and_limit(self):
        text = "601318.SH 601318.SH 000001.SZ"
        assert _extract_symbols(text) == ["601318.SH", "000001.SZ"]
        many = " ".join(f"{600000 + i}.SH" for i in range(40))
        assert len(_extract_symbols(many)) == 30


class TestParseMetadataFromTitle:
    def test_parses_date_ymd(self):
        meta = _parse_metadata_from_title("债市周报-240901")
        assert meta["publish_date"] == date(2024, 9, 1)

    def test_parses_date_full(self):
        meta = _parse_metadata_from_title("债市周报-20260901")
        assert meta["publish_date"] == date(2026, 9, 1)

    def test_parses_date_cn(self):
        meta = _parse_metadata_from_title("债市周报2026年9月1日发布")
        assert meta["publish_date"] == date(2026, 9, 1)

    def test_institution_and_industry(self):
        meta = _parse_metadata_from_title("中信证券-银行行业周报20260901")
        assert meta["institution"] is not None
        assert "银行" in meta["industry"]


class TestExtractMetaFromText:
    def test_extracts_institution_analyst_date(self):
        text = (
            "华泰证券研究所\n"
            "证券分析师：张三 证券投资咨询执业资格证书\n"
            "2026年9月1日\n"
        )
        meta = _extract_meta_from_text(text)
        assert meta["institution"] is not None
        assert "张三" in meta["analyst"]
        assert meta["publish_date"] == date(2026, 9, 1)


class TestInferFigureType:
    def test_too_small_decorative(self):
        assert _infer_figure_type(w=80, h=80, size_kb=10) == "decorative"

    def test_extreme_ratio_decorative(self):
        assert _infer_figure_type(w=1000, h=100, size_kb=20) == "decorative"

    def test_chart_when_wide(self):
        assert _infer_figure_type(w=400, h=200, size_kb=15) == "chart"

    def test_chart_when_heavy(self):
        assert _infer_figure_type(w=200, h=200, size_kb=50) == "chart"

    def test_small_square_decorative(self):
        assert _infer_figure_type(w=200, h=200, size_kb=10) == "decorative"

    def test_plain_image(self):
        assert _infer_figure_type(w=300, h=300, size_kb=25) == "image"