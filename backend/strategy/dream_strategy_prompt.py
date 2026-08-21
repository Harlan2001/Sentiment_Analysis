"""Build DreamStrategy prompts from instrument-scoped Sentiment intelligence."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from backend.strategy.sentiment_context import (
    MarketContextScope,
    build_sentiment_strategy_context,
)

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
TRADING_PARAMETERS_START = "[TRADING_PARAMETERS]"
TRADING_PARAMETERS_END = "[/TRADING_PARAMETERS]"

# Defaults keep even a broad request runnable on its first attempt.
# They remain in the user-editable section and are rendered as form fields.
DEFAULT_TRADING_PARAMETERS = (
    ("开仓规则", "5日均线上穿20日均线，且收盘价站上20日均线"),
    ("平仓规则", "5日均线跌破20日均线，或触发止盈止损"),
    ("单笔仓位", "20%资金"),
    ("止损", "1.5%"),
    ("止盈", "3.0%"),
    ("回测区间", "最近2年"),
    ("信号频率", "日频"),
)


def _default_trading_parameters() -> str:
    return "\n".join(f"- {name}：{value}" for name, value in DEFAULT_TRADING_PARAMETERS)


# News retrieval only needs a market *category* (gold vs bond), never a specific
# instrument. Hard-coding a three-instrument whitelist here produced prompts whose
# declared instrument contradicted the user's own words; the actual tradeable
# instrument is Dream AI's decision, guided by the user's verbatim requirement.
GOLD_SCOPE = MarketContextScope(
    label="黄金市场",
    news_keywords=("黄金", "金价", "贵金属", "现货金"),
    directional_trade_guidance=False,
    include_yield_curve=False,
)
BOND_SCOPE = MarketContextScope(
    label="债券市场",
    news_keywords=("国债", "债券", "收益率", "货币政策"),
    directional_trade_guidance=True,
    include_yield_curve=True,
)
DEFAULT_SCOPE = BOND_SCOPE

_GOLD_KEYWORDS = ("黄金", "金价", "贵金属", "现货金")
# Words that mark a gold mention as excluded ("除...黄金外") rather than requested.
_NEGATION_MARKERS = ("除", "除了", "除外", "排除", "不要", "剔除")


def _resolve_market_scope(requirement: str) -> MarketContextScope:
    """Resolve only the news universe (gold vs bond), never a specific instrument.

    The specific tradeable instrument is Dream AI's decision, guided by the
    user's own requirement text which is passed through verbatim.
    """

    text = "".join(requirement.split())
    if not any(keyword in text for keyword in _GOLD_KEYWORDS):
        return BOND_SCOPE
    first_gold = min(text.index(k) for k in _GOLD_KEYWORDS if k in text)
    if any(marker in text[:first_gold] for marker in _NEGATION_MARKERS):
        return BOND_SCOPE
    return GOLD_SCOPE


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


def _sentiment_guidance(
    counts: dict[str, int], scope: MarketContextScope
) -> tuple[str, str]:
    if not scope.directional_trade_guidance:
        return (
            f"已仅按{scope.label}检索新闻；原有方向标签不直接等同于{scope.label}多空。",
            "新闻仅用于风险提示、信号过滤或提高开仓阈值，不单独决定交易方向。",
        )
    if counts["positive"] > counts["negative"]:
        return f"利多{scope.label}信号占优", "将新闻仅用于方向确认或降低开仓阈值"
    if counts["negative"] > counts["positive"]:
        return (
            f"利空{scope.label}信号占优",
            "将新闻仅用于空头方向确认、提高开仓阈值或风险降级",
        )
    return f"利多与利空{scope.label}信号均衡或不足", "不以新闻形成方向，必要时暂停交易"


# Execution rules that apply to every strategy generation, including the first
# one. The template owns the output contract: the actual strategy version, not
# chat text, is the source for the four front-end result modules.
_COMMON_EXECUTION_RULES = """- Execute the formal-result workflow in the template: create or update the actual strategy version, write its code and concise summary, then run its backtest to a terminal result.
- Do not use ordinary chat text as a result carrier. It must contain no planning, self-talk, deliberation, code draft, code block, strategy summary, backtest metric, or backtest log.
- The current Sentiment news analysis above is a fresh snapshot for this version. Use its representative events as auditable news references for this strategy version.
- Broad requests such as "随便生成一个策略" are valid. When no instrument or detailed objective is supplied, use the prompt's default instrument and conservative trading parameters to generate and backtest one complete runnable strategy; do not ask a follow-up merely because the user left the choice to you.
- If the user has named an instrument and objective but omitted ordinary execution parameters, use conservative, explicit defaults (including signal window, position size, stop loss, take profit, and test period) so that a complete, runnable strategy can be generated and backtested now. List those defaults in the strategy summary.
- Store the strategy code, concise logic summary, backtest metrics, and backtest log on the formal strategy version for separate front-end display. Do not duplicate them in a chat reply."""

# Rules that only make sense when continuing an already-existing Dream session.
_CONTINUATION_EXECUTION_RULES = """- Continue the existing DreamStrategy session.
- Existing strategy versions are already complete. Do not reopen, regenerate, or ask about their parameters unless the latest request explicitly asks to modify them.
- If the latest request asks for another strategy, generate only that newly requested strategy as the next version in this same session; do not combine it with prior strategies or generate two strategies."""


def build_dream_strategy_continuation_prompt(market_prompt: str) -> str:
    """Add continuation rules to a freshly-built market-aware strategy prompt."""

    if not market_prompt.strip():
        raise ValueError("Market-aware strategy prompt must not be empty")
    return f"""{market_prompt}

