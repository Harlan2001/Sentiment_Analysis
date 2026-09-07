"""strategy/portfolio_analysis 单测：组合策略分析主流程与错误分支。

不碰真实 DB / LLM：monkeypatch 掉 resolve_target_news_date、
fetch_news_for_date、llm_chat_async 与 PortfolioAnalysisRepository。
"""

import json
from datetime import date, datetime

import pytest

from backend.strategy import portfolio_analysis as pa


def _sample_news() -> list[dict]:
    return [
        {
            "news_id": 1,
            "title": "央行开展公开市场操作投放流动性",
            "direction": "positive",
            "horizon": "短期",
            "reason": "资金面宽松支撑债市",
            "pub_time": datetime(2026, 9, 4, 18, 30, 0),
        },
        {
            "news_id": 2,
            "title": "财政增量政策发力专项债发行提速",
            "direction": "negative",
            "horizon": "中期",
            "reason": "供给压力抬升降久期风险",
            "pub_time": datetime(2026, 9, 4, 10, 5, 0),
        },
    ]


def _valid_analysis() -> dict:
    return {
        "general": {
            "duration_years": {"min": 1.5, "max": 3.0},
            "single_bond_weight_pct": {"min": 2.0, "max": 8.0},
            "min_rating": "AA+",
            "portfolio_fund_wan": 100.0,
        },
        "distribution_by_category": {
            key: {"min": 1.0, "max": 20.0} for key in pa.CATEGORY_KEYS
        },
        "distribution_by_type": {
            "interest_rate_bond": {"min": 30.0, "max": 60.0},
            "credit_bond": {"min": 40.0, "max": 70.0},
        },
    }


class _FakeRepo:
    def __init__(self, cached_row=None):
        self.cached_row = cached_row
        self.saved_success_kwargs = None
        self.saved_failure_kwargs = None

    def get_by_cache_key(self, cache_key):
        return self.cached_row

    def save_success(self, **kwargs):
        self.saved_success_kwargs = kwargs

    def save_failure(self, **kwargs):
        self.saved_failure_kwargs = kwargs


def _patch_env(monkeypatch, *, repo=None, news=None, llm_content=None):
    """搭好默认打桩；返回 fake repo 供断言。"""
    fake = repo if repo is not None else _FakeRepo()

    async def _llm(*args, **kwargs):
        return llm_content

    monkeypatch.setattr(pa, "resolve_target_news_date", lambda **_: date(2026, 9, 4))
    monkeypatch.setattr(pa, "fetch_news_for_date", lambda d, limit=50: news or [])
    monkeypatch.setattr(pa, "llm_chat_async", _llm)
    monkeypatch.setattr(pa, "PortfolioAnalysisRepository", lambda: fake)
    return fake


def _cached_success_row() -> dict:
    row = _valid_analysis()
    return {
        "status": "success",
        "output": row,
        "model_name": "glm",
        "news_count": 2,
        "window_start": datetime(2026, 9, 3, 0, 0, 0),
        "window_end": datetime(2026, 9, 4, 0, 0, 0),
        "latest_news_pub_time": datetime(2026, 9, 3, 18, 30, 0),
        "request_id": "cached-001",
        "latency_ms": 42,
    }


@pytest.mark.asyncio
async def test_happy_path_builds_analysis_and_meta(monkeypatch):
    fake = _patch_env(monkeypatch, news=_sample_news(), llm_content=json.dumps(_valid_analysis()))

    result = await pa.analyze_portfolio_strategy()

    assert result["analysis"]["general"]["min_rating"] == "AA+"
    assert set(result["analysis"]["distribution_by_category"]) == set(pa.CATEGORY_KEYS)
    meta = result["meta"]
    assert meta["cache_hit"] is False
    assert meta["model_name"] == "glm"
    assert meta["news_count"] == 2
    assert meta["window_start"].startswith("2026-09-04")
    assert meta["latest_news_pub_time"].startswith("2026-09-04")
    assert isinstance(meta["latency_ms"], int)
    # 成功应写缓存
    assert fake.saved_success_kwargs is not None
    assert fake.saved_success_kwargs["cache_key"].startswith("portfolio-analysis:2026-09-04:glm:")
    assert fake.saved_success_kwargs["news_ids"] == [1, 2]


@pytest.mark.asyncio
async def test_cache_hit_skips_llm(monkeypatch):
    calls: list[str] = []

    async def _llm(*args, **kwargs):
        calls.append("called")
        return "{}"

    fake = _FakeRepo(cached_row=_cached_success_row())
    _patch_env(monkeypatch, repo=fake, news=_sample_news())
    monkeypatch.setattr(pa, "llm_chat_async", _llm)

    result = await pa.analyze_portfolio_strategy()

    assert calls == []
    assert result["meta"]["cache_hit"] is True
    assert result["analysis"]["general"]["min_rating"] == "AA+"
    assert fake.saved_success_kwargs is None


