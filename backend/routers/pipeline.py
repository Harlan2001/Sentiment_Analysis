from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from backend.analysis.analyzer import process_single_news_analysis
from backend.config.config import API_PREFIX, MYSQL_CONFIG, get_default_analysis_model_name
from backend.common.database import DatabaseConfig, get_db_connection, init_database
from backend.common.db_operations import DBOperations
from backend.common.task_logging import add_task_event, finish_task_run, start_task_run
from backend.common.vector_store import get_faiss_store

router = APIRouter(prefix=API_PREFIX, tags=["pipeline"])


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
