"""研究组合 CSV 导入校验、公式注入防护与导出。"""

from __future__ import annotations

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from typing import Any

CSV_COLUMNS = (
    "bond_code",
    "bond_name",
    "asset_category",
    "weight_pct",
    "yield_pct",
    "duration_years",
    "note",
)
MAX_IMPORT_BYTES = 1024 * 1024
MAX_IMPORT_ROWS = 1000
BOND_CODE_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


class CsvImportFormatError(ValueError):
    """文件级格式错误；此时没有可导入的行。"""


class CsvImportTooLargeError(CsvImportFormatError):
    """上传内容超过 1 MiB。"""


def safe_csv_text(value: str | None) -> str:
    """防止文本被表格软件当作公式执行，保留原文并前置单引号。

    空格、制表符或换行后的 ``= + - @`` 同样按危险公式处理。数值列不走此函数，
    因而合法的负收益率仍以数值形式导出。
    """
    if value is None:
        return ""
    if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _decimal_value(
    raw: str,
    *,
    field: str,
    label: str,
    scale: int,
    upper_bound: Decimal,
    allow_zero: bool,
    allow_negative: bool,
) -> tuple[Decimal | None, str | None]:
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None, f"{label}必须是有效数字"
    if not value.is_finite():
        return None, f"{label}必须是有限数字"
    if value.as_tuple().exponent < -scale:
        return None, f"{label}最多保留 {scale} 位小数"
    if not allow_negative and value < 0:
        return None, f"{label}不能小于 0"
    if not allow_zero and value <= 0:
        return None, f"{label}必须大于 0"
    if value.copy_abs() >= upper_bound:
        return None, f"{label}超出存储范围"
    return value, None


