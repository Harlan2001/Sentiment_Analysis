"""四类 AI 任务在真实 MySQL 上的队列、租约、日志与权限验收。"""

from __future__ import annotations

import uuid
from datetime import date

import pymysql
import pytest

from backend.repositories.ai_task_repository import AITaskRepository
from backend.repositories.base import ExecutionLeaseError
from backend.repositories.news_summary_repository import DailyNewsSummaryRepository
from backend.repositories.policy_document_repository import PolicyDocumentRepository
from backend.repositories.research_report_repository import ResearchReportRepository
from backend.task_execution.queue import AITaskQueue, TaskNotFoundError

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _clean(mysql_conn, clean_tables):
    clean_tables(
        "task_events",
        "policy_analysis",
        "policy_document",
        "report_generation_tasks",
        "daily_news_summary_tasks",
        "report_figure",
        "research_report",
        "task_runs",
    )


def _generation(mysql_conn, owner="alice", status="queued"):
    task_id = str(uuid.uuid4())
    with mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute(
            """INSERT INTO report_generation_tasks
               (id,owner_username,title,requirement,report_ids_json,source_snapshot_json,
                status,queued_at,stage)
               VALUES (%s,%s,'测试综合研报','要求','[]','[]',%s,NOW(6),'queued')""",
            (task_id, owner, status),
        )
    return task_id


def _research(mysql_conn, owner="alice"):
    with mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute(
            """INSERT INTO research_report
               (title,file_path,file_hash,full_text,status,uploaded_by,queued_at,stage)
               VALUES ('测试研报','test.pdf',%s,'真实正文','queued',%s,NOW(6),'queued')""",
            (uuid.uuid4().hex, owner),
        )
        return int(cursor.lastrowid)


def _policy(repository, owner="alice", title="货币政策测试"):
    return repository.create_document(
        owner,
        file_hash=uuid.uuid4().hex,
        title=title,
        original_filename="policy.pdf",
        issuer="测试机关",
        document_no=None,
        publish_date=date(2026, 1, 1),
        full_text="降准释放长期流动性，支持实体经济发展。" * 20,
        page_count=2,
        focus_title="长端利率影响",
        analysis_requirement="重点关注收益率下行传导",
    )


def test_generation_competition_retry_stale_lease_and_events(mysql_conn):
    queue = AITaskQueue.from_environment()
    task_id = _generation(mysql_conn)
    first = queue.claim("report_generation", task_id, lease_seconds=180)
    assert first is not None
    assert queue.claim("report_generation", task_id, lease_seconds=180) is None
    queue.update_stage(first, "generating", "正在生成")
    assert queue.fail(first, "模拟失败")
    queue.retry("report_generation", task_id, "alice")
    with pytest.raises(TaskNotFoundError):
        queue.retry("report_generation", task_id, "bob")
    second = queue.claim("report_generation", task_id, lease_seconds=180)
    assert second is not None
    assert not queue.fail(first, "旧 worker 不得覆盖")

    detail = AITaskRepository.from_environment().get_execution_detail(
        "alice", "report_generation", task_id
    )
    assert detail["task"]["status"] == "running"
    assert detail["execution"]["id"] == second.run_id
    assert any(item["event_type"] == "queued" for item in detail["items"])
    with mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT status,retry_count FROM report_generation_tasks WHERE id=%s", (task_id,))
        row = cursor.fetchone()
    assert row == {"status": "running", "retry_count": 1}
    queue.fail(second, "清理")


def test_recovery_preserves_queued_and_marks_only_interrupted(mysql_conn):
    queue = AITaskQueue.from_environment()
    queued = _generation(mysql_conn)
    interrupted = _generation(mysql_conn, status="running")
    with mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute(
            """UPDATE report_generation_tasks
                  SET lease_token='dead',lease_expires_at=DATE_SUB(NOW(6),INTERVAL 1 SECOND)
                WHERE id=%s""",
            (interrupted,),
        )
    assert queue.recover_interrupted() == 1
    with mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT id,status FROM report_generation_tasks ORDER BY created_at,id")
        statuses = {row["id"]: row["status"] for row in cursor.fetchall()}
    assert statuses[queued] == "queued"
    assert statuses[interrupted] == "failed"


