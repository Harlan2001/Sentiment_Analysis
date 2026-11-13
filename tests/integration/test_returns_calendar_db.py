"""真实 MySQL 下的收益日历查询契约；仅新增并清理本用例的隔离数据。"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import pytest

from backend.routers.returns import returns_calendar
from tests.integration.helpers import insert_factor, insert_news

pytestmark = pytest.mark.integration


def test_returns_calendar_real_sql_enrichment_and_deduplication(mysql_conn):
    # 随机远期日期避免读取/清空其他集成用例数据，也模拟跨自然日取上一有效行情。
    base_day = date(2099, 1, 10) + timedelta(days=uuid.uuid4().int % 2500)
    previous_day = base_day - timedelta(days=3)
    day_string = base_day.isoformat()
    suffix = uuid.uuid4().hex
    factor_id = insert_factor(
        mysql_conn, f"TEST_RETURNS_{suffix}", "收益日历隔离因子", "POLICY"
    )
    news_ids = []
    try:
        first = insert_news(mysql_conn, title="高分利空", pub_time=f"{day_string} 09:00:00")
        second = insert_news(mysql_conn, title="低分利多", pub_time=f"{day_string} 10:00:00")
        unscored = insert_news(mysql_conn, title="未评分中性", pub_time=f"{day_string} 11:00:00")
        news_ids = [first, second, unscored]

        with mysql_conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO analysis (news_id, direction, horizon, reason, model, created_at)
                   VALUES (%s, %s, '中期', '集成测试理由', %s, NOW())""",
                [
                    (first, "negative", "glm"),
                    (second, "negative", "kimi"),
                    (second, "positive", "glm"),  # 最佳模型应选 glm，而非后写的 kimi
                    (unscored, "neutral", "glm"),
                ],
            )
            cur.executemany(
                """INSERT INTO news_factor
                       (news_id, factor_id, direction, driver, model, pub_time, created_at)
                   VALUES (%s, %s, 'negative', '集成测试机制', %s, %s, NOW())""",
                [
                    (first, factor_id, "glm", f"{day_string} 09:00:00"),
                    (first, factor_id, "kimi", f"{day_string} 09:00:00"),
                    (second, factor_id, "glm", f"{day_string} 10:00:00"),
                ],
            )
            cur.executemany(
                """INSERT INTO news_importance_score
                       (news_id, score_version, importance_score, signals_json, top_category)
                   VALUES (%s, 'v1', %s, %s, 'POLICY')""",
                [
                    (first, 90, json.dumps({"s_hit": 0.7})),
                    (second, 70, json.dumps({"s_hit": 0.5})),
                ],
            )
            cur.executemany(
                "INSERT INTO yield_data (date, period, value) VALUES (%s, '10Y', %s)",
                [(previous_day, 1.8), (base_day, 1.82)],
            )

        payload = returns_calendar(start=day_string, end=day_string)["data"]

        items = [
            item for item in payload["news_by_date"][day_string]
            if item["id"] in news_ids
        ]
        assert [item["id"] for item in items] == [first, second, unscored]
        assert items[0]["market_alignment"] == "supporting"
        assert items[0]["score_signals"] == {"s_hit": 0.7}
        assert len(items[0]["factors"]) == 1
        assert items[1]["direction"] == "利多"
        assert items[1]["market_alignment"] == "opposing"
        assert items[2]["importance_score"] is None
        assert items[2]["market_alignment"] == "neutral"

        day = next(item for item in payload["days"] if item["date"] == day_string)
        factor = next(item for item in day["active_factors"] if item["id"] == factor_id)
        assert factor["news_count"] == 2
        point = payload["yields_by_date"][day_string]["10Y"]
        assert point["previous_date"] == previous_day.isoformat()
        assert point["diff_bp"] == 2.0
    finally:
        # 只删除本用例创建的行；不对共享测试表执行 TRUNCATE。
        with mysql_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM yield_data WHERE period='10Y' AND date IN (%s, %s)",
                (previous_day, base_day),
            )
            if news_ids:
                placeholders = ",".join(["%s"] * len(news_ids))
                for table in ("news_importance_score", "news_factor", "analysis"):
                    cur.execute(
                        f"DELETE FROM {table} WHERE news_id IN ({placeholders})",
                        news_ids,
                    )
                cur.execute(f"DELETE FROM news WHERE id IN ({placeholders})", news_ids)
            cur.execute("DELETE FROM factor WHERE id=%s", (factor_id,))
