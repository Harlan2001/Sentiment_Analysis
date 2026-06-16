from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.analysis.analyzer import process_single_news_analysis
from backend.config.config import (
    ANALYSIS_MODEL_PRIORITY,
    NEWS_SOURCES,
    MYSQL_CONFIG,
    get_default_analysis_model_name,
)
from backend.common.database import DatabaseConfig, execute_query, get_db_connection, init_database
from backend.common.db_operations import DBOperations
from backend.task_logging import add_task_event, finish_task_run, start_task_run
from backend.vector_store import get_faiss_store
from backend.yield_db import get_yield_window_by_news_id

router = APIRouter(prefix="/api", tags=["news"])


class AnalysisTriggerRequest(BaseModel):
    idempotency_key: str
    mode: str = "model_missing"
    limit: Optional[int] = None
    model_name: Optional[str] = None
    news_ids: Optional[List[int]] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    run_vector_index: bool = True
    vector_batch_size: int = 200
    vector_limit: Optional[int] = None
    run_strategy_push: bool = True


def _priority_cases() -> str:
    return "".join([f"WHEN '{m}' THEN {i} " for i, m in enumerate(ANALYSIS_MODEL_PRIORITY)])


def _run_vector_index_update(batch_size: int = 200, limit: Optional[int] = None) -> Dict[str, Any]:
    db_config = DatabaseConfig(**MYSQL_CONFIG)
    init_database(db_config)
    store = get_faiss_store()

    processed = 0
    added = 0
    loops = 0

    while True:
        if limit is not None and processed >= limit:
            break

        current_batch_size = batch_size
        if limit is not None:
            remaining = limit - processed
            if remaining <= 0:
                break
            current_batch_size = min(batch_size, remaining)

        pending_items = store.get_pending_news(batch_size=current_batch_size)
        if not pending_items:
            break

        loops += 1
        pending_ids = [news_id for news_id, _ in pending_items]
        added_count = store.batch_add(pending_items)
        added += added_count
        store.mark_as_indexed(pending_ids)
        store.save()
        processed += len(pending_items)

    return {
        "loops": loops,
        "processed": processed,
        "added": added,
        "index_size": store.size(),
        "batch_size": batch_size,
        "limit": limit,
    }


@router.get("/yields")
def get_yields(start: str, end: str, type: str = Query("10年")):
    try:
        return DBOperations.get_yield_series_by_period(start, end, type)
    except Exception as exc:
        return {"error": f"数据库表不存在或数据未初始化: {str(exc)}. 请运行 python init_yield_db.py 初始化数据库"}


