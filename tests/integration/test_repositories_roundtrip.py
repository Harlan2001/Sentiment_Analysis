"""集成测试：数据库层基本读写的 roundtrip（验证迁移出的 schema 可写可读）。"""

import pytest

from backend.common.database import execute_query, execute_update
from tests.integration.helpers import insert_news, insert_user

pytestmark = pytest.mark.integration


class TestDatabaseRoundtrip:
    def test_users_roundtrip(self, mysql_conn, clean_tables):
        clean_tables("users")
        username = "roundtrip_user_1"
        insert_user(mysql_conn, username)

        row = execute_query(
            "SELECT username, password FROM users WHERE username=%s",
            (username,),
            one=True,
        )
        assert row and row[0] == username

        execute_update("DELETE FROM users WHERE username=%s", (username,))
        gone = execute_query(
            "SELECT id FROM users WHERE username=%s", (username,), one=True
        )
        assert not gone

    def test_news_roundtrip(self, mysql_conn, clean_tables):
        clean_tables("news")
        title = "roundtrip-集成-新闻"
        news_id = insert_news(mysql_conn, title=title)

        row = execute_query("SELECT title FROM news WHERE id=%s", (news_id,), one=True)
        assert row and row[0] == title

        execute_update("DELETE FROM news WHERE id=%s", (news_id,))
        gone = execute_query("SELECT id FROM news WHERE id=%s", (news_id,), one=True)
        assert not gone

    def test_yield_data_roundtrip(self, mysql_conn, clean_tables):
        clean_tables("yield_data")
        with mysql_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO yield_data (date, period, value) VALUES (%s, %s, %s)",
                ("2026-09-01", "10Y", 2.1000),
            )
        row = execute_query(
            "SELECT value FROM yield_data WHERE date=%s AND period=%s",
            ("2026-09-01", "10Y"),
            one=True,
        )
        assert row and abs(float(row[0]) - 2.1) < 1e-6
        execute_update(
            "DELETE FROM yield_data WHERE date=%s AND period=%s",
            ("2026-09-01", "10Y"),
        )