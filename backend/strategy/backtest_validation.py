"""策略回测的验收门。

平台对"回测通过"的口径是"回测进程正常退出"，**0 成交也算通过**（源码注释原文
``total_trade_count=0 is OK``）。实测 25 个历史模板里 21 个 0 成交但全部 passed，
其中我们正在用的那个甚至只打印信号日志、一次下单接口都没调。

所以必须由我们自己再判一道，且要区分三种失败——它们的处置完全不同：
失败/异常都不值得重试，只有"跑完了但没成交"才该带着原因让模型重生。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

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

# 建议的最低成交笔数（按每年），低于此值视为策略没有真正运转。
MIN_TRADES_PER_YEAR = 10


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

    @property
    def passed(self) -> bool:
        return self.verdict == VERDICT_PASSED

    @property
    def retryable(self) -> bool:
        """只有"无成交"值得带原因重生；回测失败/异常重试也不会变好。"""
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

    # ② 日志里能否解析到成交笔数。
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

    # ③ 成交笔数是否为正。
    traded = trade_count > 0
    steps.append(
        ValidationStep(
            "trade_count_positive",
            traded,
            f"成交 {trade_count} 笔",
        )
    )

    # 附加：标的是否在白名单内。
    symbol_ok = True
    if whitelist:
        symbol_ok, symbol_detail = _check_symbol_whitelist(code, whitelist)
        steps.append(ValidationStep("symbol_whitelisted", symbol_ok, symbol_detail))
    result_obj.symbol_whitelisted = symbol_ok

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

    if mismatch:
        result_obj.verdict = VERDICT_BACKTEST_ERROR
        result_obj.reason = "下单类型与标的类型不匹配（期货标的用了现券下单类型）"
        return result_obj

    if not traded:
        result_obj.verdict = VERDICT_NO_TRADE
        result_obj.reason = f"回测正常结束但成交 {trade_count} 笔，策略未真实运转"
        return result_obj

    if not symbol_ok:
        result_obj.verdict = VERDICT_BACKTEST_ERROR
        result_obj.reason = "策略使用的标的不在任务卡白名单内"
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
        "1）必须真实调用下单接口建立和了结仓位；"
        "2）禁止只打印信号日志、禁止做成不下单的演示稿；"
        "3）交易标的必须沿用任务卡指定的品种，不得更换；"
        "4）回测必须产生真实成交记录。"
    )
    if snippet.strip():
        lines.append("回测日志摘要：")
        lines.append(snippet.strip())
    return "\n".join(lines)