@router.get("/news")
def get_news(
    date: Optional[str] = Query(None, description="单个日期查询，格式 YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="时间段开始日期，格式 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="时间段结束日期，格式 YYYY-MM-DD"),
    source: Optional[str] = Query(None, description="新闻源过滤，多个用逗号分隔，如 cls,wechat"),
    model: Optional[str] = Query(None, description="模型短名，用于 single/all 视图过滤"),
    view: str = Query("best", description="best | single | all"),
):
    priority_cases = _priority_cases()
    params = []
    date_filter = ""

    if date:
        date_filter = "DATE(n.pub_time) = %s"
        params = [date]
    elif start_date and end_date:
        date_filter = "DATE(n.pub_time) BETWEEN %s AND %s"
        params = [start_date, end_date]
    else:
        default_end = datetime.now().strftime("%Y-%m-%d")
        default_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        date_filter = "DATE(n.pub_time) BETWEEN %s AND %s"
        params = [default_start, default_end]

    source_filter = ""
    if source:
        sources = [s.strip() for s in source.split(",") if s.strip()]
        if sources:
            placeholders = ",".join(["%s" for _ in sources])
            source_filter = f"AND n.source IN ({placeholders})"
            params.extend(sources)

    effective_view = view if view in ("best", "single", "all") else "best"
    if effective_view == "single" and not model:
        model = get_default_analysis_model_name()

    with get_db_connection() as conn:
        cur = conn.cursor()

        if effective_view == "single":
            cur.execute(
                f"""
                SELECT n.id, n.title, n.pub_time, n.source,
                       COALESCE(a.direction, '中性') as direction,
                       COALESCE(a.horizon, '短期') as horizon,
                       COALESCE(a.reason, '待分析') as reason,
                       COALESCE(a.model, %s) as model
                FROM news n
                LEFT JOIN analysis a ON a.news_id = n.id AND a.model = %s
                WHERE {date_filter} {source_filter}
                ORDER BY n.pub_time ASC
                """,
                [model, model] + params,
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "title": r[1],
                    "publish_time": r[2],
                    "source": NEWS_SOURCES.get(r[3], r[3]),
                    "direction": r[4],
                    "horizon": r[5],
                    "reason": r[6],
                    "model": r[7],
                    "selected_model": r[7],
                    "analyses": [],
                }
                for r in rows
            ]

        if effective_view == "best":
            cur.execute(
                f"""
                SELECT n.id, n.title, n.pub_time, n.source,
                       COALESCE(a.direction, '中性') as direction,
                       COALESCE(a.horizon, '短期') as horizon,
                       COALESCE(a.reason, '待分析') as reason,
                       COALESCE(a.model, 'default') as model
                FROM news n
                LEFT JOIN analysis a ON a.news_id = n.id
                    AND a.model = (
                        SELECT model FROM analysis
                        WHERE news_id = n.id
                        ORDER BY CASE model
                            {priority_cases}
                            ELSE 999
                        END
                        LIMIT 1
                    )
                WHERE {date_filter} {source_filter}
                ORDER BY n.pub_time ASC
                """,
                params,
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "title": r[1],
                    "publish_time": r[2],
                    "source": NEWS_SOURCES.get(r[3], r[3]),
                    "direction": r[4],
                    "horizon": r[5],
                    "reason": r[6],
                    "model": r[7],
                    "selected_model": r[7],
                    "analyses": [],
                }
                for r in rows
            ]

        cur.execute(
            f"""
            SELECT n.id, n.title, n.pub_time, n.source
            FROM news n
            WHERE {date_filter} {source_filter}
            ORDER BY n.pub_time ASC
            """,
            params,
        )
        news_rows = cur.fetchall()
        if not news_rows:
            return []

        news_ids = [r[0] for r in news_rows]
        placeholders = ",".join(["%s"] * len(news_ids))
        analysis_sql = f"""
            SELECT news_id, direction, horizon, reason, model
            FROM analysis
            WHERE news_id IN ({placeholders})
        """
        analysis_params: List[Any] = list(news_ids)
        if model:
            analysis_sql += " AND model = %s"
            analysis_params.append(model)

        cur.execute(analysis_sql, analysis_params)
        analysis_rows = cur.fetchall()

    analyses_by_news: Dict[int, List[Dict[str, Any]]] = {}
    for news_id, direction, horizon, reason, model_name in analysis_rows:
        analyses_by_news.setdefault(news_id, []).append(
            {
                "direction": direction or "中性",
                "horizon": horizon or "短期",
                "reason": reason or "待分析",
                "model": model_name,
            }
        )

    priority_rank = {m: i for i, m in enumerate(ANALYSIS_MODEL_PRIORITY)}
    result: List[Dict[str, Any]] = []

    for row in news_rows:
        current_analyses = analyses_by_news.get(row[0], [])
        if current_analyses:
            selected = sorted(current_analyses, key=lambda x: priority_rank.get(x["model"], 999))[0]
        else:
            selected = {"direction": "中性", "horizon": "短期", "reason": "待分析", "model": model or "default"}

        result.append(
            {
                "id": row[0],
                "title": row[1],
                "publish_time": row[2],
                "source": NEWS_SOURCES.get(row[3], row[3]),
                "direction": selected["direction"],
                "horizon": selected["horizon"],
                "reason": selected["reason"],
                "model": selected["model"],
                "selected_model": selected["model"],
                "analyses": current_analyses,
            }
        )

    return result


