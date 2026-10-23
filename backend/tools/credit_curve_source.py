"""信用债曲线取数：复用中债下载接口，仅换曲线参数。

与国债下载器（backend/tools/bond_downloader.py）**同一个接口**：
    https://yield.chinabond.com.cn/cbweb-czb-web/czb/historyDown
差异仅在 ``nameType``：
    nameType=1 → 国债收益率曲线（现有）
    nameType=2 → 中短期票据收益率曲线（本模块）

**限制**：该端点只提供"中短期票据"整体曲线，不提供分评级曲线
（`nameType>=3` 返回 HTML 错误页），故无法按 AAA/AA 分档。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from backend.config.config import get_requests_proxies

logger = logging.getLogger(__name__)

_ENDPOINT = "https://yield.chinabond.com.cn/cbweb-czb-web/czb/historyDown"
# 中短期票据收益率曲线
_NAME_TYPE = "2"

# 该曲线的期限列 → 期限码（实测列名为 1年/2年/3年/5年/7年/10年/15年/20年/30年）
_TERM_MAP: dict[str, str] = {
    "1年": "1Y",
    "2年": "2Y",
    "3年": "3Y",
    "5年": "5Y",
    "7年": "7Y",
    "10年": "10Y",
    "15年": "15Y",
    "20年": "20Y",
    "30年": "30Y",
}

# 接口限制：单次下载时段不得超过 1 年
MAX_WINDOW_DAYS = 365


class CreditCurveError(RuntimeError):
    """取数失败（网络异常 / 接口改版 / 非交易日无数据）。"""


def download_credit_curve(
    start_date: str,
    end_date: str,
    output_path: Path | None = None,
) -> Path:
    """下载指定区间的中短期票据曲线 Excel。"""
    span = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days
    if span >= MAX_WINDOW_DAYS:
        raise CreditCurveError(f"下载时段不能超过 1 年（当前 {span} 天）")

    params = {
        "startDate": start_date,
        "endDate": end_date,
        "gjqx": "0",  # 取全期限
        "locale": "zh_CN",
        "nameType": _NAME_TYPE,
        "qxmc": _NAME_TYPE,
    }
    try:
        response = requests.get(
            _ENDPOINT, params=params, timeout=60, proxies=get_requests_proxies()
        )
        response.raise_for_status()
    except Exception as exc:
        raise CreditCurveError(f"信用债曲线下载失败: {exc}") from exc

    # 接口异常时返回 HTML 错误页而非 Excel
    if not response.content[:2] == b"PK":
        raise CreditCurveError("信用债曲线下载失败：返回内容不是 Excel（接口可能已变更）")

    if output_path is None:
        from backend.config.config import DATA_DIR

        output_path = DATA_DIR / "CreditBonds.xlsx"
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    logger.info("信用债曲线已下载: %s (%d 字节)", output_path, len(response.content))
    return output_path


def parse_credit_curve(excel_path: Path) -> list[dict[str, Any]]:
    """解析中债信用债曲线 Excel 为待入库记录。

    表格式：首列为日期，其余各列为期限（1年/2年/...），单元格为收益率。
    """
    try:
        frame = pd.read_excel(excel_path)
    except Exception as exc:
        raise CreditCurveError(f"Excel 解析失败: {exc}") from exc

    if frame.empty:
        return []

    date_column = frame.columns[0]
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")

    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        raw_date = row[date_column]
        if pd.isna(raw_date):
            continue
        trade_date = raw_date.strftime("%Y-%m-%d")
        for column in frame.columns[1:]:
            # 列名可能带空格，且需容忍「1年」这类中文列名
            label = str(column).strip()
            term = _TERM_MAP.get(label)
            if term is None:
                # 退化匹配：列名包含 "10年" 等
                for key, code in _TERM_MAP.items():
                    if key in label:
                        term = code
                        break
            if term is None:
                continue
            value = row[column]
            if pd.isna(value):
                continue
            try:
                number = float(str(value).strip())
            except (TypeError, ValueError):
                continue
            records.append({"trade_date": trade_date, "term": term, "value": round(number, 4)})

    logger.info("信用债曲线解析完成: %d 条", len(records))
    return records


def fetch_credit_curve(days: int = 365) -> list[dict[str, Any]]:
    """下载并解析最近 N 天的信用债曲线（N 不超过 365）。"""
    end = date.today()
    start = end - timedelta(days=min(days, MAX_WINDOW_DAYS) - 1)
    path = download_credit_curve(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    return parse_credit_curve(path)