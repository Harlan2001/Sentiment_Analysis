"""
集成测试冒烟（P1）：验证测试库存在 + 核心 schema 已就位。

本地运行先建库:
    docker compose -f docker-compose.test.yml --profile test up -d
    MYSQL_HOST=127.0.0.1 MYSQL_PORT=33306 MYSQL_USER=root MYSQL_PASSWORD=test \
        MYSQL_TEST_DATABASE=Sentiment_analysis_test \
        uv run pytest tests/integration -m integration -v
"""

import pytest

# migrate 脚本合成出来的表（docs/表结构.md 19 张 + sql/ 增量）。
# 注意: docs/表结构.md 略缺 forecast_report 等生产在用表(P3 需与生产 schema 对齐),
# 故此处只断言 migrate 确实建出的核心表, 防止冒烟被文档缺口误伤。
CORE_TABLES = [
    "news",            # 新闻主表
    "news_content_blocks",
    "analysis",        # 新闻分析结果
    "factor",          # 因子表
    "news_factor",
    "factor_discovery_history",
    "yield_data",      # 收益率数据
    "news_vectors",
    "task_runs",
    "task_events",
    "users",
    "macro_signal_request_log",
    "portfolio_strategy_analysis_cache",
    "research_report",
]


@pytest.mark.integration
def test_test_database_exists(mysql_conn, test_db_name):
    with mysql_conn.cursor() as cur:
        cur.execute(
            "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s",
            (test_db_name,),
        )
        row = cur.fetchone()
    assert row, f"测试库 {test_db_name} 不存在, 请先运行 scripts/migrate_test_db.py"


@pytest.mark.integration
@pytest.mark.parametrize("table", CORE_TABLES)
def test_core_schema_tables(mysql_conn, test_db_name, table):
    with mysql_conn.cursor() as cur:
        cur.execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (test_db_name, table),
        )
        row = cur.fetchone()
    assert row, f"核心表 {table} 不在测试库 {test_db_name} 中, 请重新 migrate"


@pytest.mark.integration
def test_core_table_snapshot_count(mysql_conn, test_db_name):
    """粗粒度防回归: 核心表数量不空（收敛到 docs/表结构.md 实有的主链路表集合）。"""
    with mysql_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME IN "
            "('news','analysis','factor','yield_data','users','task_runs',"
            "'news_vectors','news_factor')",
            (test_db_name,),
        )
        count = cur.fetchone()[0]
    assert count >= 8, f"核心 schema 明显不完整: 仅命中 {count} 张关键表"