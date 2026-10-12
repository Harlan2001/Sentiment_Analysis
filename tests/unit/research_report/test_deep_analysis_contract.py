"""板块一《单篇研报 AI 深度拆解》契约测试（TDD）。

对应 docs/PRD-研报分析功能细化.md 板块一（1.2 规则 / 1.3 输出骨架 / 1.6 验收红线）。

契约约定实现侧提供（模块/函数名可调整，但须同步改测试，语义不得放宽）：

- ``backend/research_report/deep_analysis.py``
  - ``validate_deep_analysis(markdown: str) -> list[str]``：返回违规说明列表，
    空列表表示合格；入参为空时抛 ``ValueError``。检查规则：
      1. 六个固定章节按序出现：核心论点 / 论证结构 / 观点复现 /
         关键证据与数据 / 风险提示与适用边界 / AI 分析解读（非作者观点）；
      2. 每张观点卡片（观点复现章节内按 ``###`` 切分）五要素齐全：
         论点、论据、前提假设、推理链路、风险（风险与边界）；
      3. 论点 / 论据 / 风险三类要素要么在行内附逐字原文摘录（带页码），
         要么显式写“原文未明确给出”；前提假设/推理链路不强制出处；
      4. AI 解读章节标题必须含“非作者观点”。
  - ``find_fluff_sentences(text: str) -> list[str]``：返回命中空话词表
    （如“未来可期/值得关注/持续向好”）且未附溯源的句子。
- ``analyze_report`` 的新契约：模型返回深度拆解 Markdown（字符串透传）；
  模型未返回内容时抛 ``RuntimeError``，不再返回 ``{"error": ...}`` 假成功。
"""

import pytest

from backend.research_report import llm

# ── 合格样例（满足 1.3 骨架与全部溯源规则） ──────────────────────────────

VALID_MARKDOWN = """# 测试研报 · 深度拆解

## 一、核心论点（作者观点）
- 一句话主张：利率债慢牛，10Y 中枢 1.55%。（原文：“利率债延续慢牛，10 年期国债收益率中枢下行至 1.55%。”，第1页）
- 操作建议：收益率超调时加仓。（原文：“收益率超调上行时积极加仓。”，第2页）

## 二、论证结构（观点树）
- 主论点：利率债慢牛（原文：“利率债延续慢牛，10 年期国债收益率中枢下行至 1.55%。”，第1页）
  - 分论点 1：基本面弱（原文：“GDP 增长 4.6%，地产投资 -6%，CPI 中枢 0.4%。”，第3页）

## 三、观点复现
### 观点 1：10Y 中枢降至 1.55%
- 论点：10Y 中枢由 1.80% 降至 1.55%。（原文：“利率债延续慢牛，10 年期国债收益率中枢下行至 1.55%。”，第1页）
- 论据：GDP 4.6%、地产投资 -6%、CPI 0.4%。（原文：“GDP 增长 4.6%，地产投资 -6%，CPI 中枢 0.4%。”，第3页）
- 前提假设：赤字率 3.2%、专项债不超预期。（原文：“赤字率维持在 3.2% 左右。”，第9页）
- 推理链路：地产拖累→产出缺口为负→低通胀→货币宽松→配置需求大于供给→收益率下行。
- 风险与边界：赤字率提至 4.0% 则全年判断失效。（原文：“赤字率提高至 4.0% 则全年判断需修正。”，第13页）

## 四、关键证据与数据
| 指标 | 数值 | 原文出处 |
| --- | --- | --- |
| GDP 增速 | 4.6% | “GDP 增长 4.6%，地产投资 -6%，CPI 中枢 0.4%。”（第3页） |

## 五、作者风险提示与适用边界
- 财政超预期发力将带来 20-30bp 上行风险。（原文：“赤字率提高至 4.0% 则全年判断需修正。”，第13页）

## 六、AI 分析解读（非作者观点）
- 隐含假设：配置需求大于净供给，但原文未给出净供给测算。
"""



def _validate(markdown: str) -> list[str]:
    from backend.research_report.deep_analysis import validate_deep_analysis

    return validate_deep_analysis(markdown)


# ── 1.3 固定骨架 ─────────────────────────────────────────────────────────


def test_valid_markdown_has_no_violations():
    assert _validate(VALID_MARKDOWN) == []


@pytest.mark.parametrize("missing_heading", ["核心论点", "论证结构", "观点复现", "关键证据与数据",
                                            "风险提示与适用边界", "非作者观点"])
def test_missing_required_section_is_violation(missing_heading):
    marker = {
        "核心论点": "## 一、核心论点（作者观点）",
        "论证结构": "## 二、论证结构（观点树）",
        "观点复现": "## 三、观点复现",
        "关键证据与数据": "## 四、关键证据与数据",
        "风险提示与适用边界": "## 五、作者风险提示与适用边界",
        "非作者观点": "## 六、AI 分析解读（非作者观点）",
    }[missing_heading]
    # 删除该标题所在行（保留章节正文不足以冒充标题）
    markdown = "\n".join(
        line for line in VALID_MARKDOWN.splitlines() if not line.startswith(marker)
    )
    violations = _validate(markdown)
    assert violations, f"缺少章节 {missing_heading} 必须报违规"
    assert any(missing_heading in v for v in violations)


# ── 1.2 规则 2/3：五要素与逐观点溯源 ────────────────────────────────────