def parse_holdings_csv(content: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """解析 UTF-8/UTF-8-SIG CSV，返回持仓及逐行错误。

    文件级错误抛出 ``CsvImportFormatError``；行级错误全部收集，调用方必须在
    ``errors`` 非空时放弃整批写入。持仓字典中的 ``_row`` 仅供导入错误定位。
    """
    if len(content) > MAX_IMPORT_BYTES:
        raise CsvImportTooLargeError("CSV 文件不能超过 1MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvImportFormatError("CSV 必须使用 UTF-8 或 UTF-8-SIG 编码") from exc
    if "\x00" in text:
        raise CsvImportFormatError("CSV 包含非法空字符")

    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise CsvImportFormatError("CSV 文件为空") from exc
    except csv.Error as exc:
        raise CsvImportFormatError(f"CSV 格式错误：{exc}") from exc
    if tuple(cell.strip() for cell in header) != CSV_COLUMNS:
        raise CsvImportFormatError("CSV 表头必须依次为：" + ",".join(CSV_COLUMNS))

    source_rows: list[tuple[int, list[str]]] = []
    try:
        for row_number, row in enumerate(reader, start=2):
            if not row or not any(cell.strip() for cell in row):
                continue
            source_rows.append((row_number, row))
            if len(source_rows) > MAX_IMPORT_ROWS:
                raise CsvImportFormatError("CSV 数据行不能超过 1000 行")
    except csv.Error as exc:
        raise CsvImportFormatError(f"CSV 格式错误：{exc}") from exc

    holdings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_codes: dict[str, int] = {}

    def add_error(row: int, field: str, message: str) -> None:
        errors.append({"row": row, "field": field, "message": message})

    for row_number, values in source_rows:
        if len(values) != len(CSV_COLUMNS):
            add_error(row_number, "_row", f"应有 {len(CSV_COLUMNS)} 列，实际为 {len(values)} 列")
            continue
        raw = dict(zip(CSV_COLUMNS, (cell.strip() for cell in values), strict=True))
        before = len(errors)

        required_limits = {
            "bond_code": (32, "债券代码"),
            "bond_name": (120, "债券名称"),
            "asset_category": (40, "资产类别"),
        }
        for field, (limit, label) in required_limits.items():
            if not raw[field]:
                add_error(row_number, field, f"{label}不能为空")
            elif len(raw[field]) > limit:
                add_error(row_number, field, f"{label}不能超过 {limit} 个字符")
        if raw["note"] and len(raw["note"]) > 500:
            add_error(row_number, "note", "备注不能超过 500 个字符")

        bond_code = raw["bond_code"]
        normalized_code = bond_code.casefold()
        code_is_valid = bool(bond_code) and BOND_CODE_PATTERN.fullmatch(bond_code) is not None
        if bond_code and len(bond_code) <= 32 and not code_is_valid:
            add_error(
                row_number,
                "bond_code",
                "债券代码仅支持 ASCII 字母、数字、点、下划线和连字符",
            )
        if code_is_valid:
            if normalized_code in seen_codes:
                add_error(
                    row_number,
                    "bond_code",
                    f"债券代码与第 {seen_codes[normalized_code]} 行重复",
                )
            else:
                seen_codes[normalized_code] = row_number

        weight, error = _decimal_value(
            raw["weight_pct"],
            field="weight_pct",
            label="权重",
            scale=6,
            upper_bound=Decimal("101"),
            allow_zero=False,
            allow_negative=False,
        )
        if error:
            add_error(row_number, "weight_pct", error)
        elif weight is not None and weight > Decimal("100"):
            add_error(row_number, "weight_pct", "权重不能大于 100")

        yield_pct: Decimal | None = None
        if raw["yield_pct"]:
            yield_pct, error = _decimal_value(
                raw["yield_pct"],
                field="yield_pct",
                label="收益率",
                scale=6,
                upper_bound=Decimal("10000"),
                allow_zero=True,
                allow_negative=True,
            )
            if error:
                add_error(row_number, "yield_pct", error)

        duration: Decimal | None = None
        if raw["duration_years"]:
            duration, error = _decimal_value(
                raw["duration_years"],
                field="duration_years",
                label="久期",
                scale=4,
                upper_bound=Decimal("1000000"),
                allow_zero=True,
                allow_negative=False,
            )
            if error:
                add_error(row_number, "duration_years", error)

        if len(errors) == before:
            holdings.append(
                {
                    "bond_code": bond_code,
                    "bond_name": raw["bond_name"],
                    "asset_category": raw["asset_category"],
                    "weight_pct": weight,
                    "yield_pct": yield_pct,
                    "duration_years": duration,
                    "note": raw["note"] or None,
                    "_row": row_number,
                }
            )

    return holdings, errors


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, str):
        return safe_csv_text(value)
    return value


def build_portfolio_csv(detail: dict[str, Any]) -> bytes:
    """导出组合元信息、持仓、指标、资产配置和确定性风险项，带 UTF-8 BOM。"""
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")

    def write(values: list[Any] | tuple[Any, ...]) -> None:
        writer.writerow([_csv_cell(value) for value in values])

    write(["研究组合导出（配置金额为研究规模估算，非市值）"])
    write(["字段", "值"])
    metadata = (
        ("组合ID", "id"),
        ("组合名称", "name"),
        ("组合说明", "description"),
        ("研究规模（人民币元）", "size_amount"),
        ("持仓日期", "as_of_date"),
        ("目标久期（年）", "target_duration"),
        ("状态", "status"),
        ("版本", "version"),
        ("创建时间", "created_at"),
        ("更新时间", "updated_at"),
    )
    for label, field in metadata:
        write([label, detail.get(field)])

    write([])
    write(["持仓"])
    write(list(CSV_COLUMNS[:6]) + ["sort_order", "note"])
    for holding in detail.get("holdings", []):
        write([holding.get(field) for field in (*CSV_COLUMNS[:6], "sort_order", "note")])

    metrics = detail.get("metrics", {})
    write([])
    write(["指标", "值"])
    for field in (
        "invested_weight",
        "cash_weight",
        "weighted_duration",
        "weighted_yield",
        "duration_coverage",
        "yield_coverage",
        "max_holding_weight",
        "max_holding_share_of_invested",
        "estimated_invested_amount",
        "estimated_cash_amount",
        "amount_basis",
    ):
        write([field, metrics.get(field)])

    write([])
    write(["资产配置", "权重（%）", "研究规模估算金额（人民币元）", "是否现金"])
    for allocation in metrics.get("asset_allocations", []):
        write(
            [
                allocation.get("category"),
                allocation.get("weight"),
                allocation.get("estimated_amount"),
                "是" if allocation.get("is_cash") else "否",
            ]
        )

    write([])
    write(["风险代码", "级别", "标题", "风险说明"])
    for risk in metrics.get("risk_items", []):
        write([risk.get("code"), risk.get("level"), risk.get("title"), risk.get("detail")])

    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")
