from __future__ import annotations

import json

from fastapi import APIRouter

from backend.common.database import get_db_connection
from backend.config.config import API_PREFIX

router = APIRouter(prefix=f"{API_PREFIX}/graph-augment", tags=["graph-augment"])


@router.get("/job-by-news/{news_id}")
def get_graph_augment_by_news(news_id: int):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, news_id, run_id, status, stage, result_json,
                   extract_json, created_at, updated_at
            FROM graph_augment_jobs
            WHERE news_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (news_id,),
        )
        result = cur.fetchone()

    if not result:
        return {"job": None}

    return {
        "job": {
            "id": result[0],
            "news_id": result[1],
            "run_id": result[2],
            "status": result[3],
            "stage": result[4],
            "result_json": json.loads(result[5]) if result[5] else None,
            "extract_json": json.loads(result[6]) if result[6] else None,
            "created_at": result[7].isoformat() if result[7] else None,
            "updated_at": result[8].isoformat() if result[8] else None,
        }
    }