[EXECUTION RULES]
{_CONTINUATION_EXECUTION_RULES}
{_COMMON_EXECUTION_RULES}
"""


def build_dream_strategy_first_prompt(market_prompt: str) -> str:
    """Add execution rules to the first strategy prompt of a new session.

    The first generation used to send the bare template without these rules,
    which let Dream return a planning-only or malformed reply (and the summary
    field then carried the code). The common rules apply to the first turn too;
    only the continuation-specific rules are omitted because there is no
    existing session to continue.
    """

    if not market_prompt.strip():
        raise ValueError("Market-aware strategy prompt must not be empty")
    return f"""{market_prompt}

[EXECUTION RULES]
{_COMMON_EXECUTION_RULES}
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
        line.rstrip()
        for line in edited_prompt[
            edited_start + len(EDITABLE_SECTION_START) : edited_end
        ]
        .strip()
        .splitlines()
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
    scope = _resolve_market_scope(normalized_requirement)
    context = build_sentiment_strategy_context(
        lookback_days, model_name, scope
    )
    counts = context["news_sentiment"]["counts"]
    conclusion, action = _sentiment_guidance(counts, scope)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    values = {
        "USER_REQUIREMENT": (
            f"{EDITABLE_SECTION_START}\n{TRADING_PARAMETERS_START}\n"
            f"{_default_trading_parameters()}\n{TRADING_PARAMETERS_END}\n\n"
            f"[STRATEGY_REQUIREMENT]\n{normalized_requirement}\n"
            f"[/STRATEGY_REQUIREMENT]\n{EDITABLE_SECTION_END}"
        ),
        "MARKET_AS_OF": context["reference_time"].strftime("%Y-%m-%d %H:%M"),
        "FREQUENCY": DEFAULT_FREQUENCY,
        "MARKET_SCOPE": scope.label,
        "MARKET_TECHNICAL_STATE": TECHNICAL_STATE,
        "YIELD_CURVE_SUMMARY": _format_yields(
            context["yield_curve"], scope
        ),
        "REPORT_GENERATED_AT": context["generated_at"],
        "WINDOW_START": context["window_start"].strftime("%Y-%m-%d %H:%M"),
        "WINDOW_END": context["reference_time"].strftime("%Y-%m-%d %H:%M"),
        "WINDOW_DAYS": str(context["lookback_days"]),
        "ANALYSIS_MODEL": context["model_name"],
        "DIRECTIONAL_EVENT_COUNT": str(counts["positive"] + counts["negative"]),
        "POSITIVE_EVENT_COUNT": str(counts["positive"]),
        "NEGATIVE_EVENT_COUNT": str(counts["negative"]),
        "SHORT_HORIZON_COUNT": str(
            context["news_sentiment"]["horizons"].get("短期", 0)
        ),
        "REPRESENTATIVE_EVENTS": _format_events(context["events"]),
        "POSITIVE_FACTORS": _format_factors(context["factors"]["positive"]),
        "NEGATIVE_FACTORS": _format_factors(context["factors"]["negative"]),
        "YIELD_CURVE_DETAIL": _format_yields(
            context["yield_curve"], scope
        ),
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
            "instrument": scope.label,
            "frequency": DEFAULT_FREQUENCY,
        }
    )
    return context
