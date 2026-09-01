"""LLM JSON 输出解析工具。

统一各分析模块对 LLM 返回文本的提取与清洗逻辑：
1. 剥离 fenced code block（```json ... ```）与前后废话
2. 清理尾随逗号等常见 JSON 不合规问题
"""

import json
import re
from typing import Any, Dict

_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def sanitize_json(text: str) -> str:
    """清理 LLM 返回文本中常见的 JSON 不合规问题（尾随逗号等）。"""
    if not text:
        return ""
    return _TRAILING_COMMA_RE.sub(r"\1", text)


def extract_json_string(content: str) -> str:
    """提取 LLM 输出中最外层 JSON 对象文本。

    无视代码块标记与前后缀解释文字；无 JSON 结构时返回空字符串。
    """
    if not content:
        return ""

    # 移除代码块标记
    cleaned = re.sub(r"```json|```", "", content).strip()

    # 提取第一个 { ... } 结构（无视前后废话）
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return ""
    return sanitize_json(match.group().strip())


def extract_json(text: str) -> Dict[str, Any]:
    """提取并以字典解析 LLM 返回文本中的 JSON 对象。

    提取/清洗逻辑见 extract_json_string；未找到 JSON 或解析失败时抛出
    带上下文提示的 json.JSONDecodeError。
    """
    json_str = extract_json_string(text)
    if not json_str:
        raise json.JSONDecodeError("未找到 JSON 对象", text or "", 0)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise json.JSONDecodeError(
            f"AI 返回内容解析 JSON 失败，提取后文本前200字符: {json_str[:200]}",
            exc.doc,
            exc.pos,
        ) from exc