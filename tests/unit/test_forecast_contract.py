from datetime import date, datetime

from backend.analysis.forecast_contract import FORECAST_TARGET, attach_forecast_context


def test_attach_context_uses_deterministic_target_and_real_data_cutoffs():
    report = {"报告摘要": "测试"}
    news = [
        {"id": 11, "pub_date": date(2026, 11, 5)},
        {"id": 12, "pub_date": datetime(2026, 11, 6, 9, 30)},
    ]
    yields = {
        "10Y": [{"date": date(2026, 11, 4)}, {"date": "2026-11-06"}],
        "5Y": [{"date": "2026-11-05"}],
    }

    assert attach_forecast_context(report, news, yields) is report
    assert report["预测标的"] == FORECAST_TARGET
    assert report["预测标的"] is not FORECAST_TARGET
    assert report["数据状态"] == {
        "包含新闻": True,
        "包含收益率": True,
        "新闻截至": "2026-11-06",
        "收益率截至": "2026-11-06",
    }


def test_attach_context_marks_missing_inputs_without_inventing_dates():
    report = attach_forecast_context({}, [{"id": 1, "pub_date": None}], {})
    assert report["数据状态"] == {
        "包含新闻": True,
        "包含收益率": False,
        "新闻截至": None,
        "收益率截至": None,
    }

    empty = attach_forecast_context({}, [], {"10Y": []})
    assert empty["数据状态"]["包含新闻"] is False
    assert empty["数据状态"]["新闻截至"] is None


def test_evidence_ids_are_limited_to_real_integer_input_ids_and_deduplicated():
    report = {
        "核心驱动": [
            {"类型": "政策", "证据新闻ID": [11, 11, 999, "11", True, 12.0]},
            {"类型": "海外", "证据新闻ID": "11"},
            {"类型": "资金"},
            "保留异常项，不让后处理崩溃",
        ]
    }
    attach_forecast_context(report, [{"id": 11}], {})

    assert report["核心驱动"][0]["证据新闻ID"] == [11]
    assert report["核心驱动"][1]["证据新闻ID"] == []
    assert report["核心驱动"][2]["证据新闻ID"] == []
    assert report["核心驱动"][3] == "保留异常项，不让后处理崩溃"


def test_prompt_contract_defines_10y_semantics_horizons_and_real_news_ids():
    # 延迟导入：模块级模型配置由 tests/conftest.py 提供测试环境。
    from backend.analysis.generate_report import PROMPT_VERSION, construct_enhanced_prompt

    prompt = construct_enhanced_prompt(
        news_texts=[{
            "id": 321,
            "pub_date": "2026-11-06",
            "title": "公开市场操作",
            "direction": "利多",
            "horizon": "短期",
            "reason": "净投放",
        }],
        yield_data={"10Y": [{"date": "2026-11-06", "value": 1.8}]},
        market_summary={},
        report_date="2026-11-06",
    )

    assert PROMPT_VERSION == "v2.4"
    assert "预测标的固定为中债 10Y 国债到期收益率" in prompt
    assert "T+1/T+5/T+20" in prompt
    assert "[新闻ID:321]" in prompt
    assert "证据新闻ID只能原样引用" in prompt
    assert "失效条件" in prompt
