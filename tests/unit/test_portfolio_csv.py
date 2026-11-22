"""研究组合 CSV 解析、整批校验及导出公式防护。"""

import csv
import io
from decimal import Decimal

import pytest

from backend.portfolio.csv_io import (
    CSV_COLUMNS,
    MAX_IMPORT_BYTES,
    CsvImportFormatError,
    CsvImportTooLargeError,
    build_portfolio_csv,
    parse_holdings_csv,
    safe_csv_text,
)
from backend.portfolio.metrics import calculate_portfolio_metrics

HEADER = ",".join(CSV_COLUMNS)


def csv_bytes(*rows):
    return ("﻿" + "\n".join((HEADER, *rows)) + "\n").encode("utf-8")


def test_utf8_sig_import_preserves_decimal_and_null_values():
    holdings, errors = parse_holdings_csv(
        csv_bytes(
            " 240001 , 国债一 , 利率债 ,33.333333,-0.125000,0, 备注 ",
            "240002,国债二,信用债,6.666667,,,",
        )
    )

    assert errors == []
    assert len(holdings) == 2
    assert holdings[0] == {
        "bond_code": "240001",
        "bond_name": "国债一",
        "asset_category": "利率债",
        "weight_pct": Decimal("33.333333"),
        "yield_pct": Decimal("-0.125000"),
        "duration_years": Decimal("0"),
        "note": "备注",
        "_row": 2,
    }
    assert holdings[1]["yield_pct"] is None
    assert holdings[1]["duration_years"] is None
    assert holdings[1]["note"] is None
    assert holdings[1]["_row"] == 3


def test_row_validation_collects_field_row_and_duplicate_errors():
    holdings, errors = parse_holdings_csv(
        csv_bytes(
            "A,债券A,利率,0,2,1,",
            "a,债券a,利率,100.000001,2,1,",
            "B,,利率,20,NaN,-0.0001,",
            "C,债券C,利率,1.0000000,2,1,",
            "D,债券D,利率,20,2,1",
        )
    )

    assert holdings == []
    locations = {(error["row"], error["field"]) for error in errors}
    assert (2, "weight_pct") in locations
    assert (3, "weight_pct") in locations
    assert (4, "bond_name") in locations
    assert (4, "yield_pct") in locations
    assert (4, "duration_years") in locations
    assert (5, "weight_pct") in locations
    assert (6, "_row") in locations
    assert all(error["message"] for error in errors)


def test_duplicate_codes_are_case_insensitive_and_identify_both_rows():
    holdings, errors = parse_holdings_csv(
        csv_bytes("AbC,债券A,利率,10,2,1,", "abc,债券B,利率,20,3,2,")
    )

    assert len(holdings) == 1
    assert errors == [
        {"row": 3, "field": "bond_code", "message": "债券代码与第 2 行重复"}
    ]


def test_bond_code_rejects_non_ascii_and_unsupported_punctuation():
    holdings, errors = parse_holdings_csv(
        csv_bytes(
            "BAD/CODE,债券A,利率,10,2,1,",
            "债券A,债券B,利率,10,2,1,",
            "GOOD_A-1.2,债券C,利率,10,2,1,",
        )
    )

    assert [row["bond_code"] for row in holdings] == ["GOOD_A-1.2"]
    assert {(error["row"], error["field"]) for error in errors} == {
        (2, "bond_code"),
        (3, "bond_code"),
    }
    assert all("ASCII" in error["message"] for error in errors)


@pytest.mark.parametrize(
    "content, message",
    [
        (b"", "为空"),
        ("bond_code,bond_name\nA,债券\n".encode(), "表头"),
        (b"\xff\xfe\x00", "UTF-8"),
        (csv_bytes("A,债券,利率,10,2,1,") + b"\x00", "空字符"),
    ],
)
def test_file_level_validation(content, message):
    with pytest.raises(CsvImportFormatError, match=message):
        parse_holdings_csv(content)


def test_import_size_and_row_limits():
    with pytest.raises(CsvImportTooLargeError, match="1MB"):
        parse_holdings_csv(b"x" * (MAX_IMPORT_BYTES + 1))

    rows = [f"B{i:04d},债券{i},利率,0.1,2,1," for i in range(1001)]
    with pytest.raises(CsvImportFormatError, match="1000"):
        parse_holdings_csv(csv_bytes(*rows))


@pytest.mark.parametrize("value", ["=1+1", "+CMD", "-2+3", "@SUM(A1)", " \t=1", "\n@x"])
def test_csv_formula_prefixes_are_neutralized(value):
    sanitized = safe_csv_text(value)
    assert sanitized == "'" + value


@pytest.mark.parametrize("value", [None, "", "普通文本", "1+1", "（=）"])
def test_safe_csv_text_preserves_non_formula_text(value):
    assert safe_csv_text(value) == (value or "")


def test_export_contains_bom_metadata_holdings_metrics_and_safe_text_cells():
    holdings = [
        {
            "id": 1,
            "bond_code": "A",
            "bond_name": "=HYPERLINK(\"bad\")",
            "asset_category": "利率债",
            "weight_pct": Decimal("20"),
            "yield_pct": Decimal("-1.25"),
            "duration_years": Decimal("2"),
            "sort_order": 0,
            "note": "  @ dangerous",
        }
    ]
    detail = {
        "id": "portfolio-1",
        "name": "=1+1",
        "description": "说明",
        "size_amount": Decimal("1000"),
        "as_of_date": "2026-01-01",
        "target_duration": Decimal("0"),
        "status": "active",
        "version": 1,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "holdings": holdings,
        "metrics": calculate_portfolio_metrics(
            holdings, size_amount=Decimal("1000"), target_duration=Decimal("0")
        ),
    }

    content = build_portfolio_csv(detail)
    assert content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    cells = [cell for row in rows for cell in row]
    assert "'=1+1" in cells
    assert "'=HYPERLINK(\"bad\")" in cells
    assert "'  @ dangerous" in cells
    assert "-1.25" in cells  # 数值列的合法负数不能加公式防护前缀
    assert "'-1.25" not in cells
    assert "estimated_invested_amount" in cells
    assert "200.00" in cells
    assert "TARGET_DURATION_DEVIATION" in cells
    assert "medium" in cells
    assert "目标久期偏离" in cells
    assert any("加权久期与目标久期的偏离超过" in cell for cell in cells)
    assert "研究组合导出（配置金额为研究规模估算，非市值）" in cells
