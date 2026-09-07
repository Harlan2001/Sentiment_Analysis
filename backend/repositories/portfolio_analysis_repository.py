"""组合策略分析结果缓存仓储（``portfolio_strategy_analysis_cache`` 表）。

按 ``cache_key``（目标新闻日 + 模型 + 数据版本）命中即复用，``force_refresh``
强制重算后覆盖。失败只记录 ``status='fail'`` 与 ``error_message``。
"""

from __future__ import annotations

import json
from typing import Any, Optional

from backend.common.database import execute_query, execute_update

_CACHE_TABLE = "portfolio_strategy_analysis_cache"


class PortfolioAnalysisRepository:
    """组合策略分析结果缓存读写。"""

    def get_by_cache_key(self, cache_key: str) -> Optional[dict[str, Any]]:
        """按缓存键读取最近一条记录；不存在返回 None。

        ``output`` / ``news_ids`` 由 JSON 列反序列化，时间列保持原始值，
        由调用方统一格式化为对外字符串。
        """
        row = execute_query(
            f"SELECT id, cache_key, target_news_date, model_name, status, "
            f"output_json, news_count, news_ids_json, window_start, window_end, "
            f"latest_news_pub_time, request_id, error_message, started_at, "
            f"finished_at, latency_ms "
            f"FROM {_CACHE_TABLE} WHERE cache_key=%s ORDER BY id DESC LIMIT 1",
            (cache_key,),
            one=True,
        )
        if not row:
            return None
        (
            row_id,
            cache_key,
            target_news_date,
            model_name,
            status,
            output_json,
            news_count,
            news_ids_json,
            window_start,
            window_end,
            latest_news_pub_time,
            request_id,
            error_message,
            started_at,
            finished_at,
            latency_ms,
        ) = row
        return {
            "id": row_id,
            "cache_key": cache_key,
            "target_news_date": target_news_date,
            "model_name": model_name,
            "status": status,
            "output": json.loads(output_json) if output_json else None,
            "news_count": news_count,
            "news_ids": json.loads(news_ids_json) if news_ids_json else [],
            "window_start": window_start,
            "window_end": window_end,
            "latest_news_pub_time": latest_news_pub_time,
            "request_id": request_id,
            "error_message": error_message,
            "started_at": started_at,
            "finished_at": finished_at,
            "latency_ms": latency_ms,
        }

    def save_success(
        self,
        *,
        cache_key: str,
        target_news_date,
        model_name: str,
        analysis: dict[str, Any],
        news_ids: list[int],
        news_count: int,
        window_start,
        window_end,
        latest_news_pub_time,
        request_id: str,
        started_at,
        finished_at,
        latency_ms: int,
    ) -> None:
        """写入/覆盖一条成功分析记录（``status='success'``）。"""
        execute_update(
            f"INSERT INTO {_CACHE_TABLE} "
            f"(cache_key, target_news_date, model_name, status, output_json, "
            f"news_count, news_ids_json, window_start, window_end, "
            f"latest_news_pub_time, request_id, started_at, finished_at, "
            f"latency_ms) VALUES (%s,%s,%s,'success',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            f"ON DUPLICATE KEY UPDATE "
            f"target_news_date=VALUES(target_news_date), "
            f"model_name=VALUES(model_name), status=VALUES(status), "
            f"output_json=VALUES(output_json), news_count=VALUES(news_count), "
            f"news_ids_json=VALUES(news_ids_json), "
            f"window_start=VALUES(window_start), window_end=VALUES(window_end), "
            f"latest_news_pub_time=VALUES(latest_news_pub_time), "
            f"request_id=VALUES(request_id), error_message=NULL, "
            f"started_at=VALUES(started_at), finished_at=VALUES(finished_at), "
            f"latency_ms=VALUES(latency_ms)",
            (
                cache_key,
                target_news_date,
                model_name,
                json.dumps(analysis, ensure_ascii=False, default=str),
                news_count,
                json.dumps(news_ids, ensure_ascii=False),
                window_start,
                window_end,
                latest_news_pub_time,
                request_id,
                started_at,
                finished_at,
                latency_ms,
            ),
        )

    def save_failure(
        self,
        *,
        cache_key: str,
        target_news_date,
        model_name: str,
        request_id: str,
        error_message: str,
        started_at,
        finished_at,
        latency_ms: int,
    ) -> None:
        """写入一条失败记录（``status='fail'``，仅保留错误信息）。"""
        execute_update(
            f"INSERT INTO {_CACHE_TABLE} "
            f"(cache_key, target_news_date, model_name, status, news_count, "
            f"request_id, error_message, started_at, finished_at, latency_ms) "
            f"VALUES (%s,%s,%s,'fail',0,%s,%s,%s,%s,%s) "
            f"ON DUPLICATE KEY UPDATE "
            f"status=VALUES(status), error_message=VALUES(error_message), "
            f"request_id=VALUES(request_id), started_at=VALUES(started_at), "
            f"finished_at=VALUES(finished_at), latency_ms=VALUES(latency_ms)",
            (
                cache_key,
                target_news_date,
                model_name,
                request_id,
                error_message,
                started_at,
                finished_at,
                latency_ms,
            ),
        )