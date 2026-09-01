"""
宏观信号请求日志模块

负责将每次 /api/macro/signal 调用结果写入 macro_signal_request_log 表。
写入失败只打日志，不向业务层抛出异常，保证主链路不受影响。
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from backend.common.database import get_db_connection

logger = logging.getLogger(__name__)

# queried_news 最多存储的 news_id 数量，防止 JSON 过大
MAX_QUERIED_NEWS = 100

# factor_code 解析失败时的兜底值
_FALLBACK_FACTOR_CODE = "UNKNOWN"
# signal_type 非法/缺失时日志中落库的缺省值
_FALLBACK_SIGNAL_TYPE = "presence"

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


@dataclass(frozen=True)
class SignalRequestContext:
    """单次信号查询请求的公共上下文，成功与失败日志行共享。"""

    request_id: str
    query_start_time: Optional[datetime]
    query_end_time: Optional[datetime]
    decay_lambda: float
    started_at: datetime
    finished_at: datetime
    latency_ms: int


def _build_log_row(
    ctx: SignalRequestContext,
    factor_code: str,
    signal_type: str,
    success: int,
    error_message: Optional[str] = None,
    signal_value=None,
    confidence=None,
    news_count: int = 0,
    queried_news=None,
) -> dict:
    """组装一条日志行：公共字段取自已校验的 ctx，信号字段按调用方传入。"""
    return {
        "request_id": ctx.request_id,
        "factor_code": factor_code,
        "signal_type": signal_type,
        "query_start_time": ctx.query_start_time,
        "query_end_time": ctx.query_end_time,
        "decay_lambda": ctx.decay_lambda,
        "signal_value": signal_value,
        "confidence": confidence,
        "news_count": news_count,
        "queried_news": queried_news,
        "success": success,
        "error_message": error_message,
        "started_at": ctx.started_at,
        "finished_at": ctx.finished_at,
        "latency_ms": ctx.latency_ms,
    }


def build_success_log_row(
    ctx: SignalRequestContext,
    signal_result: dict,
    signal_type: str,
) -> dict:
    """
    根据单个因子的信号计算结果组装成功日志行。
    signal_result 可能包含 error 字段（factor_code not found），此时视为失败行。
    signal_type 为请求方指定的类型；信号结果含 signal_type 时以其为准。
    """
    is_not_found = "error" in signal_result
    hit_news_ids = signal_result.get("hit_news_ids", [])[:MAX_QUERIED_NEWS]

    return _build_log_row(
        ctx,
        factor_code=signal_result["factor_code"],
        signal_type=signal_result.get("signal_type") or signal_type,
        success=0 if is_not_found else 1,
        error_message=signal_result.get("error"),
        signal_value=signal_result.get("signal_value"),
        confidence=signal_result.get("confidence"),
        news_count=signal_result.get("news_count", 0),
        queried_news=json.dumps(hit_news_ids) if hit_news_ids else None,
    )


def build_failure_log_rows(
    ctx: SignalRequestContext,
    factor_codes: list,
    signal_type: Optional[str],
    error_message: str,
) -> list:
    """
    请求失败时（参数校验失败或服务异常）按 factor_code 列表组装失败日志行。
    若 factor_codes 为空（连解析都失败），则写一行 factor_code='UNKNOWN' 兜底。
    """
    codes = factor_codes if factor_codes else [_FALLBACK_FACTOR_CODE]
    truncated_msg = error_message[:500] if error_message else None

    return [
        _build_log_row(
            ctx,
            factor_code=code,
            signal_type=signal_type or _FALLBACK_SIGNAL_TYPE,
            success=0,
            error_message=truncated_msg,
        )
        for code in codes
    ]


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