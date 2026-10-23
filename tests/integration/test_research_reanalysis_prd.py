"""板块二 P0-3 集成测试：重新分析 + 来源快照不可变（真实 MySQL 测试库）。

未设置 MYSQL_TEST_DATABASE 时自动 skip（见 tests/integration/conftest.py）。
"""

import uuid

import pytest

from backend.repositories.report_generation_repository import ReportGenerationRepository
from backend.repositories.research_report_repository import ResearchReportRepository

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _clean(clean_tables):
    clean_tables("report_figure", "report_generation_tasks", "research_report")


def _insert_analyzed_report(mysql_conn, market_view: str = "bullish") -> int:
    file_hash = uuid.uuid4().hex[:16]
    with mysql_conn.cursor() as cur:
        cur.execute(
            """INSERT INTO research_report
                   (title, file_path, file_hash, status, ai_market_view,
                    ai_summary, full_text, publish_date)
               VALUES (%s, %s, %s, 'analyzed', %s, %s, %s, %s)""",
            (
                "集成测试研报",
                f"pdf/research/original/{file_hash}.pdf",
                file_hash,
                market_view,
                "旧摘要",
                "全文内容",
                "2026-01-02",
            ),
        )
        return cur.lastrowid


class TestSnapshotImmutability:
    def test_synthesis_snapshot_frozen_when_source_reanalyzed(self, mysql_conn):
        """P0-3：源研报重析后，已生成任务的来源快照必须保持生成时版本。"""
        report_id = _insert_analyzed_report(mysql_conn, "bullish")
        gen_repo = ReportGenerationRepository.from_environment()
        sources = gen_repo.load_sources([report_id])
        task = gen_repo.create_task(
            owner_username="tester",
            title="快照测试",
            requirement="需求",
            date_start=None,
            date_end=None,
            sources=sources,
        )

        # 源研报随后被重新分析：观点由 bullish 翻转为 bearish
        with mysql_conn.cursor() as cur:
            cur.execute(
                "UPDATE research_report SET ai_market_view='bearish' WHERE id=%s",
                (report_id,),
            )

        refreshed = gen_repo.get_task("tester", task["id"])
        snapshot = refreshed["source_snapshot_json"]
        assert isinstance(snapshot, list)
        assert snapshot[0]["ai_market_view"] == "bullish"


class TestReanalyzeAnalyzedReport:
    def test_analyzed_report_can_be_claimed_after_reset(self, mysql_conn):
        """P0-3：需提供把 analyzed 重置为可抢占状态的能力，随后 claim 成功。"""
        report_id = _insert_analyzed_report(mysql_conn)
        repo = ResearchReportRepository.from_environment()

        # 现状 claim_for_analysis 仅接受 parsed/failed，analyzed 直接抢不到
        assert repo.claim_for_analysis(report_id) is False

        # 新增能力（命名可调整）：显式重置后允许重新分析
        repo.reset_for_reanalysis(report_id)
        assert repo.claim_for_analysis(report_id) is True
