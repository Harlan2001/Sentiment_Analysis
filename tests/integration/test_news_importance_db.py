"""集成测试：新闻重要性打分落库链路（S3-2）。

覆盖：
- 多表信号采集 → 纯函数打分 → news_importance_score 落表的完整链路；
- news_factor 复合主键 (news_id, factor_id, model) 下因子数必须 DISTINCT；
- upsert 幂等（重复跑不产生多行、分值不变）；
- 无分析/无因子/无内容块的裸新闻兜底可打分。

需显式设置 MYSQL_TEST_DATABASE（见 tests/integration/conftest.py），否则整文件 skip。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from backend.config.config import RECOMMEND_HOLDING_DAYS
from backend.recommend.scoring import score_news_ids
from backend.repositories.news_importance_repository import NewsImportanceRepository
from tests.integration.helpers import insert_factor, insert_news

pytestmark = pytest.mark.integration

_CLEAN_TABLES = (
    "news_importance_score",
    "news_factor",
    "analysis",
    "news_content_blocks",
    "factor_event_study",
    "factor",
    "news",
)


def _insert_analysis(conn, news_id: int, model: str, direction: str, horizon: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO analysis (news_id, direction, horizon, reason, model, created_at)
               VALUES (%s, %s, %s, %s, %s, NOW())""",
            (news_id, direction, horizon, "集成测试理由", model),
        )


def _insert_factor_link(conn, news_id: int, factor_id: int, model: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO news_factor
                   (news_id, factor_id, direction, driver, model, pub_time, created_at)
               VALUES (%s, %s, 'positive', '集成测试机制', %s, NOW(), NOW())""",
            (news_id, factor_id, model),
        )


def _insert_blocks(conn, news_id: int) -> None:
    with conn.cursor() as cur:
        for order, block_type in enumerate(("image", "table", "heading")):
            cur.execute(
                """INSERT INTO news_content_blocks
                       (news_id, block_type, block_order, content)
                   VALUES (%s, %s, %s, '集成测试内容块')""",
                (news_id, block_type, order),
            )


def _insert_study(conn, factor_code: str, *, hit_rate: float, base: float, sample: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO factor_event_study
                   (factor_code, factor_name, holding_days, sample_size, hit_count,
                    hit_rate, majority_base, period_label)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'all')""",
            (factor_code, "集成测试因子", RECOMMEND_HOLDING_DAYS,
             sample, int(hit_rate * sample), hit_rate, base),
        )


