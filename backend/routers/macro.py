from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from backend.common.database import get_db_connection
from backend.config.config import API_PREFIX
from backend.macrosignal.macro_signal import (
    DEFAULT_DECAY_LAMBDA,
    SIGNAL_DIRECTIONAL,
    SIGNAL_PRESENCE,
    get_macro_signal,
)
from backend.macrosignal.macro_signal_log import (
    SignalRequestContext,
    build_failure_log_rows,
    build_success_log_row,
    insert_signal_logs,
)

router = APIRouter(prefix=f"{API_PREFIX}/macro", tags=["macro"])

shanghai_tz = ZoneInfo("Asia/Shanghai")

VALID_SIGNAL_TYPES = (SIGNAL_PRESENCE, SIGNAL_DIRECTIONAL)


def _now_utc_naive() -> datetime:
    """当前 UTC 时间的 naive 表示（存储约定：naive UTC，替代已弃用的 utcnow()）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_shanghai_naive(value: str) -> datetime:
    """把 ISO 时间归一化为上海墙钟的 naive datetime（存储约定：naive 上海墙钟）。"""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(shanghai_tz).replace(tzinfo=None)
    return parsed


def _signal_log_context(
    request_id: str,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    decay_lambda: float,
    started_at: datetime,
) -> SignalRequestContext:
    """组装信号请求日志上下文，finished_at 取当前时刻（即调用结束时），并计算耗时。"""
    finished_at = _now_utc_naive()
    latency_ms = int((finished_at - started_at).total_seconds() * 1000)
    return SignalRequestContext(
        request_id=request_id,
        query_start_time=start_dt,
        query_end_time=end_dt,
        decay_lambda=decay_lambda,
        started_at=started_at,
        finished_at=finished_at,
        latency_ms=latency_ms,
    )


@router.get("/signal")
def get_macro_signal_api(
    factor_code: str = Query(..., description="因子代码，多个用逗号分隔，如 A,B,C"),
    start_time: str = Query(
        ..., description="起始时间，ISO 格式，如 2025-01-01T00:00:00"
    ),
    end_time: str = Query(
        ..., description="结束时间，ISO 格式，如 2025-01-01T23:59:59"
    ),
    signal_type: str = Query(..., description="信号类型：presence | directional"),
    decay_lambda: float = Query(
        DEFAULT_DECAY_LAMBDA, description="时间衰减系数，仅 directional 生效"
    ),
):
    request_id = str(uuid.uuid4())
    started_at = _now_utc_naive()
    start_dt = end_dt = None
    codes = []
    log_rows = []
    normalized_signal_type = (
        signal_type if signal_type in VALID_SIGNAL_TYPES else None
    )

    try:
        if normalized_signal_type is None:
            raise HTTPException(
                status_code=400, detail="signal_type 必须为 presence 或 directional"
            )

        try:
            start_dt = _normalize_shanghai_naive(start_time)
            end_dt = _normalize_shanghai_naive(end_time)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="时间格式错误，请使用 ISO 格式，如 2025-01-01T00:00:00",
            )

        if start_dt > end_dt:
            raise HTTPException(status_code=400, detail="start_time 不能晚于 end_time")

        codes = list(
            dict.fromkeys(c.strip() for c in factor_code.split(",") if c.strip())
        )
        if not codes:
            raise HTTPException(status_code=400, detail="factor_code 不能为空")

        results = get_macro_signal(
            factor_codes=codes,
            start_time=start_dt,
            end_time=end_dt,
            signal_type=normalized_signal_type,
            decay_lambda=decay_lambda,
        )

        success_ctx = _signal_log_context(
            request_id, start_dt, end_dt, decay_lambda, started_at
        )
        for result in results:
            log_rows.append(build_success_log_row(success_ctx, result, signal_type))

        for item in results:
            item.pop("hit_news_ids", None)

        if len(codes) == 1:
            return results[0]
        return results

    except HTTPException as he:
        log_rows = build_failure_log_rows(
            _signal_log_context(request_id, start_dt, end_dt, decay_lambda, started_at),
            factor_codes=codes,
            signal_type=normalized_signal_type,
            error_message=he.detail,
        )
        raise

    except Exception as exc:
        log_rows = build_failure_log_rows(
            _signal_log_context(request_id, start_dt, end_dt, decay_lambda, started_at),
            factor_codes=codes,
            signal_type=normalized_signal_type,
            error_message=str(exc),
        )
        raise HTTPException(status_code=500, detail="服务内部错误")

    finally:
        insert_signal_logs(log_rows)


@router.get("/signal/logs")
def get_macro_signal_logs(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数，最大100"),
    request_id: Optional[str] = Query(None, description="请求ID过滤"),
    factor_code: Optional[str] = Query(None, description="因子代码过滤"),
    success: Optional[int] = Query(None, description="成功状态 0/1"),
    signal_type: Optional[str] = Query(
        None, description="信号类型 presence/directional"
    ),
    start_time: Optional[str] = Query(None, description="started_at 开始时间"),
    end_time: Optional[str] = Query(None, description="started_at 结束时间"),
):
    def _parse_filter_time_to_utc_naive(value: str, field_name: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"{field_name} 格式错误：{value}"
            )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=shanghai_tz)
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)

    if success is not None and success not in (0, 1):
        raise HTTPException(status_code=400, detail="success 只能为 0 或 1")
    if signal_type is not None and signal_type not in ("presence", "directional"):
        raise HTTPException(
            status_code=400, detail="signal_type 只能为 presence 或 directional"
        )

    start_dt = (
        _parse_filter_time_to_utc_naive(start_time, "start_time")
        if start_time
        else None
    )
    end_dt = _parse_filter_time_to_utc_naive(end_time, "end_time") if end_time else None

    conditions = []
    params: list = []
    if request_id:
        conditions.append("request_id = %s")
        params.append(request_id)
    if factor_code:
        conditions.append("factor_code = %s")
        params.append(factor_code)
    if success is not None:
        conditions.append("success = %s")
        params.append(success)
    if signal_type is not None:
        conditions.append("signal_type = %s")
        params.append(signal_type)
    if start_dt is not None:
        conditions.append("started_at >= %s")
        params.append(start_dt)
    if end_dt is not None:
        conditions.append("started_at <= %s")
        params.append(end_dt)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * page_size

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM macro_signal_request_log {where_clause}", params
        )
        total = cur.fetchone()[0]
        cur.execute(
            f"""
            SELECT l.id, l.request_id, l.factor_code, l.signal_type,
                   l.query_start_time, l.query_end_time, l.decay_lambda,
                   l.signal_value, l.confidence, l.news_count,
                   l.queried_news, l.success, l.error_message,
                   l.started_at, l.finished_at, l.latency_ms,
                   f.name AS factor_name
            FROM macro_signal_request_log l
            LEFT JOIN factor f ON f.code = l.factor_code
            {where_clause}
            ORDER BY l.started_at DESC, l.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    def _parse_queried_news(raw) -> list:
        if raw is None:
            return []
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, ValueError):
            return []

    def _fmt_dt(value):
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            dt_utc = value.replace(tzinfo=timezone.utc)
            return dt_utc.astimezone(shanghai_tz).isoformat()
        return str(value)

    def _fmt_query_time(value):
        # query_start/end 按存储约定已是上海墙钟 naive，无需换时区
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.strftime("%Y-%m-%dT%H:%M:%S")
        return str(value)

    items = [
        {
            "id": row[0],
            "request_id": row[1],
            "factor_code": row[2],
            "signal_type": row[3],
            "query_start_time": _fmt_query_time(row[4]),
            "query_end_time": _fmt_query_time(row[5]),
            "decay_lambda": float(row[6]) if row[6] is not None else None,
            "signal_value": float(row[7]) if row[7] is not None else None,
            "confidence": float(row[8]) if row[8] is not None else None,
            "news_count": row[9] or 0,
            "queried_news": _parse_queried_news(row[10]),
            "success": row[11],
            "error_message": row[12],
            "started_at": _fmt_dt(row[13]),
            "finished_at": _fmt_dt(row[14]),
            "latency_ms": row[15],
            "factor_name": row[16],
        }
        for row in rows
    ]

    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
        "filters": {
            "request_id": request_id,
            "factor_code": factor_code,
            "success": success,
            "signal_type": signal_type,
            "start_time": start_time,
            "end_time": end_time,
        },
    }