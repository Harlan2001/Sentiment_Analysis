"""Build DreamStrategy prompts from instrument-scoped Sentiment intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from backend.strategy.sentiment_context import MarketContextScope, build_sentiment_strategy_context


TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1]
    / "integrations"
    / "dream"
    / "prompts"
    / "sentiment_strategy_chat_prompt_template.md"
)
DEFAULT_FREQUENCY = "日频"
TECHNICAL_STATE = "价格与技术数据由量化宿主在策略运行时读取；Sentiment 不提供 OHLCV，不得伪造技术状态。"
EDITABLE_SECTION_START = "[USER_EDITABLE_REQUIREMENT]"
EDITABLE_SECTION_END = "[/USER_EDITABLE_REQUIREMENT]"


@dataclass(frozen=True)
class InstrumentDefinition:
    name: str
    request_keywords: tuple[str, ...]
    market_scope: MarketContextScope


INSTRUMENTS: tuple[InstrumentDefinition, ...] = (
    InstrumentDefinition(
        name="黄金期货 (FCT_AU_MAIN)",
        request_keywords=("黄金", "FCT_AU_MAIN", "AU_MAIN"),
        market_scope=MarketContextScope(
            label="黄金市场",
            news_keywords=("黄金", "金价", "贵金属", "现货金"),
            directional_trade_guidance=False,
            include_yield_curve=False,
        ),
    ),
    InstrumentDefinition(
        name="2Y 国债期货 (FCT_TS_MAIN)",
        request_keywords=("2Y", "2年期国债期货", "FCT_TS_MAIN", "TS_MAIN"),
        market_scope=MarketContextScope(
            label="2年期国债市场",
            news_keywords=("2年期国债", "国债", "债券", "收益率", "货币政策"),
        ),
    ),
    InstrumentDefinition(
        name="10Y 国债期货 (FCT_T_MAIN)",
        request_keywords=("10Y", "国债期货", "FCT_T_MAIN", "T_MAIN"),
        market_scope=MarketContextScope(
            label="10年期国债市场",
            news_keywords=("10年期国债", "国债", "债券", "收益率", "货币政策"),
        ),
    ),
)
DEFAULT_INSTRUMENT = InstrumentDefinition(
    name="未从用户需求中识别具体交易品种；请根据用户明确需求确认，不得默认为 10Y 国债期货",
    request_keywords=(),
    market_scope=MarketContextScope(
        label="全市场新闻",
        directional_trade_guidance=False,
        include_yield_curve=False,
    ),
)


def _resolve_instrument(requirement: str) -> InstrumentDefinition:
    """Return the instrument definition explicitly named by the user."""

    normalized = "".join(requirement.upper().split())
    for instrument in INSTRUMENTS:
        if any(keyword.upper() in normalized for keyword in instrument.request_keywords):
            return instrument
    return DEFAULT_INSTRUMENT


def _format_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "- 本窗口内暂无与标的匹配的明确方向事件。"
    return "\n".join(
        "- {time:%m-%d %H:%M} | {title} | {direction}/{horizon} | {reason}".format(
            time=item["pub_time"],
            title=item["title"],
            direction=item["direction"],
            horizon=item["horizon"],
            reason=item["reason"],
        )
        for item in events
    )


def _format_factors(factors: list[dict[str, Any]]) -> str:
    return "、".join(item["name"] for item in factors) if factors else "暂无高置信号"


def _format_yields(yield_curve: list[dict[str, Any]], scope: MarketContextScope) -> str:
    if not scope.include_yield_curve:
        return "本标的不使用债券收益率曲线；价格和技术数据由策略运行时读取。"
    if not yield_curve:
        return "暂无可用收益率数据"
    return "；".join(
        f"{item['period']} {item['value']:.2f}%（5日{item['change_5d_bp']:+.0f}bp）"
        for item in yield_curve
    )


def _sentiment_guidance(counts: dict[str, int], scope: MarketContextScope) -> tuple[str, str]:
    if not scope.directional_trade_guidance:
        return (
            f"已仅按{scope.label}检索新闻；原有方向标签不直接等同于{scope.label}多空。",
            "新闻仅用于风险提示、信号过滤或提高开仓阈值，不单独决定交易方向。",
        )
    if counts["positive"] > counts["negative"]:
        return f"利多{scope.label}信号占优", "将新闻仅用于方向确认或降低开仓阈值"
    if counts["negative"] > counts["positive"]:
        return f"利空{scope.label}信号占优", "将新闻仅用于空头方向确认、提高开仓阈值或风险降级"
    return f"利多与利空{scope.label}信号均衡或不足", "不以新闻形成方向，必要时暂停交易"


def build_dream_strategy_continuation_prompt(market_prompt: str) -> str:
    """Add continuation rules to a freshly-built market-aware strategy prompt."""

    if not market_prompt.strip():
        raise ValueError("Market-aware strategy prompt must not be empty")
    return f"""{market_prompt}

