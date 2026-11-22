"""统一 AI 队列的原子竞争、恢复语义与有界调度测试。"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager

import pytest

from backend.repositories.base import ExecutionLeaseError
from backend.repositories.research_report_repository import ResearchReportRepository
from backend.task_execution.dispatcher import AITaskDispatcher
from backend.task_execution.queue import AITaskQueue, TaskHandle


class FakeCursor:
    def __init__(self, *, claim_results: list[int] | None = None, final_update_result: int = 1):
        self.calls: list[tuple[str, tuple]] = []
        self.claim_results = list(claim_results or [])
        self.final_update_result = final_update_result
        self.rowcount = 1
        self.lastrowid = 91
        self._row: dict | None = None
        self._rows: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params)))
        self.rowcount = 1
        self._row = None
        self._rows = []
        if "SET status = %s, stage = 'loading'" in normalized:
            self.rowcount = self.claim_results.pop(0) if self.claim_results else 1
        elif normalized.startswith("SELECT") and "active_run_id" in normalized and "owner_username" in normalized:
            self._row = {"owner_username": "alice", "active_run_id": None}
        elif normalized.startswith("SELECT requested_model"):
            self._row = {"requested_model": "provider/glm"}
        elif normalized.startswith("SELECT status FROM"):
            self._row = {"status": "failed"}
        elif normalized.startswith("SELECT id, active_run_id"):
            self._rows = []
        elif normalized.startswith("UPDATE research_report SET ai_summary"):
            self.rowcount = self.final_update_result
        return self.rowcount

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeQueue(AITaskQueue):
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def _connection(self):
        yield self.connection


class FakeResearchRepository(ResearchReportRepository):
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def _connection(self):
        yield self.connection


def test_enqueue_persists_requested_model_in_correct_parameter_order():
    cursor = FakeCursor()
    queue = FakeQueue(FakeConnection(cursor))
    assert queue.enqueue(
        "research_report", 7, allowed_statuses=("parsed", "failed"), requested_model="provider/glm"
    )
    sql, params = cursor.calls[0]
    assert "requested_model = %s" in sql
    assert params == ("queued", "provider/glm", 7, "parsed", "failed")


def test_only_one_worker_can_claim_and_execution_log_is_linked():
    cursor = FakeCursor(claim_results=[1, 0])
    queue = FakeQueue(FakeConnection(cursor))
    handle = queue.claim("research_report", 7, lease_seconds=180)
    assert handle is not None
    assert handle.owner_username == "alice"
    assert handle.run_id == 91
    assert handle.requested_model == "provider/glm"
    assert queue.claim("research_report", 7, lease_seconds=180) is None
    assert any("INSERT INTO task_runs" in sql for sql, _ in cursor.calls)
    assert any("INSERT INTO task_events" in sql for sql, _ in cursor.calls)


def test_recovery_only_selects_running_with_missing_or_expired_lease():
    cursor = FakeCursor()
    queue = FakeQueue(FakeConnection(cursor))
    assert queue.recover_interrupted() == 0
    selects = [sql for sql, _ in cursor.calls if sql.startswith("SELECT id, active_run_id")]
    assert len(selects) == 4
    assert all("lease_token IS NULL OR lease_expires_at <= NOW(6)" in sql for sql in selects)
    assert not any("SET status = 'queued'" in sql for sql, _ in cursor.calls)


def test_stale_research_lease_rolls_back_instead_of_overwriting_result():
    connection = FakeConnection(FakeCursor(final_update_result=0))
    repository = FakeResearchRepository(connection)
    with pytest.raises(ExecutionLeaseError):
        repository.finish_analysis(
            7,
            model_name="glm",
            parsed={"summary": "新结果"},
            raw="{}",
            lease_token="stale-token",
            run_id=91,
        )
    assert connection.rollbacks == 1
    assert connection.commits == 0


class BoundedQueue:
    def __init__(self):
        self.claims: list[tuple[str, str]] = []

    def recover_interrupted(self):
        return 0

    def list_queued(self):
        return [("research_report", str(index)) for index in range(500)]

    def claim(self, task_type, domain_id, *, lease_seconds):
        self.claims.append((task_type, domain_id))
        return TaskHandle(task_type, domain_id, "alice", domain_id, len(self.claims))


class ControlledDispatcher(AITaskDispatcher):
    def __init__(self, queue):
        super().__init__(queue=queue, max_workers=3, domain_max_workers=3, poll_seconds=60)
        self.full = asyncio.Event()

    async def _execute(self, handle):
        if self.active_count >= 3:
            self.full.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            return


@pytest.mark.asyncio
async def test_500_queued_reports_do_not_create_500_workers():
    queue = BoundedQueue()
    dispatcher = ControlledDispatcher(queue)
    await dispatcher.start()
    await asyncio.wait_for(queue_full(dispatcher), timeout=1)
    assert len(queue.claims) == 3
    assert dispatcher.active_count == 3
    await dispatcher.stop()


async def queue_full(dispatcher):
    while dispatcher.active_count < 3:
        await asyncio.sleep(0.001)
