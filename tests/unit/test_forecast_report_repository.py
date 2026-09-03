"""forecast_report 仓储单测：假游标注入，不连真实数据库。

覆盖：最新日期空/非空、prediction JSON 解析与容错、全量报告读取。
"""

import json
from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock

from backend.repositories.forecast_report_repository import (
    ForecastReportRepository,
    _parse_prediction,
)


def _patch_repo_connection(monkeypatch, row):
    """把 base.get_repo_connection 替换为返回固定行的假连接。"""
    cursor = MagicMock()
    cursor.fetchone.return_value = row
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = cursor

    @contextmanager
    def _fake(*args, **kwargs):
        yield mock_conn

    monkeypatch.setattr("backend.repositories.base.get_repo_connection", _fake)
    return cursor


# ---- _parse_prediction 纯函数 ----

def test_parse_prediction_json_string_to_dict():
    assert _parse_prediction('{"a": 1}') == {"a": 1}


def test_parse_prediction_invalid_json_keeps_string():
    value = "报告摘要纯文本"
    assert _parse_prediction(value) == value


def test_parse_prediction_non_string_passthrough():
    assert _parse_prediction({"a": 1}) == {"a": 1}
    assert _parse_prediction(None) is None


# ---- get_latest_trade_date ----

def test_get_latest_trade_date_returns_max_date(monkeypatch):
    _patch_repo_connection(monkeypatch, {"latest_date": date(2026, 9, 1)})
    assert ForecastReportRepository().get_latest_trade_date() == date(2026, 9, 1)


def test_get_latest_trade_date_empty_table_returns_none(monkeypatch):
    _patch_repo_connection(monkeypatch, None)
    assert ForecastReportRepository().get_latest_trade_date() is None


# ---- get_prediction ----

def test_get_prediction_parses_json(monkeypatch):
    _patch_repo_connection(monkeypatch, {"prediction": json.dumps({"报告摘要": "略"})})
    assert ForecastReportRepository().get_prediction(date(2026, 9, 1)) == {"报告摘要": "略"}


def test_get_prediction_no_row_returns_none(monkeypatch):
    _patch_repo_connection(monkeypatch, None)
    assert ForecastReportRepository().get_prediction(date(2026, 9, 1)) is None


def test_get_prediction_non_dict_prediction_returns_none(monkeypatch):
    _patch_repo_connection(monkeypatch, {"prediction": "不是对象"})
    assert ForecastReportRepository().get_prediction(date(2026, 9, 1)) is None


# ---- get_full_report ----

def test_get_full_report_parses_prediction_and_keeps_fields(monkeypatch):
    row = {
        "trade_date": date(2026, 9, 1),
        "model_name": "glm",
        "prompt_version": "v2.3",
        "prediction": json.dumps({"市场概览": "略"}),
        "created_at": None,
    }
    _patch_repo_connection(monkeypatch, row)
    report = ForecastReportRepository().get_full_report(date(2026, 9, 1))
    assert report["prediction"] == {"市场概览": "略"}
    assert report["model_name"] == "glm"
    assert report["trade_date"] == date(2026, 9, 1)


def test_get_full_report_no_row_returns_none(monkeypatch):
    _patch_repo_connection(monkeypatch, None)
    assert ForecastReportRepository().get_full_report(date(2026, 9, 1)) is None
