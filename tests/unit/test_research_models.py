"""research_report/llm 纯函数单测：模型解析、fence 剥离、usage 提取、JSON 兜底。

不连库、不发 LLM 请求（client 全部 mock）。依赖 conftest 注入的 LLM_API_KEY / MYSQL_* 兜底环境变量。
"""

import json
from types import SimpleNamespace

import pytest

from backend.research_report import llm


def _fake_response(content: str):
    usage = SimpleNamespace(
        prompt_tokens=10, completion_tokens=5, total_tokens=15
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=usage,
    )


def _fake_client(content: str):
    client = SimpleNamespace()
    client.chat = SimpleNamespace(
        completions=SimpleNamespace(create=lambda *a, **k: _fake_response(content))
    )
    client.with_options = lambda *a, **k: client
    return client


def _fake_client_sequence(contents: list[str]):
    """按调用顺序依次返回不同内容的 client（用于重试测试）。"""
    calls = {"n": 0}

    def create(*a, **k):
        idx = min(calls["n"], len(contents) - 1)
        calls["n"] += 1
        return _fake_response(contents[idx])

    client = SimpleNamespace()
    client.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
    client.with_options = lambda *a, **k: client
    client._call_count = calls
    return client


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    """重试退避在测试中归零（真实退避 5s/12s）。"""
    monkeypatch.setattr(llm, "RETRY_DELAYS", (0, 0))


# ---- get_research_model_name ----


def test_get_research_model_name_default(monkeypatch):
    monkeypatch.delenv(llm.RESEARCH_MODEL_ENV, raising=False)
    assert llm.get_research_model_name() == "glm"


def test_get_research_model_name_override(monkeypatch):
    monkeypatch.setenv(llm.RESEARCH_MODEL_ENV, "qwen")
    assert llm.get_research_model_name() == "qwen"


# ---- resolve_provider_model ----


def test_resolve_provider_model_maps_short_name():
    assert llm.resolve_provider_model("glm") == "glm-5.2"
    assert llm.resolve_provider_model("deepseek") == "deepseek-v4-pro"
    assert llm.resolve_provider_model("qwen") == "qwen3.7-flash"


def test_resolve_provider_model_invalid_falls_back_to_glm():
    # 与 config.get_analysis_model_info 一致：未知短名兜底 glm
    assert llm.resolve_provider_model("nonexistent") == "glm-5.2"


# ---- strip_code_fence ----


def test_strip_code_fence_removes_json_markers():
    assert llm.strip_code_fence("```json\n{\"a\": 1}\n```", "json") == "{\"a\": 1}"


def test_strip_code_fence_removes_markdown_markers():
    assert llm.strip_code_fence("```markdown\n# 标题\n```", "markdown|md") == "# 标题"


def test_strip_code_fence_keeps_plain_text():
    assert llm.strip_code_fence("纯文本", "") == "纯文本"


# ---- build_usage ----


def test_build_usage_extracts_tokens():
    usage = llm.build_usage(_fake_response("x"), 42)
    assert usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "latency_ms": 42,
    }


# ---- analyze_report 深度拆解信封解析与硬失败 ----


_VALID_MARKDOWN = """# 示例研报 · 深度拆解

## 一、核心论点（作者观点）
- 利率债慢牛。（原文：“利率债延续慢牛。”，第1页）

## 二、论证结构（观点树）
- 主论点（原文：“利率债延续慢牛。”，第1页）

## 三、观点复现
### 观点 1：利率债慢牛
- 论点：10Y 中枢下行。（原文：“利率债延续慢牛。”，第1页）
- 论据：GDP 4.6%、CPI 0.4%。（原文：“GDP 增长 4.6%，CPI 中枢 0.4%。”，第2页）
- 前提假设：赤字率 3.2%。（原文：“赤字率维持在 3.2% 左右。”，第3页）
- 推理链路：弱基本面→低通胀→宽货币→收益率下行。
- 风险与边界：财政超预期发力则判断失效。（原文：“赤字率提高至 4.0% 则判断需修正。”，第4页）

## 四、关键证据与数据
| 指标 | 数值 | 原文出处 |
| --- | --- | --- |
| GDP | 4.6% | “GDP 增长 4.6%，CPI 中枢 0.4%。”（第2页） |

## 五、作者风险提示与适用边界
- 财政超预期将带来上行风险。（原文：“赤字率提高至 4.0% 则判断需修正。”，第4页）

## 六、AI 分析解读（非作者观点）
- 原文未给净供给测算。
"""


def _envelope(**overrides):
    payload = {"markdown": _VALID_MARKDOWN, "market_view": "neutral"}
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def test_analyze_report_parses_valid_envelope(monkeypatch):
    content = _envelope(
        short_summary="s", key_points=["a"], industries=["银行"]
    )
    monkeypatch.setattr(llm, "get_llm_client", lambda: _fake_client(content))
    markdown, meta, usage = llm.analyze_report("正文")
    assert isinstance(markdown, str) and "观点复现" in markdown
    assert meta["summary"] == "s"
    assert meta["key_points"] == ["a"]
    assert meta["industries"] == ["银行"]
    assert usage["total_tokens"] == 15


def test_analyze_report_strips_fence_before_parsing(monkeypatch):
    content = "```json\n" + _envelope(market_view="bullish") + "\n```"
    monkeypatch.setattr(llm, "get_llm_client", lambda: _fake_client(content))
    _markdown, meta, _usage = llm.analyze_report("正文")
    assert meta["market_view"] == "bullish"


def test_analyze_report_raises_on_bad_json(monkeypatch):
    monkeypatch.setattr(llm, "get_llm_client", lambda: _fake_client("这不是 JSON"))
    with pytest.raises(RuntimeError):
        llm.analyze_report("正文")


def test_analyze_report_retries_empty_content_then_succeeds(monkeypatch):
    # 第 1 次空响应（常见于限流），第 2 次正常 → 重试后成功
    client = _fake_client_sequence(["", _envelope(market_view="bullish")])
    monkeypatch.setattr(llm, "get_llm_client", lambda: client)
    _markdown, meta, _usage = llm.analyze_report("正文")
    assert meta["market_view"] == "bullish"
    assert client._call_count["n"] == 2


def test_analyze_report_corrective_retry_after_structure_violation(monkeypatch):
    # 第 1 次缺章节（校验不过），第 2 次合格 → 自纠重试成功
    bad_markdown = _VALID_MARKDOWN.replace("## 三、观点复现\n", "")
    bad_envelope = json.dumps({"markdown": bad_markdown}, ensure_ascii=False)
    client = _fake_client_sequence([bad_envelope, _envelope()])
    monkeypatch.setattr(llm, "get_llm_client", lambda: client)
    markdown, _meta, _usage = llm.analyze_report("正文")
    assert "观点复现" in markdown
    assert client._call_count["n"] == 2


def test_parse_envelope_repairs_unescaped_straight_quotes_in_markdown():
    # 模型在 markdown 里用了未转义的英文引号，导致 JSON 截断 → 兜底修复后可解析
    markdown = _VALID_MARKDOWN.replace("“利率债延续慢牛。”", '"利率债慢牛了"', 1)
    raw = json.dumps({"markdown": markdown, "market_view": "neutral"}, ensure_ascii=False)
    # json.dumps 会把引号转义；模拟模型漏转义：把 \" 还原成裸 "
    raw = raw.replace('\\"利率债慢牛了\\"', '"利率债慢牛了"')
    envelope = llm._parse_envelope(raw)
    assert "利率债慢牛了" in envelope["markdown"]