@pytest.mark.asyncio
async def test_force_refresh_skips_cache(monkeypatch):
    fake = _FakeRepo(cached_row=_cached_success_row())
    _patch_env(monkeypatch, repo=fake, news=_sample_news(), llm_content="{}")

    with pytest.raises(pa.PortfolioAnalysisError):
        await pa.analyze_portfolio_strategy(force_refresh=True)

    # 强刷时即使有旧的 success 缓存也应重新走 LLM（该 mock 返回非法 JSON -> 抛错）
    dataset = _valid_analysis()
    fake2 = _FakeRepo(cached_row=_cached_success_row())
    _patch_env(monkeypatch, repo=fake2, news=_sample_news(), llm_content=json.dumps(dataset))
    result = await pa.analyze_portfolio_strategy(force_refresh=True)
    assert result["meta"]["cache_hit"] is False


@pytest.mark.asyncio
async def test_no_news_raises(monkeypatch):
    _patch_env(monkeypatch, news=[])

    with pytest.raises(pa.PortfolioAnalysisError) as exc_info:
        await pa.analyze_portfolio_strategy()
    assert "目标新闻日没有可分析的新闻" in str(exc_info.value)


@pytest.mark.asyncio
async def test_invalid_llm_output_raises(monkeypatch):
    _patch_env(monkeypatch, news=_sample_news(), llm_content="抱歉，无法分析")

    with pytest.raises(pa.PortfolioAnalysisError, match="模型输出非 JSON"):
        await pa.analyze_portfolio_strategy()


@pytest.mark.asyncio
async def test_output_schema_missing_category_raises(monkeypatch):
    bad = _valid_analysis()
    del bad["distribution_by_type"]["credit_bond"]
    _patch_env(monkeypatch, news=_sample_news(), llm_content=json.dumps(bad))

    with pytest.raises(pa.PortfolioAnalysisError, match="模型输出非 JSON"):
        await pa.analyze_portfolio_strategy()


@pytest.mark.asyncio
async def test_failure_is_recorded_in_cache(monkeypatch):
    fake = _patch_env(monkeypatch, news=_sample_news(), llm_content="非 JSON")

    with pytest.raises(pa.PortfolioAnalysisError):
        await pa.analyze_portfolio_strategy()

    assert fake.saved_failure_kwargs is not None
    assert fake.saved_failure_kwargs["cache_key"].startswith(
        "portfolio-analysis:2026-09-04:glm:"
    )
    assert fake.saved_failure_kwargs["error_message"]


class TestResolveTargetNewsDate:
    @pytest.mark.parametrize("value,expected", [
        (date(2026, 9, 4), date(2026, 9, 4)),
        (datetime(2026, 9, 4, 8, 0, 0), date(2026, 9, 4)),
    ])
    def test_returns_most_recent_news_date(self, monkeypatch, value, expected):
        monkeypatch.setattr(pa, "execute_query", lambda q, params=None, one=False: (value,))

        assert pa.resolve_target_news_date() == expected

    def test_none_when_no_news(self, monkeypatch):
        monkeypatch.setattr(pa, "execute_query", lambda q, params=None, one=False: (None,))

        assert pa.resolve_target_news_date() is None


class TestBuildPrompt:
    def test_contains_contract_and_data(self):
        prompt = pa.build_prompt(_sample_news(), date(2026, 9, 4), "glm")

        assert "2026-09-04" in prompt
        assert "glm" in prompt
        assert "gov_bond" in prompt
        assert "interest_rate_bond" in prompt
        assert "AA+" in prompt
        assert "央行开展公开市场操作投放流动性" in prompt
        # 必须包含全部 9 类键名
        for key in pa.CATEGORY_KEYS:
            assert key in prompt


class TestRangeValidation:
    def test_min_exceeds_max_rejected(self):
        with pytest.raises(ValueError):
            pa.RangeModel(min=5.0, max=2.0)


class TestSumValidation:
    def _result(self, **overrides):
        data = _valid_analysis()
        data["distribution_by_category"].update(overrides)
        return pa.PortfolioAnalysisResult.model_validate(data)

    def test_valid_sums_accepted(self):
        # 9 类各 min=1 / max=20 → mins=9≤100, maxes=180≥100；类型 70/130 亦合法
        assert pa.PortfolioAnalysisResult.model_validate(_valid_analysis())

    def test_min_sum_over_100_rejected(self):
        with pytest.raises(ValueError, match="min 之和不能超过 100"):
            self._result(
                **{key: {"min": 50.0, "max": 60.0} for key in ("gov_bond", "local_gov_bond", "corp_credit_bond")}
            )

    def test_max_sum_under_100_rejected(self):
        with pytest.raises(ValueError, match="max 之和不能低于 100"):
            self._result(
                **{key: {"min": 0.0, "max": 1.0} for key in pa.CATEGORY_KEYS}
            )

    def test_type_group_invalid_rejected(self):
        data = _valid_analysis()
        data["distribution_by_type"] = {
            "interest_rate_bond": {"min": 20.0, "max": 30.0},
            "credit_bond": {"min": 20.0, "max": 30.0},
        }
        with pytest.raises(ValueError, match="max 之和不能低于 100"):
            pa.PortfolioAnalysisResult.model_validate(data)