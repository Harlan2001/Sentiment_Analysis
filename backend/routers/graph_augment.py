from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel

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


class SaveGraphAugmentRequest(BaseModel):
    news_id: int
    run_id: str
    status: str
    stage: Optional[str] = None
    result_json: dict
    extract_json: dict


@router.post("/save")
def save_graph_augment_result(request: SaveGraphAugmentRequest = Body(...)):
    result_json_str = json.dumps(request.result_json)
    extract_json_str = json.dumps(request.extract_json)

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM graph_augment_jobs WHERE run_id = %s", (request.run_id,)
        )
        existing = cur.fetchone()

        if existing:
            cur.execute(
                """
                UPDATE graph_augment_jobs
                SET status = %s, stage = %s, result_json = %s, extract_json = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (
                    request.status,
                    request.stage,
                    result_json_str,
                    extract_json_str,
                    existing[0],
                ),
            )
            conn.commit()
            return {"success": True, "action": "updated", "id": existing[0]}

        cur.execute(
            """
            INSERT INTO graph_augment_jobs (news_id, run_id, status, stage, result_json, extract_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                request.news_id,
                request.run_id,
                request.status,
                request.stage,
                result_json_str,
                extract_json_str,
            ),
        )
        conn.commit()
        return {"success": True, "action": "inserted"}