def test_card_without_sourced_evidence_is_violation():
    markdown = VALID_MARKDOWN.replace(
        "- 论据：GDP 4.6%、地产投资 -6%、CPI 0.4%。（原文：“GDP 增长 4.6%，地产投资 -6%，CPI 中枢 0.4%。”，第3页）",
        "- 论据：基本面各项数据表现较好。",  # 无具体证据且无行内原文摘录
    )
    violations = _validate(markdown)
    assert any("论据" in v for v in violations)


def test_explicit_missing_marker_satisfies_absent_element():
    # 作者未给假设时，固定标注“原文未明确给出”视为合规，不得编造
    markdown = VALID_MARKDOWN.replace(
        "- 前提假设：赤字率 3.2%、专项债不超预期。（原文：“赤字率维持在 3.2% 左右。”，第9页）",
        "- 前提假设：原文未明确给出。",
    )
    assert _validate(markdown) == []


def test_bold_and_numbered_element_labels_are_recognized():
    # 模型常见变体：加粗 **论点**：与编号「1. 论据：」也应被识别为五要素
    markdown = VALID_MARKDOWN.replace(
        "### 观点 1：10Y 中枢降至 1.55%\n"
        "- 论点：10Y 中枢由 1.80% 降至 1.55%。（原文：“利率债延续慢牛，10 年期国债收益率中枢下行至 1.55%。”，第1页）\n"
        "- 论据：GDP 4.6%、地产投资 -6%、CPI 0.4%。（原文：“GDP 增长 4.6%，地产投资 -6%，CPI 中枢 0.4%。”，第3页）\n"
        "- 前提假设：赤字率 3.2%、专项债不超预期。（原文：“赤字率维持在 3.2% 左右。”，第9页）\n"
        "- 推理链路：地产拖累→产出缺口为负→低通胀→货币宽松→配置需求大于供给→收益率下行。\n"
        "- 风险与边界：赤字率提至 4.0% 则全年判断失效。（原文：“赤字率提高至 4.0% 则全年判断需修正。”，第13页）",
        "### 观点 1：10Y 中枢降至 1.55%\n"
        "**论点**：10Y 中枢由 1.80% 降至 1.55%。（原文：“利率债延续慢牛，10 年期国债收益率中枢下行至 1.55%。”，第1页）\n"
        "1. 论据：GDP 4.6%、地产投资 -6%、CPI 0.4%。（原文：“GDP 增长 4.6%，地产投资 -6%，CPI 中枢 0.4%。”，第3页）\n"
        "2. **前提假设**：赤字率 3.2%、专项债不超预期。（原文：“赤字率维持在 3.2% 左右。”，第9页）\n"
        "3. 推理链路：地产拖累→产出缺口为负→低通胀→货币宽松→收益率下行。\n"
        "4. 风险与边界：赤字率提至 4.0% 则全年判断失效。（原文：“赤字率提高至 4.0% 则全年判断需修正。”，第13页）",
    )
    assert _validate(markdown) == []


def test_claim_without_inline_quote_is_violation():
    # 论点去掉行内原文摘录 → 必须判违规
    markdown = VALID_MARKDOWN.replace(
        "- 论点：10Y 中枢由 1.80% 降至 1.55%。（原文：“利率债延续慢牛，10 年期国债收益率中枢下行至 1.55%。”，第1页）",
        "- 论点：10Y 中枢由 1.80% 降至 1.55%。",
    )
    violations = _validate(markdown)
    assert any("论点" in v and ("摘录" in v or "原文" in v) for v in violations)


def test_empty_input_raises():
    with pytest.raises(ValueError):
        _validate("")


# ── 1.2 规则 4：禁止空话 ─────────────────────────────────────────────────


def test_fluff_detector_flags_unsourced_empty_phrase():
    from backend.research_report.deep_analysis import find_fluff_sentences

    hits = find_fluff_sentences("行业未来可期，建议持续关注。")
    assert hits  # 空话且无出处 → 命中


def test_fluff_detector_allows_sourced_concrete_sentence():
    from backend.research_report.deep_analysis import find_fluff_sentences

    hits = find_fluff_sentences("地产投资同比 -6%，仍是主要拖累。（原文：“地产投资同比下降 6%，仍是主要拖累项。”，第3页）")
    assert hits == []


# ── analyze_report 新契约 ────────────────────────────────────────────────


def _fake_client(content: str):
    from types import SimpleNamespace

    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=usage,
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda *a, **k: resp))
    )
    client.with_options = lambda *a, **k: client
    return client


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    monkeypatch.setattr(llm, "RETRY_DELAYS", (0, 0))


def test_analyze_report_returns_deep_markdown(monkeypatch):
    import json

    envelope = json.dumps(
        {"markdown": VALID_MARKDOWN, "market_view": "bullish", "view_strength": 0.8},
        ensure_ascii=False,
    )
    monkeypatch.setattr(llm, "get_llm_client", lambda: _fake_client(envelope))
    result = llm.analyze_report("研报正文")
    # 新契约：(markdown, meta, usage)，首项为通过结构校验的深度拆解
    assert isinstance(result, tuple) and len(result) == 3
    markdown, meta, _usage = result
    assert isinstance(markdown, str)
    assert _validate(markdown) == []
    assert meta["market_view"] == "bullish"


def test_analyze_report_raises_on_empty_model_output(monkeypatch):
    monkeypatch.setattr(llm, "get_llm_client", lambda: _fake_client(""))
    with pytest.raises(RuntimeError):
        llm.analyze_report("研报正文")
