"""将已持久化的综合研报按需导出为 DOCX 或 PDF。"""

from __future__ import annotations

import html
import re
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape


def _safe_filename(title: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "-", title).strip(" .-")
    return value[:80] or "research-report"


def export_filename(title: str, extension: str) -> str:
    return f"{_safe_filename(title)}.{extension}"


def _markdown_blocks(markdown: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("### "):
            blocks.append(("h3", line[4:]))
        elif line.startswith("## "):
            blocks.append(("h2", line[3:]))
        elif line.startswith("# "):
            blocks.append(("h1", line[2:]))
        elif re.match(r"^[-*+]\s+", line):
            blocks.append(("bullet", re.sub(r"^[-*+]\s+", "", line)))
        else:
            blocks.append(("p", line))
    return blocks


def _strip_markdown(value: str) -> str:
    return re.sub(r"(\*\*|__|`|\[|\])", "", value)


def generate_docx(title: str, markdown: str, sources: list[dict]) -> bytes:
    """生成最小、兼容 Word 的 OOXML 文档，避免引入平行运行时依赖。"""
    paragraphs = [
        '<w:p><w:pPr><w:spacing w:after="160"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="36"/><w:szCs w:val="36"/><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Microsoft YaHei"/></w:rPr><w:t>{}</w:t></w:r></w:p>'.format(escape(title)),
    ]
    for kind, text in _markdown_blocks(markdown):
        value = escape(_strip_markdown(text))
        if kind == "h1":
            properties = '<w:p><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="30"/><w:szCs w:val="30"/>'
        elif kind == "h2":
            properties = '<w:p><w:pPr><w:spacing w:before="200" w:after="100"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="26"/><w:szCs w:val="26"/>'
        elif kind == "h3":
            properties = '<w:p><w:pPr><w:spacing w:before="160" w:after="80"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/>'
        elif kind == "bullet":
            properties = '<w:p><w:pPr><w:ind w:left="540" w:hanging="270"/><w:spacing w:after="80"/></w:pPr><w:r><w:rPr>'
            value = "• " + value
        else:
            properties = '<w:p><w:pPr><w:spacing w:after="120"/></w:pPr><w:r><w:rPr>'
        paragraphs.append(f'{properties}<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Microsoft YaHei"/></w:rPr><w:t xml:space="preserve">{value}</w:t></w:r></w:p>')

    paragraphs.append('<w:p><w:pPr><w:spacing w:before="240" w:after="100"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="26"/></w:rPr><w:t>来源研报</w:t></w:r></w:p>')
    for index, source in enumerate(sources, start=1):
        source_line = f"{index}. {source.get('title') or '未命名研报'} | {source.get('institution') or '未知机构'} | {source.get('publish_date') or '日期未知'}"
        paragraphs.append(f'<w:p><w:pPr><w:ind w:left="540" w:hanging="270"/><w:spacing w:after="80"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Microsoft YaHei"/></w:rPr><w:t xml:space="preserve">{escape(source_line)}</w:t></w:r></w:p>')

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{''.join(paragraphs)}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>'''
    core = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{escape(title)}</dc:title><dc:creator>Sentiment Analysis</dc:creator></cp:coreProperties>'''
    app = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Sentiment Analysis</Application></Properties>'''
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("docProps/core.xml", core)
        archive.writestr("docProps/app.xml", app)
    return stream.getvalue()


def generate_pdf(title: str, markdown: str, sources: list[dict]) -> bytes:
    """复用项目 Playwright 运行时，将结果渲染为 A4 PDF。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("PDF 导出不可用：playwright 未安装") from exc
    content = []
    for kind, text in _markdown_blocks(markdown):
        tag = {"h1": "h1", "h2": "h2", "h3": "h3", "p": "p", "bullet": "li"}[kind]
        content.append(f"<{tag}>{html.escape(_strip_markdown(text))}</{tag}>")
    source_html = "".join(f"<li>{html.escape(source.get('title') or '未命名研报')} · {html.escape(source.get('institution') or '未知机构')} · {html.escape(str(source.get('publish_date') or '日期未知'))}</li>" for source in sources)
    page_html = f'''<!doctype html><html><head><meta charset="utf-8"><style>@page{{size:A4;margin:20mm}}body{{font-family:"Microsoft YaHei",Arial,sans-serif;color:#202020;font-size:10.5pt;line-height:1.75}}h1{{font-size:18pt;margin:18pt 0 8pt}}h2{{font-size:14pt;margin:16pt 0 7pt;border-bottom:1px solid #ddd;padding-bottom:4pt}}h3{{font-size:12pt;margin:12pt 0 5pt}}p{{margin:0 0 7pt}}li{{margin:0 0 4pt}}.title{{font-size:24pt;font-weight:700;margin:0 0 10pt}}.sources{{margin-top:22pt}}</style></head><body><div class="title">{html.escape(title)}</div>{''.join(content)}<section class="sources"><h2>来源研报</h2><ol>{source_html}</ol></section></body></html>'''
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary:
        output_path = Path(temporary.name)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(page_html, wait_until="networkidle")
            page.pdf(path=str(output_path), format="A4", print_background=True)
            browser.close()
        return output_path.read_bytes()
    except Exception as exc:
        raise RuntimeError('PDF export is unavailable; install the Playwright Chromium browser') from exc
    finally:
        output_path.unlink(missing_ok=True)
