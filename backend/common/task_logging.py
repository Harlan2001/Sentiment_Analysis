"""Shared task run and task event logging helpers."""

from __future__ import annotations

import json
from typing import Any, Optional


def start_task_run(
    conn: Any,
    task_name: str,
    task_type: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    payload: Optional[Any] = None,
) -> int:
    """Insert a new running task record and return its id."""
    payload_json = (
        json.dumps(payload, ensure_ascii=False) if payload is not None else None
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO task_runs
            (task_name, task_type, idempotency_key, status, payload_json, started_at, created_at, updated_at)
            VALUES (%s, %s, %s, 'running', %s, NOW(), NOW(), NOW())
            """,
            (task_name, task_type, idempotency_key, payload_json),
        )
        return cur.lastrowid


def finish_task_run(
    conn: Any,
    task_run_id: int,
    status: str,
    total_count: int = 0,
    processed_count: int = 0,
    result: Optional[Any] = None,
    error_message: Optional[str] = None,
) -> None:
    """Update a task run with completion status and summary."""
    result_json = json.dumps(result, ensure_ascii=False) if result is not None else None
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE task_runs
            SET status = %s,
                total_count = %s,
                processed_count = %s,
                result_json = %s,
                error_message = %s,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                status,
                total_count,
                processed_count,
                result_json,
                error_message,
                task_run_id,
            ),
        )


def add_task_event(
    conn: Any,
    task_run_id: int,
    event_type: str,
    message: str,
    news_id: Optional[int] = None,
    status: Optional[str] = None,
    payload: Optional[Any] = None,
) -> None:
    """Insert a structured event record for a task run."""
    payload_json = (
        json.dumps(payload, ensure_ascii=False) if payload is not None else None
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO task_events
            (task_run_id, event_type, news_id, status, message, payload_json, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (task_run_id, event_type, news_id, status, message, payload_json),
        )
