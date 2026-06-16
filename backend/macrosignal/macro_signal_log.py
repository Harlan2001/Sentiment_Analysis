"""
宏观信号请求日志模块

负责将每次 /api/macro/signal 调用结果写入 macro_signal_request_log 表。
写入失败只打日志，不向业务层抛出异常，保证主链路不受影响。
"""

import json
import logging
from datetime import datetime
from typing import Optional
from backend.common.database import get_db_connection

logger = logging.getLogger(__name__)

# queried_news 最多存储的 news_id 数量，防止 JSON 过大
MAX_QUERIED_NEWS = 100

_INSERT_SQL = """
INSERT INTO macro_signal_request_log (
    request_id,
    factor_code,
    signal_type,
    query_start_time,
    query_end_time,
    decay_lambda,
    signal_value,
    confidence,
    news_count,
    queried_news,
    success,
    error_message,
    started_at,
    finished_at,
    latency_ms
) VALUES (
    %(request_id)s,
    %(factor_code)s,
    %(signal_type)s,
    %(query_start_time)s,
    %(query_end_time)s,
    %(decay_lambda)s,
    %(signal_value)s,
    %(confidence)s,
    %(news_count)s,
    %(queried_news)s,
    %(success)s,
    %(error_message)s,
    %(started_at)s,
    %(finished_at)s,
    %(latency_ms)s
)
"""


def build_success_log_row(
    request_id: str,
    signal_result: dict,
    query_start_time: datetime,
    query_end_time: datetime,
    decay_lambda: float,
    started_at: datetime,
    finished_at: datetime,
    latency_ms: int,
) -> dict:
    """
    根据单个因子的信号计算结果组装成功日志行。
    signal_result 可能包含 error 字段（factor_code not found），此时视为失败行。
    """
    is_not_found = "error" in signal_result
    hit_news_ids = signal_result.get("hit_news_ids", [])[:MAX_QUERIED_NEWS]

    return {
        "request_id": request_id,
        "factor_code": signal_result["factor_code"],
        "signal_type": signal_result.get("signal_type", "presence"),
        "query_start_time": query_start_time,
        "query_end_time": query_end_time,
        "decay_lambda": decay_lambda,
        "signal_value": signal_result.get("signal_value"),
        "confidence": signal_result.get("confidence"),
        "news_count": signal_result.get("news_count", 0),
        "queried_news": json.dumps(hit_news_ids) if hit_news_ids else None,
        "success": 0 if is_not_found else 1,
        "error_message": signal_result.get("error", None),
        "started_at": started_at,
        "finished_at": finished_at,
        "latency_ms": latency_ms,
    }


def build_failure_log_rows(
    request_id: str,
    factor_codes: list,
    signal_type: Optional[str],
    query_start_time: Optional[datetime],
    query_end_time: Optional[datetime],
    decay_lambda: float,
    error_message: str,
    started_at: datetime,
    finished_at: datetime,
    latency_ms: int,
) -> list:
    """
    请求失败时（参数校验失败或服务异常）按 factor_code 列表组装失败日志行。
    若 factor_codes 为空（连解析都失败），则写一行 factor_code='UNKNOWN' 兜底。
    """
    codes = factor_codes if factor_codes else ["UNKNOWN"]
    truncated_msg = error_message[:500] if error_message else None

    rows = []
    for code in codes:
        rows.append({
            "request_id": request_id,
            "factor_code": code,
            "signal_type": signal_type or "presence",
            "query_start_time": query_start_time,
            "query_end_time": query_end_time,
            "decay_lambda": decay_lambda,
            "signal_value": None,
            "confidence": None,
            "news_count": 0,
            "queried_news": None,
            "success": 0,
            "error_message": truncated_msg,
            "started_at": started_at,
            "finished_at": finished_at,
            "latency_ms": latency_ms,
        })
    return rows


def insert_signal_logs(rows: list) -> None:
    """
    批量写入日志行到 macro_signal_request_log 表。
    写入失败只记录 warning，不向外抛出异常。
    """
    if not rows:
        return
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(_INSERT_SQL, rows)
            conn.commit()
    except Exception as e:
        logger.warning("宏观信号日志写入失败，不影响业务结果: %s", e)
