"""analysis/analyzer 单测：LLM 分析主流程与错误分支。

不碰真实 DB / LLM：monkeypatch 掉 DBOperations.get_news_by_id 与 analyzer.async_chat_completion。
覆盖主路径、发布日缺失兜底、空响应、无 JSON、JSON 解析失败、新闻/ID 异常、LLM 外部异常等分支。
"""

import json
from types import SimpleNamespace

import pytest

from backend.analysis import analyzer
from backend.analysis.analyzer import (
    AnalysisError,
    analyze_bond_yield_async,
    fallback_analysis_result,
)


def _resp(content: str):
    """构造 chat.completions 形状的响应（含 usage=None，token 日志分支被吞不影响结果）。"""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=None,
    )


def _valid_json() -> str:
    return json.dumps(
        {
            "direction": "positive",
            "horizon": "短期",
            "reason": "降息预期支撑债市",
            "factors": [
                {"code": "RATE", "name": "利率", "category": "MACRO", "direction": "positive"}
            ],
        }
    )


def _news(publish_date: str = "2026-09-01") -> dict:
    return {"title": "央行宣布降息", "content": "……全文……", "publish_date": publish_date}


@pytest.fixture(autouse=True)
def _patch_llm(monkeypatch):
    """默认: async_chat_completion 返回合法 JSON。单个用例可覆盖。"""
    async def _default(**kwargs):
        return _resp(_valid_json())

    monkeypatch.setattr(analyzer, "async_chat_completion", _default)


def _stub_news(monkeypatch, news_row):
    monkeypatch.setattr(
        analyzer.DBOperations, "get_news_by_id", staticmethod(lambda news_id: news_row)
    )


class TestFallbackAnalysisResult:
    def test_returns_neutral_with_reason(self):
        result = fallback_analysis_result("无法获取新闻发布日期")
        assert result["direction"] == "neutral"
        assert result["reason"] == "无法获取新闻发布日期"
        assert result["factors"] == []


class TestAnalyzeBondYield:
    async def test_success_main_path(self, monkeypatch):
        _stub_news(monkeypatch, _news())
        result = await analyze_bond_yield_async(news_id=1)
        assert result["direction"] == "positive"
        assert result["factors"][0]["code"] == "RATE"

    async def test_missing_publish_date_returns_fallback(self, monkeypatch):
        _stub_news(monkeypatch, _news(publish_date=""))
        result = await analyze_bond_yield_async(news_id=1)
        assert result["direction"] == "neutral"
        assert "发布日" in result["reason"]

    async def test_zero_news_id_raises(self, monkeypatch):
        with pytest.raises(AnalysisError, match="无法获取新闻ID"):
            await analyze_bond_yield_async(news_id=0)

    async def test_news_not_found_raises(self, monkeypatch):
        _stub_news(monkeypatch, None)
        with pytest.raises(AnalysisError, match="新闻不存在"):
            await analyze_bond_yield_async(news_id=42)

    async def test_empty_llm_content_raises(self, monkeypatch):
        _stub_news(monkeypatch, _news())

        async def _empty(**kwargs):
            return _resp("")

        monkeypatch.setattr(analyzer, "async_chat_completion", _empty)
        with pytest.raises(AnalysisError, match="LLM API调用失败"):
            await analyze_bond_yield_async(news_id=1)

    async def test_llm_content_without_json_raises(self, monkeypatch):
        _stub_news(monkeypatch, _news())

        async def _nojson(**kwargs):
            return _resp("抱歉，我无法判断。")

        monkeypatch.setattr(analyzer, "async_chat_completion", _nojson)
        with pytest.raises(AnalysisError, match="LLM API调用失败"):
            await analyze_bond_yield_async(news_id=1)

    async def test_json_decode_error_raises_specific(self, monkeypatch):
        _stub_news(monkeypatch, _news())

        async def _badjson(**kwargs):
            # extract_json_string 能提取出 { ... } 但 json.loads 失败
            return _resp('{"direction": ::broken::}')

        monkeypatch.setattr(analyzer, "async_chat_completion", _badjson)
        with pytest.raises(AnalysisError, match="LLM JSON解析错误"):
            await analyze_bond_yield_async(news_id=1)

    async def test_llm_exception_raises(self, monkeypatch):
        _stub_news(monkeypatch, _news())

        async def _boom(**kwargs):
            raise RuntimeError("upstream 500")

        monkeypatch.setattr(analyzer, "async_chat_completion", _boom)
        with pytest.raises(AnalysisError, match="LLM API调用失败"):
            await analyze_bond_yield_async(news_id=1)

    async def test_llm_receives_model_and_prompt(self, monkeypatch):
        _stub_news(monkeypatch, _news())
        calls = []

        async def _spy(**kwargs):
            calls.append(kwargs)
            return _resp(_valid_json())

        monkeypatch.setattr(analyzer, "async_chat_completion", _spy)
        await analyze_bond_yield_async(news_id=1, model_name="glm")
        assert calls[0]["model"]  # provider model（注册表解析）
        assert "央行宣布降息" in calls[0]["messages"][0]["content"]  # prompt 含新闻内容