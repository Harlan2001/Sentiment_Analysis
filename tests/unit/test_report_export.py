"""report/export_service 单测：纯函数 + DOCX zip 冒烟；不依赖 playwright、不连库。"""

from datetime import date
from io import BytesIO
from zipfile import ZipFile

import pytest

from backend.common.pdf_export import PlaywrightUnavailableError, render_html_to_pdf
from backend.report.export_service import (
    _format_source_line,
    _markdown_blocks,
    _safe_filename,
    _strip_markdown,
    export_filename,
    generate_docx,
)

# ---- _safe_filename / export_filename ----


def test_safe_filename_replaces_illegal_chars():
    assert _safe_filename("a/b\\c") == "a-b-c"


def test_safe_filename_truncates_to_80():
    payload = "x" * 100
    assert _safe_filename(payload) == "x" * 80


def test_safe_filename_empty_falls_back():
    assert _safe_filename("   ") == "research-report"
    assert _safe_filename("...") == "research-report"


def test_export_filename_joins_extension():
    assert export_filename("研报标题", "docx") == "研报标题.docx"


# ---- _markdown_blocks / _strip_markdown ----


def test_markdown_blocks_classifies_lines():
    text = "# 一级标题\n## 二级标题\n### 三级标题\n- 要点一\n+ 要点二\n普通段落\n\n* 要点三"
    assert _markdown_blocks(text) == [
        ("h1", "一级标题"),
        ("h2", "二级标题"),
        ("h3", "三级标题"),
        ("bullet", "要点一"),
        ("bullet", "要点二"),
        ("p", "普通段落"),
        ("bullet", "要点三"),
    ]


def test_markdown_blocks_skips_blank_lines():
    assert _markdown_blocks("   \n# 标题\n\t\n") == [("h1", "标题")]


def test_strip_markdown_removes_bold_code_links():
    assert _strip_markdown("**bold** and `code` and [link]") == "bold and code and link"


# ---- _format_source_line ----


def test_format_source_line_uses_defaults():
    assert _format_source_line({}) == "未命名研报 · 未知机构 · 日期未知"


def test_format_source_line_values_and_separator():
    source = {"title": "T", "institution": "I", "publish_date": date(2026, 1, 1)}
    assert _format_source_line(source) == "T · I · 2026-01-01"
    assert _format_source_line(source, separator=" | ") == "T | I | 2026-01-01"


# ---- generate_docx 冒烟：合法 zip 且含 word/document.xml ----


def test_generate_docx_returns_valid_zip_with_document_xml():
    content = generate_docx(
        "测试标题",
        "# 引言\n\n正文内容\n- 要点一",
        [{"title": "来源A", "institution": "机构B", "publish_date": "2026-01-01"}],
    )
    with ZipFile(BytesIO(content)) as archive:
        names = archive.namelist()
        assert "word/document.xml" in names
        assert "[Content_Types].xml" in names
        document = archive.read("word/document.xml").decode("utf-8")
        assert "测试标题" in document
        assert "来源研报" in document
        assert "1. 来源A | 机构B | 2026-01-01" in document


def test_generate_docx_sources_missing_fields_use_defaults():
    content = generate_docx("t", "# 标题", [{}])
    document = ZipFile(BytesIO(content)).read("word/document.xml").decode("utf-8")
    assert "1. 未命名研报 | 未知机构 | 日期未知" in document


# ---- 共享 PDF 助手：playwright 缺失时的降级异常（不真正渲染） ----


def test_render_html_to_pdf_raises_when_playwright_missing(monkeypatch):
    real_import = __import__

    def _block_playwright(name, *args, **kwargs):
        if name == "playwright" or name.startswith("playwright."):
            raise ImportError("playwright 缺失")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _block_playwright)
    with pytest.raises(PlaywrightUnavailableError):
        render_html_to_pdf("<html><body>x</body></html>")