[EXECUTION RULES]
- Continue the existing DreamStrategy session and directly generate a complete strategy response now.
- The current Sentiment news analysis above is a fresh snapshot for this version. Use its representative events as auditable news references for this strategy version.
- If important execution parameters are missing, ask concise follow-up questions instead of inventing defaults. When the user supplies them, use those additions to generate the next strategy response in this same session.
- Existing strategy versions are already complete. Do not reopen, regenerate, or ask about their parameters unless the latest request explicitly asks to modify them.
- If the latest request asks for another strategy, generate only that newly requested strategy as the next version in this same session; do not combine it with prior strategies or generate two strategies.
- Return the complete strategy code, concise logic summary, and backtest result in the same language as the user request.
"""


def apply_user_edited_requirement(system_draft_prompt: str, edited_prompt: str) -> str:
    """Accept edits only inside the explicitly editable requirement section.

    The market/news/audit portion of a draft is reproducible context. The
    browser may display the complete prompt, but it must not be able to alter
    those protected sections before they are sent to DreamStrategy.
    """
    draft_start = system_draft_prompt.find(EDITABLE_SECTION_START)
    draft_end = system_draft_prompt.find(EDITABLE_SECTION_END)
    edited_start = edited_prompt.find(EDITABLE_SECTION_START)
    edited_end = edited_prompt.find(EDITABLE_SECTION_END)
    if min(draft_start, draft_end, edited_start, edited_end) < 0:
        raise ValueError("Prompt is missing its editable requirement section")

    draft_prefix = system_draft_prompt[: draft_start + len(EDITABLE_SECTION_START)]
    draft_suffix = system_draft_prompt[draft_end:]
    edited_prefix = edited_prompt[: edited_start + len(EDITABLE_SECTION_START)]
    edited_suffix = edited_prompt[edited_end:]
    if draft_prefix != edited_prefix or draft_suffix != edited_suffix:
        raise ValueError("News references, scope, and audit text are protected")

    requirement = "\n".join(
        line.rstrip() for line in edited_prompt[edited_start + len(EDITABLE_SECTION_START):edited_end].strip().splitlines()
    ).strip()
    if not requirement:
        raise ValueError("Strategy requirement must not be empty")
    if len(requirement) > 2000:
        raise ValueError("Strategy requirement must not exceed 2000 characters")
    return f"{draft_prefix}\n{requirement}\n{draft_suffix}"

def build_dream_strategy_prompt(
    requirement: str,
    lookback_days: int = 7,
    model_name: Optional[str] = None,
) -> dict[str, Any]:
    """Build the real DreamStrategy prompt without calling the external service."""

    normalized_requirement = " ".join(requirement.split())
    if not normalized_requirement:
        raise ValueError("策略需求不能为空")
    instrument = _resolve_instrument(normalized_requirement)
    context = build_sentiment_strategy_context(lookback_days, model_name, instrument.market_scope)
    counts = context["news_sentiment"]["counts"]
    conclusion, action = _sentiment_guidance(counts, instrument.market_scope)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    values = {
        "USER_REQUIREMENT": f"{EDITABLE_SECTION_START}\n{normalized_requirement}\n{EDITABLE_SECTION_END}",
        "MARKET_AS_OF": context["reference_time"].strftime("%Y-%m-%d %H:%M"),
        "INSTRUMENT": instrument.name,
        "FREQUENCY": DEFAULT_FREQUENCY,
        "MARKET_SCOPE": instrument.market_scope.label,
        "MARKET_TECHNICAL_STATE": TECHNICAL_STATE,
        "YIELD_CURVE_SUMMARY": _format_yields(context["yield_curve"], instrument.market_scope),
        "REPORT_GENERATED_AT": context["generated_at"],
        "WINDOW_START": context["window_start"].strftime("%Y-%m-%d %H:%M"),
        "WINDOW_END": context["reference_time"].strftime("%Y-%m-%d %H:%M"),
        "WINDOW_DAYS": str(context["lookback_days"]),
        "ANALYSIS_MODEL": context["model_name"],
        "DIRECTIONAL_EVENT_COUNT": str(counts["positive"] + counts["negative"]),
        "POSITIVE_EVENT_COUNT": str(counts["positive"]),
        "NEGATIVE_EVENT_COUNT": str(counts["negative"]),
        "SHORT_HORIZON_COUNT": str(context["news_sentiment"]["horizons"].get("短期", 0)),
        "REPRESENTATIVE_EVENTS": _format_events(context["events"]),
        "POSITIVE_FACTORS": _format_factors(context["factors"]["positive"]),
        "NEGATIVE_FACTORS": _format_factors(context["factors"]["negative"]),
        "YIELD_CURVE_DETAIL": _format_yields(context["yield_curve"], instrument.market_scope),
        "SENTIMENT_CONCLUSION": conclusion,
        "SENTIMENT_STRATEGY_ACTION": action,
    }
    prompt = template
    for key, value in values.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", value)
    context.update(
        {
            "user_requirement": normalized_requirement,
            "prompt": prompt,
            "quant_message": {"role": "user", "content": prompt},
            "prompt_version": "sentiment-strategy-chat-v2-instrument-scoped",
            "instrument": instrument.name,
            "frequency": DEFAULT_FREQUENCY,
        }
    )
    return context
