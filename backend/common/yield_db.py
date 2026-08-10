"""
收益率数据库模块 - 使用 Long Format 表结构
支持高效的收益率查询，基于新闻 pub_time 作为基准
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from backend.common.database import execute_query, get_db_connection
from backend.common.db_operations import DBOperations
from backend.config.config import BOND_XLSX, PERIOD_MAP

logger = logging.getLogger(__name__)


def import_yield_data_from_excel(excel_path: Path = BOND_XLSX):
    """
    从Excel文件追加导入收益率数据到Long Format表。
    规则：
    - 以 (date, period) 作为主键
    - 已存在的日期/期限组合直接跳过
    - 只插入从未出现过的新日期/期限组合
    """
    logger.info("开始从 %s 导入收益率数据...", excel_path)

    # 读取Excel
    df = pd.read_excel(excel_path)
    logger.debug("Excel列名: %s", df.columns.tolist())

    # 日期列处理
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])

    # 期限映射（自动匹配）
    actual_period_map = {}
    period_map = PERIOD_MAP  # 不用再 dict() 包一层

    for col in df.columns[1:]:
        col_clean = str(col).strip()
        for cn, p in period_map.items():
            if cn in col_clean or p in col_clean:
                actual_period_map[col] = p
                break

    logger.debug("期限映射: %s", actual_period_map)

    # 转长格式
    long_data = []
    for _, row in df.iterrows():
        date_str = row[date_col].strftime("%Y-%m-%d")
        for col, period in actual_period_map.items():
            val = row[col]
            if pd.notna(val):
                long_data.append(
                    {"date": date_str, "period": period, "value": float(val)}
                )

    # 前值填充（精简版）
    long_df = pd.DataFrame(long_data)
    long_df["value"] = (
        long_df.sort_values(["period", "date"]).groupby("period")["value"].ffill()
    )

    # 批量入库
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for _, row in long_df.iterrows():
            cursor.execute(
                "INSERT IGNORE INTO yield_data (date, period, value) VALUES (%s, %s, %s)",
                (row["date"], row["period"], row["value"]),
            )
        conn.commit()

    logger.info(
        "导入完成: %d 条记录, 日期范围 %s ~ %s, 期限数 %d",
        len(long_df),
        long_df["date"].min(),
        long_df["date"].max(),
        long_df["period"].nunique(),
    )


def get_yield_window_by_news_pub_time(
    pub_time, window_before: int = 14, window_after: int = 7, period: str = "10Y"
) -> Tuple[List[Dict], Optional[str], Optional[str]]:
    """根据新闻发布时间获取收益率窗口。

    pub_time 为 datetime.datetime / date 对象（如 2026-02-26 10:02:54）。
    """
    try:
        base_date = pub_time.date() if isinstance(pub_time, datetime) else pub_time
    except Exception:
        return [], None, None

    start = (base_date - timedelta(days=window_before)).strftime("%Y-%m-%d")
    end = (base_date + timedelta(days=window_after)).strftime("%Y-%m-%d")

    return DBOperations.get_yield_series_by_period(start, end, period), start, end


def get_yield_window_by_news_id(
    news_id: int, window_before: int = 14, window_after: int = 7, period: str = "10Y"
) -> Tuple[List[Dict], Optional[str], Optional[str]]:
    """根据新闻ID获取收益率窗口"""
    row = execute_query("SELECT pub_time FROM news WHERE id = %s", (news_id,), one=True)
    if not row:
        return [], None, None
    return get_yield_window_by_news_pub_time(
        row[0], window_before, window_after, period
    )