def _score_count(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM news_importance_score")
        return int(cur.fetchone()[0])


class TestNewsImportanceScoring:
    def test_full_pipeline_distinct_and_idempotent(self, mysql_conn, clean_tables):
        clean_tables(*_CLEAN_TABLES)
        factor_id = insert_factor(mysql_conn, "TEST_IMPORTANCE_POL", "测试政策因子", "POLICY")
        news_id = insert_news(mysql_conn, title="央行逆回购加量呵护资金面")

        # 两个模型方向分歧 → agreement 应为 0.5
        _insert_analysis(mysql_conn, news_id, "glm", "positive", "中期(1-6月)")
        _insert_analysis(mysql_conn, news_id, "kimi", "negative", "中期(1-6月)")

        # 同一因子两个模型行 → DISTINCT 因子数必须是 1 而不是 2
        _insert_factor_link(mysql_conn, news_id, factor_id, "glm")
        _insert_factor_link(mysql_conn, news_id, factor_id, "kimi")

        _insert_blocks(mysql_conn, news_id)
        _insert_study(mysql_conn, "TEST_IMPORTANCE_POL", hit_rate=0.7, base=0.5, sample=100)

        written = score_news_ids([news_id])
        assert written == 1
        assert _score_count(mysql_conn) == 1

        repo = NewsImportanceRepository.from_environment()
        row = repo.get_by_news_ids([news_id])[news_id]
        score = float(row["importance_score"])
        assert 0 < score < 100
        assert row["factor_count"] == 1
        assert row["top_category"] == "POLICY"
        assert int(row["s_policy"]) == 1
        # edge = 0.7 - 0.5 = 0.2 → 0.5 + 2*0.2 = 0.9
        assert float(row["s_hit"]) == pytest.approx(0.9, abs=1e-4)
        assert float(row["s_agreement"]) == pytest.approx(0.5, abs=1e-4)
        # 图+表+标题块 → 0.5 + 1.0 + 0.25 = 1.75，除以 1.5 后封顶 1.0
        assert float(row["s_rich"]) == 1.0

        signals = row["signals_json"]
        if isinstance(signals, str):
            signals = json.loads(signals)
        assert set(signals) == {
            "s_direction", "s_agreement", "s_horizon", "s_category", "s_hit",
            "s_nfactor", "s_rich", "s_policy", "s_source",
        }

        # 幂等：再跑一次仍是一行，分值不变
        assert score_news_ids([news_id]) == 1
        assert _score_count(mysql_conn) == 1
        assert float(repo.get_by_news_ids([news_id])[news_id]["importance_score"]) == pytest.approx(score)

    def test_bare_news_gets_fallback_score(self, mysql_conn, clean_tables):
        clean_tables(*_CLEAN_TABLES)
        news_id = insert_news(mysql_conn, title="一条没有任何分析的简讯")

        assert score_news_ids([news_id]) == 1
        row = NewsImportanceRepository.from_environment().get_by_news_ids([news_id])[news_id]
        assert 0 < float(row["importance_score"]) < 100
        assert row["factor_count"] == 0
        assert row["top_category"] is None
        assert float(row["s_direction"]) == 0.2
        assert float(row["s_nfactor"]) == 0.0


class TestRankingQueries:
    """排行榜仓储查询：窗口过滤、final_score 排序、DISTINCT 计数与多空榜。"""

    def test_rankings_window_order_and_counts(self, mysql_conn, clean_tables):
        clean_tables(*_CLEAN_TABLES)
        factor_id = insert_factor(mysql_conn, "TEST_RANK_POL", "排行政策因子", "POLICY")
        now = datetime.now()
        fmt = "%Y-%m-%d %H:%M:%S"
        fresh_pos = insert_news(
            mysql_conn, title="窗口内利多新闻",
            pub_time=(now - timedelta(hours=1)).strftime(fmt),
        )
        fresh_plain = insert_news(
            mysql_conn, title="窗口内无分析新闻",
            pub_time=(now - timedelta(hours=2)).strftime(fmt),
        )
        stale = insert_news(
            mysql_conn, title="窗口外旧闻",
            pub_time=(now - timedelta(days=40)).strftime(fmt),
        )

        # 同一因子关联两条窗口内新闻（其中一条双模型行，计数仍须 DISTINCT）
        _insert_factor_link(mysql_conn, fresh_pos, factor_id, "glm")
        _insert_factor_link(mysql_conn, fresh_pos, factor_id, "kimi")
        _insert_factor_link(mysql_conn, fresh_plain, factor_id, "glm")
        _insert_analysis(mysql_conn, fresh_pos, "glm", "positive", "中期(1-6月)")

        assert score_news_ids([fresh_pos, fresh_plain, stale]) == 3
        repo = NewsImportanceRepository.from_environment()

        top = repo.top_news(days=7)
        top_ids = {int(r["id"]) for r in top}
        assert fresh_pos in top_ids and fresh_plain in top_ids
        assert stale not in top_ids  # 窗口外排除
        finals = [float(r["final_score"]) for r in top]
        assert finals == sorted(finals, reverse=True)  # final_score 降序

        hot = repo.hot_factors(days=7)
        assert hot and int(hot[0]["id"]) == factor_id
        assert int(hot[0]["news_count"]) == 2  # DISTINCT，双模型行不膨胀

        distribution = repo.category_distribution(days=7)
        policy = next(r for r in distribution if r["category"] == "POLICY")
        assert int(policy["news_count"]) == 2
        assert 0 < float(policy["share"]) <= 1

        positive_board = repo.top_news(days=7, direction="positive")
        board_ids = {int(r["id"]) for r in positive_board}
        assert fresh_pos in board_ids
        assert fresh_plain not in board_ids  # 无分析方向不进多空榜
