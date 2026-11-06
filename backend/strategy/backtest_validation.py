"""策略回测的验收门。

平台对"回测通过"的口径是"回测进程正常退出"，**0 成交也算通过**（源码注释原文
``total_trade_count=0 is OK``）。实测 25 个历史模板里 21 个 0 成交但全部 passed，
其中我们正在用的那个甚至只打印信号日志、一次下单接口都没调。

2026-10-30 会话 #60 又暴露第二种假阳性：``Total Orders 29`` 但 Average Win/Loss
均为 0%、换手率 0%、净利润 0.000%——订单提交了却没有任何真实成交盈亏（废单/未
撮合）。所以"订单数"也不等于成交，必须再查成交的经济实质。

所以必须由我们自己再判一道，且要区分三种失败——它们的处置完全不同：
失败/异常默认不值得重试，只有"跑完了但没成交/成交无实质/演示稿"才带原因重生。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from backend.strategy.strategy_code_review import review_generated_code

# 判定结论，前端据此选徽章文案，不自行推断。
VERDICT_PASSED = "passed"
VERDICT_NO_TRADE = "no_trade"
VERDICT_BACKTEST_FAILED = "backtest_failed"
VERDICT_BACKTEST_ERROR = "backtest_error"

# 回测控制台里的成交笔数行，例如 ``成交笔数: 27``。
# 注意这行只在回测成功的分支才打印，所以"解析不到"必须和"等于 0"分开判。
_TRADE_COUNT_PATTERN = re.compile(r"成交笔数\s*[:：]\s*(-?\d+)")
# 回退取值：Lean 标准输出里始终有 ``STATISTICS:: Total Orders 29``。
# 对端只有部分分支会打印中文结果块，没有回退会把「回测成功且有成交」误判成异常。
_TOTAL_ORDERS_PATTERN = re.compile(r"STATISTICS::\s*Total Orders\s+(-?\d+)")
# 下单类型错配的典型痕迹：现券买卖类型（XBOND）下到期货品种上。
_XBOND_PATTERN = re.compile(r"BusinessType\.XBOND")
_FUTURES_HINT_PATTERN = re.compile(r"FCT_|CFFEX|期货|\.CFFEX", re.IGNORECASE)

# FCT_T_MAIN 与代码 100040 是同一品种的两个别名，指定标的校验时互通。
_INSTRUMENT_ALIASES: dict[str, frozenset[str]] = {
    "FCT_T_MAIN": frozenset({"FCT_T_MAIN", "100040"}),
    "100040": frozenset({"FCT_T_MAIN", "100040"}),
}


def _statistic_pattern(label: str) -> re.Pattern[str]:
    # 不锚行尾：对端日志的 STATISTICS 行可能粘连在同一行。
    return re.compile(r"STATISTICS::\s*" + re.escape(label) + r"\s+(-?[\d,]+(?:\.\d+)?)(\s*%)?")


# 废单判定需要的指标。百分比指标带 %，数值指标不带。
_STATISTIC_FIELDS = (
    "avg_win",
    "Average Win",
    True,
), (
    "avg_loss",
    "Average Loss",
    True,
), (
    "net_profit_pct",
    "Net Profit",
    True,
), (
    "turnover_pct",
    "Portfolio Turnover",
    True,
), (
    "win_rate_pct",
    "Win Rate",
    True,
), (
    "loss_rate_pct",
    "Loss Rate",
    True,
)


def _extract_statistics(backtest_log: str) -> dict[str, float | None]:
    """从 Lean STATISTICS 块提取废单判定所需指标；缺失即 None（证据不足不判）。"""
    metrics: dict[str, float | None] = {}
    for key, label, _is_percent in _STATISTIC_FIELDS:
        match = _statistic_pattern(label).search(backtest_log)
        if not match:
            metrics[key] = None
            continue
        try:
            metrics[key] = float(match.group(1).replace(",", ""))
        except ValueError:
            metrics[key] = None
    return metrics


def _detect_ghost_orders(
    trade_count: int, statistics: dict[str, float | None]
) -> tuple[bool, str]:
    """订单数 > 0 但没有真实成交盈亏时判为废单。

    只在指标确实存在时下结论（指标缺失视为证据不足，保持既有行为），
    满足任一证据链即判废单：
    A. 平均盈利/亏损全是 0%，但存在胜率统计——说明平仓被记录了却没有盈亏；
    B. 换手率 0% 且净利润约等于 0——订单从未形成真实持仓周转。
    """
    if trade_count <= 0:
        return False, ""
    avg_win = statistics.get("avg_win")
    avg_loss = statistics.get("avg_loss")
    win_rate = statistics.get("win_rate_pct")
    loss_rate = statistics.get("loss_rate_pct")
    if avg_win is not None and avg_loss is not None:
        has_rate = (win_rate is not None and win_rate > 0) or (
            loss_rate is not None and loss_rate > 0
        )
        if has_rate and abs(avg_win) < 0.005 and abs(avg_loss) < 0.005:
            return True, "平均盈利与平均亏损均为 0%（订单无真实成交盈亏）"
    turnover = statistics.get("turnover_pct")
    net_profit = statistics.get("net_profit_pct")
    if turnover is not None and net_profit is not None:
        if turnover < 0.005 and abs(net_profit) < 0.01:
            return True, "组合换手率 0% 且净利润 0.00%（订单未形成真实持仓周转）"
    return False, ""


@dataclass
class ValidationStep:
    """验收门的一步判定。"""

    step: str
    ok: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"step": self.step, "ok": self.ok, "detail": self.detail}


@dataclass
class ValidationResult:
    """一次验收的完整结论。"""

    verdict: str
    steps: list[ValidationStep] = field(default_factory=list)
    trade_count: int | None = None
    raw_trade_line: str | None = None
    symbol_whitelisted: bool = True
    reason: str = ""
    # 默认只有 no_trade 可重生；标的不符这类"模型能修"的错误可显式打开。
    force_retryable: bool | None = None

    @property
    def passed(self) -> bool:
        return self.verdict == VERDICT_PASSED

    @property
    def retryable(self) -> bool:
        """只有"无成交/可修正的代码问题"值得带原因重生；平台级失败重试无用。"""
        if self.force_retryable is not None:
            return self.force_retryable
        return self.verdict == VERDICT_NO_TRADE

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "passed": self.passed,
            "retryable": self.retryable,
            "steps": [step.to_dict() for step in self.steps],
            "trade_count": self.trade_count,
            "raw_trade_line": self.raw_trade_line,
            "symbol_whitelisted": self.symbol_whitelisted,
            "reason": self.reason,
        }


def _find_trade_line(backtest_log: str) -> tuple[int | None, str | None]:
    """从回测日志里取成交笔数，返回 ``(笔数, 原始行)``。

    优先读中文结果块的「成交笔数」，读不到时回退到 Lean 标准输出的
    ``STATISTICS:: Total Orders``。后者始终存在，避免把「回测成功且有成交」
    误判为异常——实测 version 26 就是 passed=1、Total Orders=29，但没有中文块。
    """
    for line in backtest_log.splitlines():
        matched = _TRADE_COUNT_PATTERN.search(line)
        if matched:
            try:
                return int(matched.group(1)), line.strip()
            except ValueError:
                return None, line.strip()

    for line in backtest_log.splitlines():
        matched = _TOTAL_ORDERS_PATTERN.search(line)
        if matched:
            try:
                return int(matched.group(1)), line.strip()
            except ValueError:
                continue
    return None, None


def _detect_order_type_mismatch(code: str) -> bool:
    """期货标的上用了现券下单类型，属于逻辑错误，不该当成功结果展示。"""
    if not code:
        return False
    return bool(_XBOND_PATTERN.search(code)) and bool(_FUTURES_HINT_PATTERN.search(code))


# 代码里可能出现的交易品种代码形态，用于判断"策略实际用了什么标的"。
_INSTRUMENT_TOKEN_PATTERN = re.compile(
    r"\b(FCT_[A-Z0-9_]+|IBK_[A-Z0-9_]+|1\d{5})\b"
)


def _instruments_used_in_code(code: str) -> set[str]:
    """从策略代码里扫出实际出现的标的代码。"""
    if not code:
        return set()
    return set(_INSTRUMENT_TOKEN_PATTERN.findall(code))


def _check_symbol_whitelist(
    code: str, whitelist: set[str] | frozenset[str]
) -> tuple[bool, str]:
    """检查代码里出现的标的是否都在白名单内。

    代码可能通过 parameters 传入标的而不在文本中出现，这种情况不判失败——
    我们只在"明确用了白名单之外的标的"时才拦，避免误伤合法写法。
    """
    used = _instruments_used_in_code(code)
    if not used:
        return True, "代码中未直接出现标的代码（可能通过参数传入）"
    disallowed = sorted(item for item in used if item not in whitelist)
    if disallowed:
        return False, f"代码使用了白名单之外的标的：{'、'.join(disallowed)}"
    return True, f"标的均在白名单内：{'、'.join(sorted(used))}"


def validate_strategy_result(
    result: dict[str, Any],
    expected_instrument: str | None = None,
    whitelist: set[str] | frozenset[str] | None = None,
) -> ValidationResult:
    """对一次 DreamStrategy 生成结果执行我方验收。

    :param result: ``generate_strategy`` 的返回字典。
    :param expected_instrument: 任务卡里指定给模型的标的。
    :param whitelist: 允许的标的集合；传入时会对代码做包含性检查。
    """
    strategy = result.get("strategy") or {}
    code = str(strategy.get("code") or "")
    backtest_log = str(result.get("backtest_summary") or "")
    exit_code = result.get("backtest_exit_code")
    passed_flag = result.get("backtest_passed")

    steps: list[ValidationStep] = []
    result_obj = ValidationResult(verdict=VERDICT_BACKTEST_ERROR, steps=steps)

    # ① 回测是否正常结束。
    finished = bool(passed_flag) and isinstance(exit_code, int) and exit_code >= 0
    steps.append(
        ValidationStep(
            "backtest_finished",
            finished,
            f"passed={passed_flag}, exit_code={exit_code}",
        )
    )
    if not finished:
        result_obj.verdict = VERDICT_BACKTEST_FAILED
        result_obj.reason = "回测未正常结束，平台未给回测通过状态"
        return result_obj

    # ② 代码静态检查：演示稿/只打印不下单在回测之前就能判定，无需再看成交。
    review = review_generated_code(code)
    steps.append(
        ValidationStep(
            "code_places_real_orders",
            review.ok,
            review.reason if not review.ok else "代码包含真实下单调用",
        )
    )
    if not review.ok and review.syntactically_valid:
        result_obj.verdict = VERDICT_NO_TRADE
        result_obj.reason = review.reason + (f"（代码原句：{review.evidence}）" if review.evidence else "")
        return result_obj
    if not review.ok:
        result_obj.verdict = VERDICT_BACKTEST_ERROR
        result_obj.force_retryable = True
        result_obj.reason = review.reason
        return result_obj

    # ③ 日志里能否解析到成交笔数。
    trade_count, raw_line = _find_trade_line(backtest_log)
    parsed = trade_count is not None
    steps.append(
        ValidationStep(
            "trade_count_parsed",
            parsed,
            raw_line or "日志中未找到「成交笔数」行",
        )
    )
    result_obj.trade_count = trade_count
    result_obj.raw_trade_line = raw_line
    if not parsed:
        result_obj.verdict = VERDICT_BACKTEST_ERROR
        result_obj.reason = (
            "回测日志中没有成交笔数记录，无法判定策略是否真实运转"
        )
        return result_obj

    # ④ 成交笔数是否为正。
    traded = trade_count > 0
    steps.append(
        ValidationStep(
            "trade_count_positive",
            traded,
            f"成交 {trade_count} 笔",
        )
    )
    if not traded:
        result_obj.verdict = VERDICT_NO_TRADE
        result_obj.reason = f"回测正常结束但成交 {trade_count} 笔，策略未真实运转"
        return result_obj

    # ⑤ 成交的经济实质：订单数 >0 不等于真实成交（会话 #60：29 单全是废单）。
    statistics = _extract_statistics(backtest_log)
    ghost, ghost_detail = _detect_ghost_orders(trade_count, statistics)
    steps.append(
        ValidationStep(
            "fills_have_economic_value",
            not ghost,
            "订单存在真实成交盈亏" if not ghost else ghost_detail,
        )
    )
    if ghost:
        result_obj.verdict = VERDICT_NO_TRADE
        result_obj.reason = (
            f"提交 {trade_count} 单但没有真实成交盈亏（{ghost_detail}），"
            "订单可能全部废单/未撮合；订单数不等于成交"
        )
        return result_obj

    # 附加：标的是否在白名单内。
    symbol_ok = True
    if whitelist:
        symbol_ok, symbol_detail = _check_symbol_whitelist(code, whitelist)
        steps.append(ValidationStep("symbol_whitelisted", symbol_ok, symbol_detail))
    result_obj.symbol_whitelisted = symbol_ok
    if not symbol_ok:
        result_obj.verdict = VERDICT_BACKTEST_ERROR
        result_obj.reason = "策略使用的标的不在任务卡白名单内"
        return result_obj

    # 附加：是否真的用了任务卡指定的那一个标的（白名单只保证不出圈）。
    if expected_instrument:
        used = _instruments_used_in_code(code)
        accepted = _INSTRUMENT_ALIASES.get(
            expected_instrument, frozenset({expected_instrument})
        )
        if used and not (used & accepted):
            detail = f"任务卡指定 {expected_instrument}，代码实际使用：{'、'.join(sorted(used))}"
            steps.append(ValidationStep("expected_instrument_used", False, detail))
            result_obj.verdict = VERDICT_BACKTEST_ERROR
            result_obj.force_retryable = True
            result_obj.reason = "代码没有使用任务卡指定的标的"
            return result_obj
        steps.append(
            ValidationStep("expected_instrument_used", True, f"使用了指定标的 {expected_instrument}")
        )

    # 附加：下单类型与标的类型是否匹配。
    mismatch = _detect_order_type_mismatch(code)
    if mismatch:
        steps.append(
            ValidationStep(
                "order_type_matched",
                False,
                "期货标的上使用了现券下单类型 BusinessType.XBOND",
            )
        )
        result_obj.verdict = VERDICT_BACKTEST_ERROR
        result_obj.force_retryable = True
        result_obj.reason = "下单类型与标的类型不匹配（期货标的用了现券下单类型）"
        return result_obj

    result_obj.verdict = VERDICT_PASSED
    result_obj.reason = f"回测通过，成交 {trade_count} 笔"
    return result_obj


def build_retry_feedback(validation: ValidationResult, result: dict[str, Any]) -> str:
    """构造带失败原因的重生提示，回灌到同一会话请模型修正。

    只保留必要信息（失败原因 + 回测摘要片段），避免把整个日志塞进去——
    单条消息有 10,000 token 上限，会话也只有 50 条消息。
    """
    summary = str(result.get("backtest_summary") or "")
    snippet = summary[-800:] if len(summary) > 800 else summary
    lines = [
        "上一次生成的策略未通过我方验收，请修正后重新生成。",
        f"验收结论：{validation.verdict}",
        f"失败原因：{validation.reason}",
    ]
    if validation.raw_trade_line:
        lines.append(f"回测成交记录：{validation.raw_trade_line}")
    lines.append(
        "硬性要求（不得违反）："
        "1）必须真实调用下单接口建立和了结仓位，订单必须真实撮合成交；"
        "2）禁止只打印信号日志、禁止做成不下单的演示稿；"
        "3）交易标的必须沿用任务卡指定的品种，不得更换；"
        "4）回测必须产生真实成交记录和非零的成交盈亏——"
        "提交订单但 Average Win/Average Loss 为 0%、换手率为 0% 视为废单，必须修正；"
        "5）检查订单价格、数量、撮合时段与可交易状态，确保订单不会被全部拒单。"
    )
    if snippet.strip():
        lines.append("回测日志摘要：")
        lines.append(snippet.strip())
    return "\n".join(lines)