@router.get("/news/sources")
def get_news_sources():
    return {"sources": [{"key": key, "name": name, "enabled": True} for key, name in NEWS_SOURCES.items()]}


@router.get("/news/latest-trading-day")
def get_latest_publish_day():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT MAX(DATE(pub_time))
                FROM news
                WHERE pub_time IS NOT NULL
                """
            )
            result = cursor.fetchone()
            latest_date = result[0] if result and result[0] else datetime.now().strftime("%Y-%m-%d")
    return {"latest_date": latest_date}


@router.get("/news/similar")
def similar_news(news_id: int, top_k: int = 5):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT content FROM news WHERE id=%s", (news_id,))
        row = cur.fetchone()
        if not row:
            return []
        content = row[0]
        store = get_faiss_store()
        query_emb = store.model.encode([content], normalize_embeddings=True, convert_to_numpy=True).astype("float32")
        results = store.search_by_vector(query_emb, top_k + 1)

        out = []
        for item in results:
            nid = item["news_id"]
            score = item["score"]
            if nid == news_id:
                continue
            cur.execute("SELECT title FROM news WHERE id=%s", (nid,))
            row = cur.fetchone()
            if row:
                out.append({"news_id": nid, "score": round(score, 3), "title": row[0]})
            if len(out) >= top_k:
                break
    return out


@router.get("/news/{news_id}")
def get_news_detail(
    news_id: int,
    model: Optional[str] = Query(None, description="模型短名，不传则按优先级取 best"),
    include_all_models: bool = Query(False, description="是否返回多模型结果"),
):
    news_row = execute_query(
        """
        SELECT id, title, pub_time, content, source
        FROM news
        WHERE id = %s
        """,
        (news_id,),
        one=True,
    )
    if not news_row:
        return {}

    all_analysis_rows = execute_query(
        """
        SELECT direction, horizon, reason, model
        FROM analysis
        WHERE news_id = %s
        """,
        (news_id,),
        one=False,
    )

    analyses_by_model: Dict[str, Dict[str, Any]] = {}
    for a_row in all_analysis_rows:
        analyses_by_model[a_row[3]] = {
            "direction": a_row[0] or "中性",
            "horizon": a_row[1] or "短期",
            "reason": a_row[2] or "待分析",
            "model": a_row[3],
        }

    selected_model = model
    if not selected_model:
        for model_name in ANALYSIS_MODEL_PRIORITY:
            if model_name in analyses_by_model:
                selected_model = model_name
                break
    if not selected_model:
        selected_model = "default"

    selected_analysis = analyses_by_model.get(selected_model, {"direction": "中性", "horizon": "短期", "reason": "待分析", "model": selected_model})

    def _query_factors_for_model(model_name: str) -> List[Dict[str, Any]]:
        factor_rows = execute_query(
            """
            SELECT f.code, f.name, f.category, nf.direction, nf.driver
            FROM news_factor nf
            JOIN factor f ON nf.factor_id = f.id
            WHERE nf.news_id = %s AND nf.model = %s
            ORDER BY f.code ASC
            """,
            (news_id, model_name),
            one=False,
        )
        return [
            {"code": r[0], "name": r[1] or r[0], "category": r[2], "direction": r[3], "driver": r[4]}
            for r in factor_rows
        ]

    selected_factors = _query_factors_for_model(selected_model)
    analyses_payload: List[Dict[str, Any]] = []
    if include_all_models:
        for model_name, analysis_data in analyses_by_model.items():
            analyses_payload.append({**analysis_data, "factors": _query_factors_for_model(model_name)})

    content_block_rows = execute_query(
        """
        SELECT id, news_id, block_type, block_order, content,
               heading_level, image_url, image_alt, image_width,
               table_caption, table_unit, table_headers, table_rows, created_at
        FROM news_content_blocks
        WHERE news_id = %s
        ORDER BY block_order ASC
        """,
        (news_id,),
        one=False,
    )

    content_blocks = []
    for block_row in content_block_rows:
        block = {
            "id": block_row[0],
            "news_id": block_row[1],
            "block_type": block_row[2],
            "block_order": block_row[3],
            "content": block_row[4],
            "heading_level": block_row[5],
            "image_url": block_row[6],
            "image_alt": block_row[7],
            "image_width": block_row[8],
            "table_caption": block_row[9],
            "table_unit": block_row[10],
            "table_headers": None,
            "table_rows": None,
            "created_at": block_row[13],
        }
        if block_row[11]:
            try:
                block["table_headers"] = json.loads(block_row[11])
            except (json.JSONDecodeError, ValueError):
                pass
        if block_row[12]:
            try:
                block["table_rows"] = json.loads(block_row[12])
            except (json.JSONDecodeError, ValueError):
                pass
        content_blocks.append(block)

    source_key = news_row[4] if news_row[4] else ""
    source_display = NEWS_SOURCES.get(source_key, source_key)
    return {
        "id": news_row[0],
        "title": news_row[1],
        "publish_time": news_row[2],
        "content": news_row[3],
        "content_blocks": content_blocks,
        "source": source_display,
        "direction": selected_analysis["direction"],
        "horizon": selected_analysis["horizon"],
        "reason": selected_analysis["reason"],
        "model": selected_analysis["model"],
        "selected_model": selected_model,
        "factors": selected_factors,
        "analyses": analyses_payload,
    }


@router.get("/factor/{factor_code}/news")
def get_news_by_factor(
    factor_code: str,
    model: Optional[str] = Query(None, description="模型短名，不传则按优先级返回 best"),
):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, category, factor_type FROM factor WHERE code = %s", (factor_code,))
        factor_row = cur.fetchone()
        if not factor_row:
            return {"factor": None, "news": []}

        factor_id = factor_row[0]
        factor_name = factor_row[1] or factor_code
        factor_category = factor_row[2]
        priority_cases = _priority_cases()

        if model:
            cur.execute(
                """
                SELECT DISTINCT n.id, n.title, n.pub_time, DATE(n.pub_time) as publish_date,
                       COALESCE(a.direction, '中性') as direction,
                       COALESCE(a.horizon, '短期') as horizon,
                       nf.direction as factor_direction,
                       nf.model as model
                FROM news_factor nf
                JOIN news n ON nf.news_id = n.id
                LEFT JOIN analysis a ON a.news_id = n.id AND a.model = nf.model
                WHERE nf.factor_id = %s AND nf.model = %s
                ORDER BY DATE(n.pub_time) DESC, n.pub_time DESC
                """,
                (factor_id, model),
            )
        else:
            cur.execute(
                f"""
                SELECT DISTINCT n.id, n.title, n.pub_time, DATE(n.pub_time) as publish_date,
                       COALESCE(a.direction, '中性') as direction,
                       COALESCE(a.horizon, '短期') as horizon,
                       nf.direction as factor_direction,
                       nf.model as model
                FROM news_factor nf
                JOIN news n ON nf.news_id = n.id
                LEFT JOIN analysis a ON a.news_id = n.id AND a.model = nf.model
                WHERE nf.factor_id = %s
                  AND nf.model = (
                      SELECT nf2.model
                      FROM news_factor nf2
                      WHERE nf2.news_id = n.id AND nf2.factor_id = nf.factor_id
                      ORDER BY CASE nf2.model
                          {priority_cases}
                          ELSE 999
                      END
                      LIMIT 1
                  )
                ORDER BY DATE(n.pub_time) DESC, n.pub_time DESC
                """,
                (factor_id,),
            )
        rows = cur.fetchall()

    news_list = [
        {"id": r[0], "title": r[1], "publish_time": r[2], "publish_date": r[3], "direction": r[4], "horizon": r[5], "factor_direction": r[6], "model": r[7]}
        for r in rows
    ]

    return {"factor": {"code": factor_code, "name": factor_name, "category": factor_category}, "news": news_list, "count": len(news_list)}


@router.get("/news/{news_id}/yield")
def get_news_yield_data(
    news_id: int,
    period: str = Query("10年"),
    window_before: int = Query(10),
    window_after: int = Query(10),
):
    data, window_start, window_end = get_yield_window_by_news_id(
        news_id=news_id,
        window_before=window_before,
        window_after=window_after,
        period=period,
    )

    if not data:
        return {"error": "新闻不存在或无法获取收益率数据"}

    news_info = DBOperations.get_news_by_id(news_id)
    publish_date_str = news_info.get("publish_date") if news_info else None

    base_value = None
    relative_changes = []
    if publish_date_str:
        for item in data:
            if item["date"] == publish_date_str:
                base_value = item["value"]
                break
    if base_value is None and data:
        base_value = data[0]["value"]

    if base_value is not None:
        relative_changes = [
            {"date": item["date"], "change": round((item["value"] - base_value) / base_value * 100, 4)}
            for item in data
        ]

    return {
        "news_id": news_id,
        "period": period,
        "publish_date": publish_date_str,
        "data": data,
        "relative_changes": relative_changes,
        "window_before": window_before,
        "window_after": window_after,
        "window_start": window_start,
        "window_end": window_end,
    }


@router.post("/news/{news_id}/analyze")
async def analyze_news(
    news_id: int,
    model_name: Optional[str] = Query(None, description="分析模型短名，如 kingstar / doubao / deepseek"),
):
    result = await process_single_news_analysis(news_id, model_name=model_name)
    if result.get("success"):
        return result
    return {"error": result.get("message", "分析失败")}


@router.post("/internal/pipeline/trigger")
async def trigger_hourly_pipeline(payload: AnalysisTriggerRequest):
    selected_model_name = payload.model_name or get_default_analysis_model_name()

    with get_db_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, status, total_count, processed_count, result_json
                    FROM task_runs
                    WHERE idempotency_key = %s
                      AND task_name = 'analysis_trigger'
                    """,
                    (payload.idempotency_key,),
                )
                existing = cur.fetchone()

                if existing and existing[1] == "completed" and existing[4]:
                    return {
                        "success": True,
                        "idempotency_key": payload.idempotency_key,
                        "status": "completed",
                        "replayed": True,
                        "result": json.loads(existing[4]),
                    }

                if existing and existing[1] == "running":
                    return {
                        "success": True,
                        "idempotency_key": payload.idempotency_key,
                        "status": "running",
                        "accepted": False,
                        "message": "相同幂等键的触发请求正在处理中",
                    }

                payload_json = payload.model_dump()
                if existing:
                    task_run_id = existing[0]
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE task_runs
                            SET status = 'running',
                                task_type = %s,
                                payload_json = %s,
                                total_count = 0,
                                processed_count = 0,
                                result_json = NULL,
                                error_message = NULL,
                                started_at = NOW(),
                                finished_at = NULL,
                                updated_at = NOW()
                            WHERE id = %s
                              AND task_name = 'analysis_trigger'
                            """,
                            (payload.mode, json.dumps(payload_json, ensure_ascii=False), task_run_id),
                        )
                else:
                    task_run_id = start_task_run(
                        conn,
                        task_name="analysis_trigger",
                        task_type=payload.mode,
                        idempotency_key=payload.idempotency_key,
                        payload=payload_json,
                    )
                conn.commit()

            pending_news = DBOperations.get_pending_news_by_mode(
                mode=payload.mode,
                model=selected_model_name,
                limit=payload.limit,
                start_time=payload.start_time,
                end_time=payload.end_time,
                news_ids=payload.news_ids,
            )

            results: List[Dict[str, Any]] = []
            success_count = 0
            for item in pending_news:
                item_result = await process_single_news_analysis(item["news_id"], model_name=selected_model_name)
                results.append(item_result)
                if item_result.get("success"):
                    success_count += 1
                add_task_event(
                    conn,
                    task_run_id=task_run_id,
                    event_type="news_processed",
                    news_id=item["news_id"],
                    status="success" if item_result.get("success") else "failed",
                    message=item_result.get("message", ""),
                    payload=item_result,
                )

            vector_result: Dict[str, Any] = {"skipped": True}
            if payload.run_vector_index:
                add_task_event(
                    conn,
                    task_run_id=task_run_id,
                    event_type="vector_index_started",
                    status="running",
                    message="开始执行新闻向量化与索引落盘",
                    payload={"batch_size": payload.vector_batch_size, "limit": payload.vector_limit},
                )
                vector_result = _run_vector_index_update(batch_size=payload.vector_batch_size, limit=payload.vector_limit)
                add_task_event(
                    conn,
                    task_run_id=task_run_id,
                    event_type="vector_index_completed",
                    status="success",
                    message="新闻向量化与索引落盘完成",
                    payload=vector_result,
                )

            strategy_push_result: Dict[str, Any] = {"skipped": True}
            if payload.run_strategy_push:
                add_task_event(
                    conn,
                    task_run_id=task_run_id,
                    event_type="strategy_push_started",
                    status="running",
                    message="开始生成并推送交易策略建议",
                    payload=None,
                )
                try:
                    from backend.routers.strategy import strategy_push_service

                    strategy_snapshot = await strategy_push_service.trigger_now()
                    strategy_push_result = {
                        "skipped": False,
                        "success": True,
                        "snapshot": strategy_snapshot,
                    }
                    add_task_event(
                        conn,
                        task_run_id=task_run_id,
                        event_type="strategy_push_completed",
                        status="success",
                        message="交易策略建议生成并推送完成",
                        payload={"items": len(strategy_snapshot.get("items", []))},
                    )
                except Exception as strategy_exc:
                    strategy_push_result = {
                        "skipped": False,
                        "success": False,
                        "message": str(strategy_exc),
                    }
                    add_task_event(
                        conn,
                        task_run_id=task_run_id,
                        event_type="strategy_push_failed",
                        status="failed",
                        message="交易策略建议生成或推送失败",
                        payload={"error": str(strategy_exc)},
                    )

            combined_result = {
                "analysis": {
                    "model_name": selected_model_name,
                    "total_count": len(pending_news),
                    "processed_count": success_count,
                    "results": results,
                },
                "vector_index": vector_result,
                "strategy_push": strategy_push_result,
            }

            strategy_push_has_error = payload.run_strategy_push and not combined_result["strategy_push"].get("success", False)
            final_status = (
                "completed"
                if success_count == len(pending_news) and not strategy_push_has_error
                else "completed_with_errors"
            )
            finish_task_run(
                conn,
                task_run_id=task_run_id,
                status=final_status,
                total_count=len(pending_news),
                processed_count=success_count,
                result=combined_result,
            )
            conn.commit()

            return {
                "success": True,
                "idempotency_key": payload.idempotency_key,
                "status": final_status,
                "analysis": combined_result["analysis"],
                "vector_index": combined_result["vector_index"],
                "strategy_push": combined_result["strategy_push"],
            }
        except Exception as exc:
            conn.rollback()
            try:
                with get_db_connection() as retry_conn:
                    with retry_conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE task_runs
                            SET status = 'failed',
                                error_message = %s,
                                finished_at = NOW(),
                                updated_at = NOW()
                            WHERE idempotency_key = %s
                              AND task_name = 'analysis_trigger'
                            """,
                            (str(exc), payload.idempotency_key),
                        )
                    retry_conn.commit()
            except Exception:
                pass
            return {"success": False, "message": f"触发失败: {str(exc)}"}
