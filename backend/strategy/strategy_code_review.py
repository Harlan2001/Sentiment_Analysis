"""生成代码的发送前/回收后静态检查。

回测平台只看进程退出码，而实测（2026-10-30 会话 #60 之前的 25 个历史模板，
21 个零成交）表明模型最常见的两类废稿，在回测跑起来之前就能从代码本身拦住：

1. **演示稿**：逻辑齐全、有信号判断，但动作全部是 ``Debug``/``print``/日志记录，
   一次真实下单接口都不调——历史样本注释里甚至自陈"以信号日志形式呈现交易指令"。
2. **自陈不下单**：注释或字符串里明确写着"不实际下单/仅打印交易信号/模拟下单"。

本模块只做高置信度拦截。可疑但拿不准的（参数硬编码、保证金比例异常）留给上层
做 advisory 提示，不在此处判废，避免误伤能成交的策略。
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass

# KSAPI / Lean 风格的真实下单接口。self.MarketOrder / self.Buy / order 等。
# 匹配不区分大小写，既认 ``self.MarketOrder(...)`` 也认模块级 ``buy(...)``。
ORDER_PLACEMENT_METHODS = frozenset(
    {
        "marketorder",
        "limitorder",
        "stopmarketorder",
        "stoplimitorder",
        "buy",
        "sell",
        "short",
        "cover",
        "setholdings",
        "order",
        "ordertarget",
        "submitorderrequest",
        "placeorder",
    }
)

# 肯定性的"演示稿"自陈。命中这些短语意味着代码自己声明了不会真实下单。
# 刻意保守："POC""演示"这类词单独出现不判（真实下单的策略注释里也会写
# "舆情门控（POC 静态快照）"），必须与"日志/打印/模拟/不实际"等语义共现。
_DEMO_STATEMENT_PATTERNS = (
    r"信号日志形式",
    r"日志形式(?:呈现|展示|模拟)?(?:交易|下单|买卖)?(?:指令|信号)?",
    r"仅(?:仅)?(?:打印|输出|记录)(?:交易)?(?:信号|指令|日志)",
    r"只(?:是)?(?:打印|输出|记录)(?:交易)?(?:信号|指令|日志)",
    r"不(?:进行|触发|发起|做)(?:真实|实际)?(?:下单|交易|买卖)",
    r"不(?:会|做)(?:真实|实际)?成交",
    r"(?:以|用)日志(?:来)?模拟(?:下单|交易|成交)",
    r"模拟(?:下单|交易)(?:[，,。；;].*)?(?:不|仅)",
    r"不(?:走|通过)(?:真实)?下单链路",
)
_DEMO_STATEMENT_RE = re.compile("|".join(_DEMO_STATEMENT_PATTERNS))

# 命中短语的句子里若出现这些否定/禁令词，说明是在复述任务卡的要求
# （"禁止只打印信号日志"），不是自陈，必须放行。
_NEGATION_MARKERS = ("禁止", "不得", "不准", "不要", "不能", "不应", "严禁", "勿")


@dataclass(frozen=True)
class CodeReviewResult:
    """静态检查结论。ok=False 时 reason 可直接展示与回灌重生。"""

    ok: bool
    reason: str = ""
    evidence: str = ""
    syntactically_valid: bool = True


def _statement_spans(tree: ast.AST, source: str) -> list[str]:
    """提取注释与字符串字面量文本，按句切分用于自陈短语扫描。"""

    spans: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            spans.append(node.value)
    # tokenize 能同时拿到注释和字符串，且不用自己处理引号/编码边界。
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                spans.append(token.string.lstrip("#").strip())
    except tokenize.TokenError:
        # 源码若有奇特截断，注释扫描可以放弃；AST 结论不受影响。
        pass
    return spans


def _has_order_placement(tree: ast.AST) -> bool:
    """AST 层面判断是否存在真实下单调用（注释/字符串里的文字不会命中）。"""

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        if name and name.lower() in ORDER_PLACEMENT_METHODS:
            return True
    return False


def _find_demo_statement(tree: ast.AST, source: str) -> str:
    """返回命中的自陈原句；没有则返回空串。含否定/禁令词的句子放行。"""

    for text in _statement_spans(tree, source):
        for raw_sentence in re.split(r"[\n。；;]", text):
            sentence = raw_sentence.strip()
            if not sentence:
                continue
            matched = _DEMO_STATEMENT_RE.search(sentence)
            if not matched:
                continue
            if any(marker in sentence for marker in _NEGATION_MARKERS):
                continue
            return sentence[:120]
    return ""


def review_generated_code(code: str) -> CodeReviewResult:
    """检查模型生成的 KSAPI Python 代码是否为会真实下单的策略。

    解析失败不武断判废（回测平台本身会再报语法错，走 backtest_failed 分支），
    但会在结论里标明语法不可解析，供上层决定。
    """

    text = str(code or "")
    if not text.strip():
        return CodeReviewResult(ok=False, reason="生成代码为空", evidence="")

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return CodeReviewResult(
            ok=False,
            reason=f"生成代码存在语法错误：{exc.msg}",
            evidence=f"line {exc.lineno}",
            syntactically_valid=False,
        )

    demo_statement = _find_demo_statement(tree, text)
    if demo_statement:
        return CodeReviewResult(
            ok=False,
            reason="代码自陈为只记录信号、不真实下单的演示稿",
            evidence=demo_statement,
        )

    if not _has_order_placement(tree):
        return CodeReviewResult(
            ok=False,
            reason="代码没有调用任何真实下单接口（如 MarketOrder/Buy/Sell），只打印或记录信号",
        )

    return CodeReviewResult(ok=True)
