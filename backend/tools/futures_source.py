"""国债期货持仓取数：中金所成交持仓排名。

数据源：``http://www.cffex.com.cn/sj/ccpm/YYYYMM/DD/{品种}_1.csv``
- 公开接口，无需认证；CSV 为 **GBK** 编码
- 覆盖 T(10年) / TF(5年) / TS(2年) / TL(30年) 四个国债期货品种
- 每天一个文件；历史可回溯（实测 2020 年起的日期可达）

每个 CSV 为多级表头：第 1 行分组（成交量排名/持买单量排名/持卖单量排名），
第 2 行为真正列名，第 3 行起为前 20 名会员数据。
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date
from typing import Any

import requests

from backend.config.config import get_requests_proxies

logger = logging.getLogger(__name__)

_BASE = "http://www.cffex.com.cn/sj/ccpm"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# 仅国债期货（股指期货不纳入：平台定位为债券分析）
VARIETIES: tuple[str, ...] = ("T", "TF", "TS", "TL")
VARIETY_LABELS: dict[str, str] = {
    "T": "10年期国债期货",
    "TF": "5年期国债期货",
    "TS": "2年期国债期货",
    "TL": "30年期国债期货",
}

# CSV 列序（第 2 行为列名行，第 3 行起为数据）
_COL_DATE = 0
_COL_CONTRACT = 1
_COL_RANK = 2
_COL_VOL_TRADER = 3
_COL_VOLUME = 4
_COL_VOL_CHANGE = 5
_COL_LONG_TRADER = 6
_COL_LONG_POS = 7
_COL_LONG_CHANGE = 8
_COL_SHORT_TRADER = 9
_COL_SHORT_POS = 10
_COL_SHORT_CHANGE = 11


class FuturesSourceError(RuntimeError):
    """取数失败（网络异常 / 非交易日无数据 / 结构不符合预期）。"""


def _int_or_none(value: Any) -> int | None:
    """转 int；空串 / '-' / 非数值返回 None。"""
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "--"}:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _text_or_none(value: Any) -> str | None:
    """空串归一为 None。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_position_csv(content: bytes, variety: str) -> list[dict[str, Any]]:
    """解析单个品种的持仓排名 CSV，返回待入库记录。

    CSV 为 GBK 编码；第 1 行是分组表头，第 2 行是列名，第 3 行起为数据。
    """
    try:
        text = content.decode("gbk", errors="replace")
    except Exception as exc:  # 编码异常不应中断整个批次
        raise FuturesSourceError(f"{variety} CSV 解码失败: {exc}") from exc

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if len(rows) < 3:
        # 非交易日/节假日无数据文件，属正常情况
        return []

    records: list[dict[str, Any]] = []
    for row in rows[2:]:
        if len(row) <= _COL_SHORT_CHANGE:
            continue
        raw_date = _text_or_none(row[_COL_DATE])
        contract = _text_or_none(row[_COL_CONTRACT])
        rank_no = _int_or_none(row[_COL_RANK])
        if not raw_date or not contract or rank_no is None:
            continue
        # 日期形如 20261021 → 2026-10-21
        if len(raw_date) == 8 and raw_date.isdigit():
            trade_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        else:
            continue

        records.append(
            {
                "trade_date": trade_date,
                "variety": variety,
                "contract": contract,
                "rank_no": rank_no,
                "volume_trader": _text_or_none(row[_COL_VOL_TRADER]),
                "volume": _int_or_none(row[_COL_VOLUME]),
                "volume_change": _int_or_none(row[_COL_VOL_CHANGE]),
                "long_trader": _text_or_none(row[_COL_LONG_TRADER]),
                "long_position": _int_or_none(row[_COL_LONG_POS]),
                "long_change": _int_or_none(row[_COL_LONG_CHANGE]),
                "short_trader": _text_or_none(row[_COL_SHORT_TRADER]),
                "short_position": _int_or_none(row[_COL_SHORT_POS]),
                "short_change": _int_or_none(row[_COL_SHORT_CHANGE]),
            }
        )
    return records


def fetch_positions(trade_date: date, varieties: tuple[str, ...] = VARIETIES) -> list[dict[str, Any]]:
    """抓取指定交易日、指定品种的持仓排名。

    单个品种缺数据（非交易日）不视为失败；全部品种都无数据则抛错，
    避免把"取不到"静默当成"当天没有"。
    """
    path_date = f"{trade_date.year}{trade_date.month:02d}/{trade_date.day:02d}"
    proxies = get_requests_proxies()
    records: list[dict[str, Any]] = []
    errors: list[str] = []

    for variety in varieties:
        url = f"{_BASE}/{path_date}/{variety}_1.csv"
        try:
            response = requests.get(url, headers=_HEADERS, timeout=30, proxies=proxies)
            if response.status_code == 404:
                continue  # 该品种当日无文件
            response.raise_for_status()
        except Exception as exc:
            errors.append(f"{variety}: {exc}")
            continue
        records.extend(parse_position_csv(response.content, variety))

    if not records:
        detail = "; ".join(errors) if errors else "该交易日无持仓数据（可能为非交易日）"
        raise FuturesSourceError(f"国债期货持仓取数失败: {detail}")

    logger.info("国债期货持仓取数完成: %s 共 %d 条", trade_date, len(records))
    return records