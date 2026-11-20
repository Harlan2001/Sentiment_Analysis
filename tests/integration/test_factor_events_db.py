"""因子事件时序接口的真实测试库验证；未显式配置测试库时自动 skip。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config.config import API_PREFIX
from tests.integration.helpers import insert_factor, insert_news

pytestmark = pytest.mark.integration

PATH = f"{API_PREFIX}/factors/events"
START = "2026-01-01 00:00:00"
END = "2026-01-02 00:00:00"
BASE_PARAMS = {
    "start_time": "2026-01-01T00:00:00",
    "end_time": "2026-01-02T00:00:00",
}


@pytest.fixture(autouse=True)
def _clean(clean_tables):
    clean_tables("news_factor", "news", "factor")


@pytest.fixture
def client():
    return TestClient(app)


def _set_conceptual(conn, factor_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE factor SET factor_type = 'conceptual' WHERE id = %s", (factor_id,))


def _link(
    conn,
    news_id: int,
    factor_id: int,
    *,
    direction: str,
    model: str = "glm",
    pub_time: str,
    created_at: str = "2026-01-03 00:00:00",
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO news_factor
                   (news_id, factor_id, direction, driver, model, pub_time, created_at)
               VALUES (%s, %s, %s, '集成测试驱动', %s, %s, %s)""",
            (news_id, factor_id, direction, model, pub_time, created_at),
        )


def _get(client, **params):
    response = client.get(PATH, params={**BASE_PARAMS, **params})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _keys(items):
    return [(item["news_id"], item["factor_code"]) for item in items]


def test_event_stream_model_filters_boundaries_and_stable_pages(mysql_conn, client):
    factor_a = insert_factor(mysql_conn, "TEST_EVENT_A", "事件因子A", "SENTIMENT")
    factor_b = insert_factor(mysql_conn, "TEST_EVENT_B", "事件因子B", "MACRO")
    _set_conceptual(mysql_conn, factor_a)
    _set_conceptual(mysql_conn, factor_b)

    first = insert_news(mysql_conn, title="闭区间起点", pub_time=START)
    second = insert_news(mysql_conn, title="同一秒第二条新闻", pub_time=START)
    neutral = insert_news(mysql_conn, title="中性事件", pub_time="2026-01-01 12:00:00")
    last = insert_news(mysql_conn, title="闭区间终点", pub_time="2025-12-31 23:59:59")
    outside = insert_news(mysql_conn, title="窗口外事件", pub_time="2026-01-02 00:00:01")
    created_at_only = insert_news(mysql_conn, title="created_at 不可替代事件时间", pub_time=START)

    _link(mysql_conn, first, factor_a, direction="positive", pub_time=START)
    _link(mysql_conn, second, factor_a, direction="NEGATIVE", pub_time=START)
    _link(mysql_conn, second, factor_b, direction="positive", pub_time=START)
    _link(mysql_conn, neutral, factor_a, direction="neutral", pub_time="2026-01-01 12:00:00")
    # nf.pub_time 是终点，虽然 news.pub_time 在窗口外，仍应纳入。
    _link(mysql_conn, last, factor_b, direction="positive", pub_time=END)
    _link(mysql_conn, outside, factor_a, direction="positive", pub_time="2026-01-02 00:00:01")
    _link(mysql_conn, neutral, factor_a, direction="positive", model="doubao", pub_time=START)
    # created_at 落在窗口内也不能替代窗口外的 nf.pub_time。
    _link(
        mysql_conn,
        created_at_only,
        factor_a,
        direction="positive",
        pub_time="2026-01-03 00:00:00",
        created_at=START,
    )

    page1 = _get(client, page=1, page_size=2)
    page2 = _get(client, page=2, page_size=2)

    assert page1["total"] == page2["total"] == 4
    assert page1["total_pages"] == page2["total_pages"] == 2
    assert _keys(page1["items"]) == [(first, "TEST_EVENT_A"), (second, "TEST_EVENT_A")]
    assert _keys(page2["items"]) == [(second, "TEST_EVENT_B"), (last, "TEST_EVENT_B")]
    assert len(set(_keys(page1["items"] + page2["items"]))) == 4
    assert page1["items"][0]["pub_time"] == "2026-01-01T00:00:00"
    assert page2["items"][-1]["pub_time"] == "2026-01-02T00:00:00"
    assert all(item["model"] == "glm" for item in page1["items"] + page2["items"])
    assert all(item["factor_type"] == "conceptual" for item in page1["items"])

    assert _get(client, page=3, page_size=2)["items"] == []
    assert _get(client, include_neutral="true")["total"] == 5
    assert _get(client, direction="positive")["total"] == 3
    assert _get(client, direction="negative")["total"] == 1
    assert _get(client, factor_code="TEST_EVENT_A")["total"] == 2
    assert _get(client, factor_code="NOT_A_FACTOR")["total"] == 0
    doubao = _get(client, model="doubao")
    assert doubao["total"] == 1
    assert doubao["items"][0]["news_id"] == neutral