def test_research_success_and_stale_result_protection(mysql_conn):
    queue = AITaskQueue.from_environment()
    repository = ResearchReportRepository.from_environment()
    report_id = _research(mysql_conn)
    handle = queue.claim("research_report", report_id, lease_seconds=180)
    assert handle is not None
    repository.finish_analysis(
        report_id,
        model_name="glm",
        parsed={"summary": "真实结果", "market_view": "neutral"},
        raw="{}",
        deep_markdown="# 分析",
        lease_token=handle.lease_token,
        run_id=handle.run_id,
    )
    with pytest.raises(ExecutionLeaseError):
        repository.finish_analysis(
            report_id,
            model_name="glm",
            parsed={"summary": "旧结果覆盖"},
            raw="{}",
            lease_token=handle.lease_token,
            run_id=handle.run_id,
        )
    with mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT status,ai_summary FROM research_report WHERE id=%s", (report_id,))
        row = cursor.fetchone()
        cursor.execute("SELECT status FROM task_runs WHERE id=%s", (handle.run_id,))
        run = cursor.fetchone()
    assert row == {"status": "analyzed", "ai_summary": "真实结果"}
    assert run["status"] == "succeeded"


def test_policy_full_stats_filters_and_transactional_success(mysql_conn):
    queue = AITaskQueue.from_environment()
    repository = PolicyDocumentRepository.from_environment()
    document_id = _policy(repository)
    _policy(repository, title="另一个文件")
    assert queue.enqueue("policy_document", document_id, allowed_statuses=("uploaded",))
    handle = queue.claim("policy_document", document_id, lease_seconds=180)
    assert handle is not None
    repository.save_analysis(
        document_id,
        "alice",
        {
            "summary": "政策摘要",
            "domains": ["货币政策"],
            "impact_direction": "bullish",
            "impact_reason": "流动性改善",
            "evidence": [{"text": "降准", "inference": "利多"}],
            "key_points": ["降准"],
            "model_name": "glm",
        },
        lease_token=handle.lease_token,
        run_id=handle.run_id,
    )
    result = repository.list_documents("alice", limit=1)
    assert result["total"] == 2
    assert result["stats"] == {"total": 2, "analyzed": 1, "bullish": 1, "bearish": 0, "neutral": 0}
    assert len(result["items"]) == 1
    filtered = repository.list_documents("alice", keyword="货币政策", direction="bullish")
    assert filtered["total"] == 1
    assert filtered["items"][0]["focus_title"] == "长端利率影响"
    with mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT status FROM task_runs WHERE id=%s", (handle.run_id,))
        assert cursor.fetchone()["status"] == "succeeded"


def test_daily_news_success_empty_terminal_and_unified_filters(mysql_conn):
    queue = AITaskQueue.from_environment()
    repository = DailyNewsSummaryRepository.from_environment()
    task = repository.create_task("alice", date(2026, 1, 1), date(2026, 1, 1), [], "流动性")
    handle = queue.claim("daily_news", task["id"], lease_seconds=180)
    assert handle is not None
    repository.complete_task(
        "alice",
        int(task["id"]),
        status="empty",
        news_count=0,
        source_stats={},
        summary="无新闻",
        references=[],
        lease_token=handle.lease_token,
        run_id=handle.run_id,
    )
    tasks = AITaskRepository.from_environment().list_tasks(
        "alice", task_type="daily_news", status="empty"
    )
    assert tasks["total"] == 1
    assert tasks["items"][0]["result_url"] == f"/computer/news/{task['id']}"
    with mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT status FROM task_runs WHERE id=%s", (handle.run_id,))
        assert cursor.fetchone()["status"] == "succeeded"
