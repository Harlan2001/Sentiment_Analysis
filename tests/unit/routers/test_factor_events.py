"""因子事件时序接口：HTTP 契约与只读 SQL 查询测试。"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.config.config import API_PREFIX
from backend.repositories.factor_event_repository import FactorEventRepository
from backend.routers import factors

PATH = f"{API_PREFIX}/factors/events"
REQUIRED_PARAMS = {
    "start_time": "2026-01-01T00:00:00+08:00",
    "end_time": "2026-01-02T00:00:00+08:00",
}
EVENT = {
    "pub_time": "2026-01-01T08:00:00",
    "news_id": 11,
    "factor_code": "RISK_APPETITE",
    "category": "SENTIMENT",
    "factor_type": "conceptual",
    "direction": "positive",
    "model": "glm",
    "title": "测试新闻",
    "driver": "测试驱动",
}


@pytest.fixture
def client():
    from backend.app import app

    return TestClient(app)


@pytest.fixture
def repo_calls(monkeypatch):
    calls = []

    class FakeRepository:
        def list_events(self, **kwargs):
            calls.append(kwargs)
            return {"items": [EVENT], "total": 1}

    monkeypatch.setattr(
        factors.FactorEventRepository,
        "from_environment",
        classmethod(lambda cls: FakeRepository()),
    )
    return calls


def test_default_contract_and_factor_code_cleanup(client, repo_calls):
    response = client.get(
        PATH,
        params={
            **REQUIRED_PARAMS,
            "factor_code": " RISK_APPETITE,UNDERWEIGHT_PRESSURE,RISK_APPETITE,, ",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "items": [EVENT],
            "total": 1,
            "page": 1,
            "page_size": 500,
            "total_pages": 1,
        }
    }
    call = repo_calls[0]
    assert call["factor_codes"] == ["RISK_APPETITE", "UNDERWEIGHT_PRESSURE"]
    assert call["model"] == "glm"
    assert call["start_time"] == datetime(2026, 1, 1, 0, 0)
    assert call["end_time"] == datetime(2026, 1, 2, 0, 0)
    assert call["include_neutral"] is False
    assert call["direction"] is None
    assert call["page"] == 1
    assert call["page_size"] == 500


def test_aware_utc_time_is_converted_to_shanghai_naive(client, repo_calls):
    response = client.get(
        PATH,
        params={"start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-01T01:00:00Z"},
    )

    assert response.status_code == 200
    assert repo_calls[0]["start_time"] == datetime(2026, 1, 1, 8, 0)
    assert repo_calls[0]["end_time"] == datetime(2026, 1, 1, 9, 0)


def test_explicit_model_direction_and_pagination(client, repo_calls):
    response = client.get(
        PATH,
        params={
            **REQUIRED_PARAMS,
            "model": "doubao",
            "direction": " NEGATIVE ",
            "include_neutral": "true",
            "page": 2,
            "page_size": 1,
        },
    )

    assert response.status_code == 200
    call = repo_calls[0]
    assert call["model"] == "doubao"
    assert call["direction"] == "negative"
    assert call["include_neutral"] is True
    assert call["page"] == 2
    assert call["page_size"] == 1


def test_blank_optional_factor_and_direction_mean_unfiltered(client, repo_calls):
    response = client.get(PATH, params={**REQUIRED_PARAMS, "factor_code": "", "direction": ""})

    assert response.status_code == 200
    assert repo_calls[0]["factor_codes"] == []
    assert repo_calls[0]["direction"] is None


@pytest.mark.parametrize("model", ["", "   "])
def test_blank_model_is_rejected(client, repo_calls, model):
    response = client.get(PATH, params={**REQUIRED_PARAMS, "model": model})

    assert response.status_code == 400
    assert "model" in response.json()["detail"]
    assert repo_calls == []


def test_invalid_direction_is_rejected(client, repo_calls):
    response = client.get(PATH, params={**REQUIRED_PARAMS, "direction": "neutral"})

    assert response.status_code == 400
    assert "direction" in response.json()["detail"]
    assert repo_calls == []


def test_reversed_time_range_is_rejected(client, repo_calls):
    response = client.get(
        PATH,
        params={"start_time": "2026-01-03T00:00:00", "end_time": "2026-01-02T00:00:00"},
    )

    assert response.status_code == 400
    assert "start_time" in response.json()["detail"]
    assert repo_calls == []


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"start_time": "2026-01-01T00:00:00"},
        {**REQUIRED_PARAMS, "page": 0},
        {**REQUIRED_PARAMS, "page_size": 501},
        {**REQUIRED_PARAMS, "start_time": "not-a-time"},
    ],
)
def test_fastapi_rejects_missing_or_out_of_range_params(client, repo_calls, params):
    response = client.get(PATH, params=params)

    assert response.status_code == 422
    assert repo_calls == []


class ScriptedCursor:
    def __init__(self, rows, total=None):
        self.rows = rows
        self.total = len(rows) if total is None else total
        self.calls = []
        self._result = None

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params)))
        if normalized.startswith("SELECT COUNT(*)"):
            self._result = {"total": self.total}
        else:
            self._result = self.rows

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._result


@pytest.fixture
def patch_db(monkeypatch):
    def install(rows, total=None):
        cursor = ScriptedCursor(rows, total)
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor

        @contextmanager
        def fake_connection():
            yield conn

        monkeypatch.setattr("backend.repositories.base.get_repo_connection", fake_connection)
        return cursor

    return install


def list_events(**overrides):
    params = {
        "factor_codes": [],
        "start_time": datetime(2026, 1, 1),
        "end_time": datetime(2026, 1, 2),
        "model": "glm",
        "include_neutral": False,
        "direction": None,
        "page": 1,
        "page_size": 500,
    }
    params.update(overrides)
    return params


def test_repository_uses_pub_time_single_model_and_stable_order(patch_db):
    row = {**EVENT, "pub_time": datetime(2026, 1, 1, 8, 0)}
    cursor = patch_db([row])

    result = FactorEventRepository().list_events(**list_events())

    assert result["total"] == 1
    assert result["items"][0]["pub_time"] == "2026-01-01T08:00:00"
    assert len(cursor.calls) == 2
    count_sql, count_params = cursor.calls[0]
    select_sql, select_params = cursor.calls[1]
    assert "nf.model = %s" in count_sql
    assert "nf.pub_time >= %s" in count_sql
    assert "nf.pub_time <= %s" in count_sql
    assert "created_at" not in select_sql
    assert "IN ('positive', 'negative')" in select_sql
    assert "ORDER BY nf.pub_time ASC, nf.news_id ASC, nf.factor_id ASC" in select_sql
    assert count_params == ("glm", datetime(2026, 1, 1), datetime(2026, 1, 2))
    assert select_params == (*count_params, 500, 0)


def test_repository_binds_factor_direction_and_offset(patch_db):
    cursor = patch_db([], total=2)

    FactorEventRepository().list_events(
        **list_events(factor_codes=["A", "B"], direction="positive", page=2, page_size=1)
    )

    count_sql, count_params = cursor.calls[0]
    select_sql, select_params = cursor.calls[1]
    assert "f.code IN (%s,%s)" in count_sql
    assert "LOWER(COALESCE(nf.direction, 'neutral')) = %s" in select_sql
    assert count_params == (
        "glm",
        datetime(2026, 1, 1),
        datetime(2026, 1, 2),
        "A",
        "B",
        "positive",
    )
    assert select_params == (*count_params, 1, 1)


def test_repository_include_neutral_still_excludes_unknown_directions(patch_db):
    cursor = patch_db([])

    result = FactorEventRepository().list_events(**list_events(include_neutral=True))

    select_sql = cursor.calls[1][0]
    assert "IN ('positive', 'negative', 'neutral')" in select_sql
    assert result == {"items": [], "total": 0}
