"""Build DreamStrategy prompts from instrument-scoped Sentiment intelligence."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from backend.strategy.sentiment_context import (
    SHORT_HORIZON,
    MarketContextScope,
    build_sentiment_strategy_context,
    format_yield_curve,
    sentiment_dominance,
)
from backend.strategy.signal_panel import (
    DEFAULT_HOLDING_DAYS,
    build_factor_signal_panel,
    format_signal_panel,
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
INSTRUMENT_START = "[INSTRUMENT]"
INSTRUMENT_END = "[/INSTRUMENT]"


# ---------------------------------------------------------------------------
# 交易标的白名单
# ---------------------------------------------------------------------------
# 只允许这些标的，理由见需求文档 §5.1：
# - 全是利率债口径，我们的因子方向（positive = 收益率下行）可直接沿用；
# - FCT_AU_MAIN（黄金）被显式排除——因子方向是债市口径，黄金需另行做方向映射。
# 另外两个实测事实决定了默认值：
# - 唯一被实证跑出成交的是 FCT_T_MAIN（25 个历史模板里 4 个有成交的全部用它）；
# - 对端模型侧不做任何标的合法性校验，写错会一路跑到回测才崩，所以校验必须在这里做。
DEFAULT_INSTRUMENT = "FCT_T_MAIN"

WHITELISTED_INSTRUMENTS: dict[str, str] = {
    "FCT_T_MAIN": "中金所10年期国债期货",
    "100040": "中金所10年期国债期货（别名，同 FCT_T_MAIN）",
    "FCT_TS_MAIN": "中金所2年期国债期货",
    "FCT_TL_MAIN": "中金所30年期国债期货",
    "IBK_G10Y_ACTV": "银行间10Y国债活跃券",
    "IBK_CDB10_ACTV": "银行间10Y国开活跃券",
}

# 副本：一是给前端下拉用，二是把"需要资产方向映射、本期不做"的标的显式记录下来。
EXCLUDED_INSTRUMENTS: dict[str, str] = {
    "FCT_AU_MAIN": "上期所黄金期货（债市口径因子不适用，需另行做方向映射）",
}

DEFAULT_BACKTEST_MODE = "bar"
DEFAULT_CANDLE_INTERVAL = "1d"
BACKTEST_START = "2024-01-01"


def resolve_instrument(
    requirement: str, requested: Optional[str] = None
) -> tuple[str, str]:
    """解析并校验交易标的，返回 ``(code, label)``。

    显式传入的 ``requested`` 必须命中白名单，否则抛 ``ValueError``——这是标的
    合法性的唯一防线（对端模型侧不做校验）。未指定时从需求文本里找，找不到
    就用默认标的。
    """
    if requested:
        code = requested.strip()
        if code in EXCLUDED_INSTRUMENTS:
            raise ValueError(
                f"标的 {code} 本期不支持：{EXCLUDED_INSTRUMENTS[code]}"
            )
        if code not in WHITELISTED_INSTRUMENTS:
            allowed = "、".join(WHITELISTED_INSTRUMENTS)
            raise ValueError(f"标的 {code} 不在白名单内，可选：{allowed}")
        return code, WHITELISTED_INSTRUMENTS[code]

    for code, label in WHITELISTED_INSTRUMENTS.items():
        if code in requirement:
            return code, label
    return DEFAULT_INSTRUMENT, WHITELISTED_INSTRUMENTS[DEFAULT_INSTRUMENT]


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

# Words that mark a gold mention as excluded ("除...黄金外") rather than requested.
_NEGATION_MARKERS = ("除", "除了", "除外", "排除", "不要", "剔除")


def _resolve_market_scope(requirement: str) -> MarketContextScope:
    """Resolve only the news universe (gold vs bond), never a specific instrument.

    The specific tradeable instrument is Dream AI's decision, guided by the
    user's own requirement text which is passed through verbatim.
    """

    gold_keywords = GOLD_SCOPE.news_keywords
    text = "".join(requirement.split())
    if not any(keyword in text for keyword in gold_keywords):
        return BOND_SCOPE
    first_gold = min(text.index(k) for k in gold_keywords if k in text)
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


def _format_yields(yield_curve: list[dict[str, Any]], scope: MarketContextScope) -> str:
    if not scope.include_yield_curve:
        return "本标的不使用债券收益率曲线；价格和技术数据由策略运行时读取。"
    if not yield_curve:
        return "暂无可用收益率数据"
    return format_yield_curve(yield_curve)


def _panel_direction(
    panel_items: list[dict[str, Any]] | None,
) -> tuple[str, int, int]:
    """统计因子面板方向，返回 ("positive"|"negative"|"balanced"|"no_data", 多, 空)。"""
    pos = sum(1 for item in (panel_items or []) if item.get("direction") == "positive")
    neg = sum(1 for item in (panel_items or []) if item.get("direction") == "negative")
    if pos > neg:
        return "positive", pos, neg
    if neg > pos:
        return "negative", pos, neg
    if pos:
        return "balanced", pos, neg
    return "no_data", pos, neg


def _sentiment_guidance(
    counts: dict[str, int],
    scope: MarketContextScope,
    panel_items: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    dominance = sentiment_dominance(counts, scope)
    if dominance == "background_only":
        return (
            f"已仅按{scope.label}检索新闻；原有方向标签不直接等同于{scope.label}多空。",
            "新闻仅用于风险提示、信号过滤或提高开仓阈值，不单独决定交易方向。",
        )

    panel_dominance, f_pos, f_neg = _panel_direction(panel_items)
    news_direction_text = {
        "positive": f"利多{scope.label}信号占优",
        "negative": f"利空{scope.label}信号占优",
        "balanced": f"利多与利空{scope.label}信号均衡",
        "no_data": f"{scope.label}方向新闻不足",
    }
    panel_text = {
        "positive": f"事件研究因子面板偏多（多{f_pos}/空{f_neg}）",
        "negative": f"事件研究因子面板偏空（多{f_pos}/空{f_neg}）",
    }

    # 新闻标签与因子面板严格反向时必须显式标注冲突，否则任务卡自相矛盾
    # （S0 实测：因子面板 7 个全"多"，结论却写"利空占优、空头确认"）。
    if (
        dominance in {"positive", "negative"}
        and panel_dominance in {"positive", "negative"}
        and panel_dominance != dominance
    ):
        forbidden = {"positive": "做空", "negative": "做多"}[panel_dominance]
        return (
            f"信号冲突：新闻标签{news_direction_text[dominance]}，但{panel_text[panel_dominance]}",
            "两类证据口径不同：新闻方向是模型逐条标注，仅作风险过滤；"
            f"因子方向来自历史事件统计检验。冲突时不得按新闻情绪单边{forbidden}，"
            "价格/技术信号是唯一交易触发，因子面板仅作同向门控，"
            "冲突缓解前降低仓位、提高开仓阈值",
        )

    if dominance == "positive":
        return news_direction_text["positive"], "将新闻仅用于方向确认或降低开仓阈值"
    if dominance == "negative":
        return (
            news_direction_text["negative"],
            "将新闻仅用于空头方向确认、提高开仓阈值或风险降级",
        )
    if dominance == "balanced":
        return news_direction_text["balanced"], "不以新闻形成方向，必要时暂停交易"
    # no_data：新闻无方向时，因子面板可以单独给出门控倾向。
    if panel_dominance in {"positive", "negative"}:
        return (
            f"方向新闻不足；{panel_text[panel_dominance]}",
            "不以新闻形成交易方向；价格/技术信号触发，因子面板仅作同向门控",
        )
    return (
        news_direction_text["no_data"],
        "不以新闻形成方向，必要时暂停交易",
    )


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
    instrument_code: Optional[str] = None,
    backtest_mode: str = DEFAULT_BACKTEST_MODE,
    candle_interval: str = DEFAULT_CANDLE_INTERVAL,
) -> dict[str, Any]:
    """Build the real DreamStrategy prompt without calling the external service."""

    normalized_requirement = " ".join(requirement.split())
    if not normalized_requirement:
        raise ValueError("策略需求不能为空")

    instrument_code, instrument_label = resolve_instrument(
        normalized_requirement, instrument_code
    )
    scope = _resolve_market_scope(normalized_requirement)
    context = build_sentiment_strategy_context(lookback_days, model_name, scope)
    counts = context["news_sentiment"]["counts"]

    # 因子信号面板：与新闻上下文共用同一锚点，避免两块情报落在不同时点。
    signal_panel = build_factor_signal_panel(
        reference_time=context["reference_time"],
        model_name=context["model_name"],
        holding_days=DEFAULT_HOLDING_DAYS,
    )
    # 结论必须同时看新闻与因子面板，方向相反时显式标注冲突（S0 实证的自相矛盾）。
    conclusion, action = _sentiment_guidance(counts, scope, signal_panel.get("items"))

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    values = {
        "USER_REQUIREMENT": (
            f"{EDITABLE_SECTION_START}\n{TRADING_PARAMETERS_START}\n"
            f"{_default_trading_parameters()}\n{TRADING_PARAMETERS_END}\n\n"
            f"{INSTRUMENT_START}\n"
            f"- 交易标的：{instrument_code}（{instrument_label}）\n"
            f"- 回测模式：{backtest_mode}\n"
            f"- K线周期：{candle_interval}\n"
            f"{INSTRUMENT_END}\n\n"
            f"[STRATEGY_REQUIREMENT]\n{normalized_requirement}\n"
            f"[/STRATEGY_REQUIREMENT]\n{EDITABLE_SECTION_END}"
        ),
        "INSTRUMENT_CODE": instrument_code,
        "INSTRUMENT_LABEL": instrument_label,
        "BACKTEST_MODE": backtest_mode,
        "CANDLE_INTERVAL": candle_interval,
        "BACKTEST_START": BACKTEST_START,
        "BACKTEST_END": context["reference_time"].strftime("%Y-%m-%d"),
        "MARKET_AS_OF": context["reference_time"].strftime("%Y-%m-%d %H:%M"),
        "FREQUENCY": DEFAULT_FREQUENCY,
        "MARKET_SCOPE": scope.label,
        "MARKET_TECHNICAL_STATE": TECHNICAL_STATE,
        "YIELD_CURVE_SUMMARY": _format_yields(context["yield_curve"], scope),
        "REPORT_GENERATED_AT": context["generated_at"],
        "WINDOW_START": context["window_start"].strftime("%Y-%m-%d %H:%M"),
        "WINDOW_END": context["reference_time"].strftime("%Y-%m-%d %H:%M"),
        "WINDOW_DAYS": str(context["lookback_days"]),
        "ANALYSIS_MODEL": context["model_name"],
        "DIRECTIONAL_EVENT_COUNT": str(counts["positive"] + counts["negative"]),
        "POSITIVE_EVENT_COUNT": str(counts["positive"]),
        "NEGATIVE_EVENT_COUNT": str(counts["negative"]),
        "SHORT_HORIZON_COUNT": str(
            context["news_sentiment"]["horizons"].get(SHORT_HORIZON, 0)
        ),
        "REPRESENTATIVE_EVENTS": _format_events(context["events"]),
        "FACTOR_SIGNAL_PANEL": format_signal_panel(signal_panel),
        "YIELD_CURVE_DETAIL": _format_yields(context["yield_curve"], scope),
        "SENTIMENT_CONCLUSION": conclusion,
        "SENTIMENT_STRATEGY_ACTION": action,
    }
    prompt = template
    for key, value in values.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", value)

    token_used = estimate_message_tokens(prompt)
    if token_used > PROMPT_TOKEN_BUDGET:
        # 超限对端会直接报错且无截断，这里提前暴露问题而不是等远端拒绝。
        raise ValueError(
            f"策略提示词超出预算：{token_used}/{PROMPT_TOKEN_BUDGET} token，"
            "请缩短需求或减少回测区间描述"
        )

    context.update(
        {
            "user_requirement": normalized_requirement,
            "prompt": prompt,
            "prompt_version": "sentiment-intel-pack-v1",
            "instrument": instrument_label,
            "instrument_code": instrument_code,
            "backtest_mode": backtest_mode,
            "candle_interval": candle_interval,
            "frequency": DEFAULT_FREQUENCY,
            "factor_panel": signal_panel,
            "token_used": token_used,
            "token_budget": PROMPT_TOKEN_BUDGET,
        }
    )
    return context


# 提示词预算：对端上限 10,000 token（中文约 6,666 字，超限直接报错、无截断），
# 留出系统提示词与模型输出的余量后取 6,000 token（约 4,000 汉字）。
PROMPT_TOKEN_BUDGET = 6000


def estimate_message_tokens(text: str) -> int:
    """与对端 ``EstimateTokenCount`` 一致的 token 估算。

    ASCII 每字符记 1、三字节汉字每字记 6，最后整体除以 4，因此
    1 个汉字 ≈ 1.5 token。这里复刻同一算法，确保我方预算判断与对端一致。
    """

    raw = text.encode("utf-8")
    total = 0
    index = 0
    length = len(raw)
    while index < length:
        byte = raw[index]
        if byte & 0x80 == 0:
            total += 1
            index += 1
        elif byte & 0xE0 == 0xC0:
            total += 4
            index += 2
        elif byte & 0xF0 == 0xE0:
            total += 6
            index += 3
        elif byte & 0xF8 == 0xF0:
            total += 8
            index += 4
        else:
            index += 1
    return total // 4
