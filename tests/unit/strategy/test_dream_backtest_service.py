"""160055 独立回测封装单测（不触网）：参数构造、结果序列化与编排。

协议消息用最小 duck-type 假对象代替，proto 编译只在真实联调时需要。
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from backend.integrations.dream import service as svc
from backend.integrations.dream.client import EI_BACKTEST


class _FakeParameter:
    def __init__(self, name="", value="", type=0):
        self.name = name
        self.value = value
        self.type = type


class _FakeBacktestRequest:
    def __init__(self, **kwargs):
        # protobuf 未显式传值的标量字段默认是空串/0，这里复刻该语义。
        self.template_id = kwargs.get("template_id", "")
        self.version_id = kwargs.get("version_id", "")
        self.code = kwargs.get("code", "")
        self.params = kwargs.get("params", [])
        self.begin_timestamp = kwargs.get("begin_timestamp", 0)
        self.end_timestamp = kwargs.get("end_timestamp", 0)
        self.initial_capital = kwargs.get("initial_capital", 0.0)
        self.commission_ratio = kwargs.get("commission_ratio", 0.0)


class _FakePb2:
    AiStrategyV2TemplateParameter = _FakeParameter
    BacktestAiStrategyV2TemplateRequest = _FakeBacktestRequest
    BacktestAiStrategyV2TemplateResponse = object


_PB2 = _FakePb2()


class TestBuildBacktestParameters:
    def test_empty_returns_empty_list(self):
        assert svc._build_backtest_parameters(_PB2, None) == []
        assert svc._build_backtest_parameters(_PB2, {}) == []

    def test_type_inference_and_rendering(self):
        params = svc._build_backtest_parameters(
            _PB2,
            {
                "interval": "1d",
                "capital": 10000000,
                "ratio": 0.0003,
                "reinvest": True,
                "disabled": False,
                "skipped": None,
            },
        )
        by_name = {p.name: p for p in params}
        assert by_name["interval"].type == 1
        assert by_name["interval"].value == "1d"
        assert by_name["capital"].type == 2
        assert by_name["capital"].value == "10000000"
        assert by_name["ratio"].value == "0.0003"
        assert by_name["reinvest"].type == 3
        assert by_name["reinvest"].value == "true"
        assert by_name["disabled"].value == "false"
        assert "skipped" not in by_name


class TestTimestampMs:
    def test_none_passes_through(self):
        assert svc._timestamp_ms(None) is None

    def test_datetime_to_ms(self):
        value = datetime(2026, 1, 1, 0, 0, 0)
        assert svc._timestamp_ms(value) == int(value.timestamp() * 1000)

    def test_zero_treated_as_unset(self):
        assert svc._timestamp_ms(0) is None


class TestSerializeCollections:
    def test_equity_curve_skips_zero_timestamps(self):
        items = [
            SimpleNamespace(timestamp=1000, realized_pnl=1.0, total_pnl=2.0, equity=9.0),
            SimpleNamespace(timestamp=0, realized_pnl=0.0, total_pnl=0.0, equity=0.0),
        ]
        curve = svc._serialize_equity_curve(items)
        assert len(curve) == 1
        assert curve[0] == {
            "timestamp_ms": 1000,
            "realized_pnl": 1.0,
            "total_pnl": 2.0,
            "equity": 9.0,
        }

    def test_orders_map_enums_to_labels(self):
        order = SimpleNamespace(
            open_id="o1",
            trading_day=20261030,
            create_timestamp=5000,
            cancel_timestamp=0,
            commodity_key="FCT_T_MAIN",
            commodity_name="10年国债",
            side=1,
            offset=2,
            order_type=2,
            price=101.2,
            volume=2,
            remaining_volume=0,
            order_status=4,
            comment="",
            exchange_order_id="x1",
        )
        [serialized] = svc._serialize_orders([order])
        assert serialized["side"] == "buy"
        assert serialized["offset"] == "close"
        assert serialized["order_type"] == "market"
        assert serialized["status"] == "filled"
        assert serialized["cancel_timestamp_ms"] is None

    def test_trades_and_positions_map_enums(self):
        trade = SimpleNamespace(
            open_id="t1",
            trading_day=20261030,
            create_timestamp=6000,
            commodity_key="FCT_T_MAIN",
            commodity_name="10年国债",
            side=2,
            offset=1,
            order_type=1,
            price=100.0,
            volume=1,
            order_id="o1",
            position_id="p1",
            realized_pnl=-5.0,
            commission_fee=0.3,
            comment="",
            exchange_trade_id="et1",
        )
        [serialized_trade] = svc._serialize_trades([trade])
        assert serialized_trade["side"] == "sell"
        assert serialized_trade["offset"] == "open"
        assert serialized_trade["order_type"] == "limit"
        assert serialized_trade["realized_pnl"] == -5.0

        position = SimpleNamespace(
            open_id="p1",
            trading_day=20261030,
            create_timestamp=6000,
            update_timestamp=7000,
            commodity_key="FCT_T_MAIN",
            commodity_name="10年国债",
            side=1,
            price=100.0,
            volume=1,
            remaining_volume=1,
            margin=0.0,
            remaining_margin=0.0,
            unrealized_pnl=2.0,
            realized_pnl=0.0,
            status=1,
            comment="",
            exchange_position_id="",
            custom_data="",
        )
        [serialized_position] = svc._serialize_positions([position])
        assert serialized_position["side"] == "buy"
        assert serialized_position["status"] == "open"

    def test_daily_and_period_stats_pass_through(self):
        daily = SimpleNamespace(
            trading_day=20261029,
            trade_count=3,
            win_count=2,
            lose_count=1,
            win_rate=0.6667,
            win_pnl=10.0,
            lose_pnl=-3.0,
            profit_factor=3.33,
            best_trade_pnl=6.0,
            worst_trade_pnl=-3.0,
            commission_fee=0.5,
            unrealized_pnl=0.0,
            realized_pnl=7.0,
            total_pnl=7.0,
            realized_pnl_max=6.0,
            realized_pnl_max_timestamp=0,
            realized_pnl_min=-3.0,
            realized_pnl_min_timestamp=0,
            total_pnl_max=6.0,
            total_pnl_max_timestamp=0,
            total_pnl_min=-3.0,
            total_pnl_min_timestamp=0,
            max_realized_drawdown=3.0,
            max_realized_drawdown_timestamp=0,
            max_total_drawdown=3.0,
            max_total_drawdown_timestamp=0,
        )
        [serialized] = svc._serialize_daily_stats([daily])
        assert serialized["trading_day"] == 20261029
        assert serialized["total_pnl"] == 7.0

        period = SimpleNamespace(
            period=1,
            trade_count=3,
            win_count=2,
            lose_count=1,
            win_rate=0.6667,
            win_pnl=10.0,
            lose_pnl=-3.0,
            profit_factor=3.33,
            best_trade_pnl=6.0,
            worst_trade_pnl=-3.0,
            commission_fee=0.5,
            unrealized_pnl=0.0,
            realized_pnl=7.0,
            total_pnl=7.0,
            max_realized_drawdown=3.0,
            max_realized_drawdown_timestamp=0,
            max_total_drawdown=3.0,
            max_total_drawdown_timestamp=0,
            start_timestamp=0,
            end_timestamp=0,
        )
        [serialized_period] = svc._serialize_period_stats([period])
        assert serialized_period["period"] == 1


def _make_response():
    return SimpleNamespace(
        response_info=SimpleNamespace(code=0),
        daily_stats=[],
        period_stats=[],
        equity_curve=[],
        orders=[],
        positions=[],
        trades=[],
        traces=["trace line"],
        backtest_log="成交笔数: 3\nSTATISTICS:: Total Orders 3\nSTATISTICS:: Net Profit 1.500%\n",
        backtest_passed=True,
        backtest_exit_code=0,
    )


class TestRunTemplateBacktest:
    @pytest.fixture
    def _patched_network(self, monkeypatch):
        captured = {}

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def request(self, command_no, request, response_type):
                captured["command_no"] = command_no
                captured["request"] = request
                captured["response_type"] = response_type
                return _make_response()

            def close(self):
                captured["closed"] = True

        monkeypatch.setattr(svc, "prepare_protobuf_modules", lambda: (object(), _PB2))
        monkeypatch.setattr(
            svc, "_load_portal_connection", lambda settings: ("ws://x", "tok")
        )
        monkeypatch.setattr(svc, "_connect_and_login", lambda *a: _FakeClient())
        settings = svc.DreamStrategySettings(
            portal_config_url="http://example/config.json",
            template_id="tpl-1",
            agent="deepseek-chat",
            timeout_seconds=60,
        )
        monkeypatch.setattr(
            svc.DreamStrategySettings,
            "from_environment",
            classmethod(lambda cls: settings),
        )
        return captured

    def test_requires_code_or_version(self, _patched_network):
        with pytest.raises(ValueError, match="code 或 version_id"):
            svc.run_template_backtest()

    def test_code_only_sends_code_without_version(self, _patched_network):
        result = svc.run_template_backtest(code="self.MarketOrder('FCT_T_MAIN', 1)")
        captured = _patched_network
        assert captured["command_no"] == EI_BACKTEST
        request = captured["request"]
        assert request.template_id == "tpl-1"
        assert request.code.startswith("self.MarketOrder")
        assert request.version_id == ""
        assert request.initial_capital == 10_000_000.0
        assert result["backtest_passed"] is True
        assert result["version_id"] is None
        assert result["traces"] == ["trace line"]
        assert result["backtest_metrics"]
        assert any(m["label"] == "Total Orders" for m in result["backtest_metrics"])
        assert captured.get("closed") is True

    def test_version_only_sends_version_without_code(self, _patched_network):
        result = svc.run_template_backtest(version_id="ver-9")
        request = _patched_network["request"]
        assert request.version_id == "ver-9"
        assert request.code == ""
        assert result["version_id"] == "ver-9"

    def test_explicit_template_and_time_window(self, _patched_network):
        begin = datetime(2025, 1, 1)
        end = datetime(2026, 1, 1)
        svc.run_template_backtest(
            version_id="ver-9",
            template_id="tpl-2",
            parameters={"interval": "1d", "capital": 10000000},
            begin_time=begin,
            end_time=end,
            initial_capital=20_000_000,
            commission_ratio=0.0003,
        )
        request = _patched_network["request"]
        assert request.template_id == "tpl-2"
        assert request.begin_timestamp == int(begin.timestamp() * 1000)
        assert request.end_timestamp == int(end.timestamp() * 1000)
        assert request.initial_capital == 20_000_000
        assert request.commission_ratio == pytest.approx(0.0003)
        assert {p.name for p in request.params} == {"interval", "capital"}

    def test_remote_error_raised_and_client_closed(self, _patched_network, monkeypatch):
        captured = _patched_network

        class _ErrorClient:
            def request(self, command_no, request, response_type):
                response = _make_response()
                response.response_info.code = 42
                return response

            def close(self):
                captured["closed"] = True

        monkeypatch.setattr(svc, "_connect_and_login", lambda *a: _ErrorClient())
        with pytest.raises(RuntimeError, match="独立回测失败"):
            svc.run_template_backtest(version_id="ver-9")
        assert captured.get("closed") is True
