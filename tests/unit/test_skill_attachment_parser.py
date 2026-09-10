"""Supported Skill attachment formats become source-labelled text without execution."""

from __future__ import annotations

import zipfile

import pymupdf
import pytest
from openpyxl import Workbook

from backend.services.skill_attachment_parser import AttachmentParseError, parse_attachment


def test_plain_text_and_csv_keep_source_locations(tmp_path):
    text_path = tmp_path / "notes.md"
    text_path.write_text("第一行\n第二行：流动性改善", encoding="utf-8")
    csv_path = tmp_path / "factors.csv"
    csv_path.write_text("因子,方向\n流动性,改善", encoding="utf-8-sig")

    text_result = parse_attachment(text_path, text_path.name)
    csv_result = parse_attachment(csv_path, csv_path.name)

    assert "流动性改善" in text_result.chunks[0]["content"]
    assert text_result.chunks[0]["source_location"] == "第 1-2 行"
    assert "流动性 改善" in csv_result.chunks[0]["content"]


def test_docx_is_read_as_text_without_running_embedded_content(tmp_path):
    path = tmp_path / "brief.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>政策传导路径</w:t></w:r></w:p></w:body>
    </w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    result = parse_attachment(path, path.name)

    assert result.chunks[0]["content"] == "政策传导路径"
    assert result.chunks[0]["source_location"] == "第 1 段"


def test_xlsx_reads_cell_values_with_sheet_and_row_location(tmp_path):
    path = tmp_path / "factors.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "信用利差"
    worksheet.append(["日期", "数值"])
    worksheet.append(["2026-09-08", 42])
    workbook.save(path)

    result = parse_attachment(path, path.name)

    assert "2026-09-08 42" in result.chunks[0]["content"]
    assert "工作表 信用利差" in result.chunks[0]["source_location"]


def test_pdf_reads_pages_and_reports_page_count(tmp_path):
    path = tmp_path / "news.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Bond market news")
    document.save(path)
    document.close()

    result = parse_attachment(path, path.name)

    assert result.page_count == 1
    assert "Bond market news" in result.chunks[0]["content"]
    assert result.chunks[0]["source_location"] == "第 1 页"


def test_image_only_pdf_reports_clear_failure(tmp_path):
    path = tmp_path / "scan.pdf"
    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()

    with pytest.raises(AttachmentParseError, match="扫描版"):
        parse_attachment(path, path.name)
