"""集成测试：macro_signal 对真实测试库的 presence/directional 信号计算。"""

from datetime import datetime

import pytest

from backend.macrosignal.macro_signal import (
    SIGNAL_DIRECTIONAL,
    SIGNAL_PRESENCE,
    get_macro_signal,
)
from tests.integration.helpers import insert_factor, insert_news

START = datetime(2026, 9, 1)
END = datetime(2026, 9, 1, 23, 59, 59)
PUB = "2026-09-01 10:00:00"


@pytest.fixture(autouse=True)
def _clean(clean_tables):
    clean_tables("news_factor", "news", "factor")


def _link(mysql_conn, news_id: int, factor_id: int, direction: str = "positive"):
    with mysql_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO news_factor (news_id, factor_id, direction, model, pub_time) "
            "VALUES (%s,%s,%s,%s,%s)",
            (news_id, factor_id, direction, "integration-test", PUB),
        )


class TestMacroSignalDb:
    def test_presence_one_for_matched_news(self, mysql_conn):
        factor_id = insert_factor(mysql_conn, "RATE", "利率")
        news_id = insert_news(mysql_conn, pub_time=PUB)
        _link(mysql_conn, news_id, factor_id, "positive")

        result = get_macro_signal(["RATE"], START, END, SIGNAL_PRESENCE)
        assert result[0]["factor_code"] == "RATE"
        assert result[0]["signal_value"] == 1
        assert result[0]["news_count"] == 1
        assert result[0]["hit_news_ids"] == [news_id]

    def test_presence_zero_without_news(self, mysql_conn):
        insert_factor(mysql_conn, "EMPTY", "空因子")
        insert_factor(mysql_conn, "RATE", "利率")
        result = get_macro_signal(["RATE"], START, END, SIGNAL_PRESENCE)
        assert result[0]["signal_value"] == 0
        assert result[0]["news_count"] == 0

    def test_unknown_factor_returns_error(self, mysql_conn):
        result = get_macro_signal(
            ["NOPE"], START, END, SIGNAL_PRESENCE
        )
        assert result[0] == {"factor_code": "NOPE", "error": "not found"}

    def test_directional_positive_news(self, mysql_conn):
        factor_id = insert_factor(mysql_conn, "RATE", "利率")
        news_id = insert_news(mysql_conn, pub_time=PUB)
        _link(mysql_conn, news_id, factor_id, "positive")

        result = get_macro_signal(["RATE"], START, END, SIGNAL_DIRECTIONAL)
        assert result[0]["signal_value"] == 1

    def test_directional_negative_news(self, mysql_conn):
        factor_id = insert_factor(mysql_conn, "RATE", "利率")
        news_id = insert_news(mysql_conn, pub_time=PUB)
        _link(mysql_conn, news_id, factor_id, "negative")

        result = get_macro_signal(["RATE"], START, END, SIGNAL_DIRECTIONAL)
        assert result[0]["signal_value"] == -1
pytestmark = pytest.mark.integration
