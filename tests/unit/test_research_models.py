"""research_report/llm 纯函数单测：模型解析、fence 剥离、usage 提取、JSON 兜底。

不连库、不发 LLM 请求（client 全部 mock）。依赖 conftest 注入的 LLM_API_KEY / MYSQL_* 兜底环境变量。
"""

from types import SimpleNamespace

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
    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda *a, **k: _fake_response(content))
        )
    )


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


# ---- analyze_report JSON 解析与兜底 ----


def test_analyze_report_parses_valid_json(monkeypatch):
    content = '{"summary":"s","key_points":["a"],"industries":["银行"]}'
    monkeypatch.setattr(llm, "get_llm_client", lambda: _fake_client(content))
    parsed, raw, usage = llm.analyze_report("正文")
    assert parsed == {"summary": "s", "key_points": ["a"], "industries": ["银行"]}
    assert raw == content
    assert usage["total_tokens"] == 15


def test_analyze_report_strips_fence_before_parsing(monkeypatch):
    content = '```json\n{"summary":"s","market_view":"bullish"}\n```'
    monkeypatch.setattr(llm, "get_llm_client", lambda: _fake_client(content))
    parsed, _, _ = llm.analyze_report("正文")
    assert parsed["market_view"] == "bullish"


def test_analyze_report_returns_error_dict_on_bad_json(monkeypatch):
    monkeypatch.setattr(llm, "get_llm_client", lambda: _fake_client("这不是 JSON"))
    parsed, raw, _ = llm.analyze_report("正文")
    assert parsed["error"] == "JSON解析失败"
    assert raw == "这不是 JSON"