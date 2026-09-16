"""个人记忆基础版提取规则。

只处理用户原始消息；不读取助手回复、工具结果或项目上下文。
第一版使用可解释的确定性规则，后续可替换为结构化 LLM 提取器。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryCandidate:
    category: str
    normalized_key: str
    title: str
    content: str
    source_type: str
    status: str
    confidence: float


_SENSITIVE_PATTERNS = (
    re.compile(r"(?:密码|口令|验证码|token|access[_ -]?key|secret)\s*[:：=]?\s*\S+", re.I),
    re.compile(r"\b\d{17}[\dXx]\b"),
    re.compile(r"\b(?:\d[ -]?){16,19}\b"),
    re.compile(r"\b1[3-9]\d{9}\b"),
)

_FORGET_PREFIXES = ("忘记", "别记", "不要记得", "删除记忆", "清除记忆")
_EXPLICIT_PREFIXES = ("记住", "请记住", "帮我记住", "以后默认", "今后默认", "以后都")
_INFERRED_MARKERS = ("我喜欢", "我习惯", "我偏好", "我更喜欢", "我长期关注", "我主要关注", "我是", "我从事")


def contains_sensitive_data(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SENSITIVE_PATTERNS)


def _clean_content(text: str) -> str:
    value = " ".join(text.strip().split())
    value = re.sub(r"^(?:请|帮我)?记住[：,:，\s]*", "", value)
    return value.strip("。.!！ ")[:2000]


def _category(content: str) -> str:
    if any(word in content for word in ("回答", "中文", "英文", "结论", "表格", "简洁", "详细", "格式")):
        return "response_preference"
    if any(word in content for word in ("关注", "感兴趣", "研究方向")):
        return "long_term_interest"
    if any(word in content for word in ("必须", "不要", "不能", "注明", "约束")):
        return "personal_constraint"
    return "user_background"


def _title(category: str, content: str) -> str:
    labels = {
        "response_preference": "回答偏好",
        "user_background": "用户背景",
        "long_term_interest": "长期关注",
        "personal_constraint": "长期约束",
    }
    summary = content[:32] + ("…" if len(content) > 32 else "")
    return f"{labels[category]}：{summary}"


def _key(category: str, content: str) -> str:
    if category == "response_preference":
        if "中文" in content or "英文" in content:
            return "response.language"
        if "结论" in content:
            return "response.structure"
        if "简洁" in content or "详细" in content:
            return "response.detail_level"
        if "表格" in content:
            return "response.format"
    digest = hashlib.sha256(content.casefold().encode("utf-8")).hexdigest()[:32]
    return f"{category}:{digest}"


def extract_memory_intent(text: str) -> tuple[str, list[MemoryCandidate]]:
    """返回 ``(intent, candidates)``，intent 为 remember/forget/none。"""
    value = " ".join((text or "").strip().split())
    if not value:
        return "none", []
    if any(value.startswith(prefix) for prefix in _FORGET_PREFIXES):
        query = value
        for prefix in _FORGET_PREFIXES:
            if query.startswith(prefix):
                query = query[len(prefix):]
                break
        query = query.strip("：,:，。.!！ ")
        if not query:
            return "none", []
        candidate = MemoryCandidate(
            category="response_preference",
            normalized_key="forget-query",
            title="忘记个人记忆",
            content=query,
            source_type="explicit_chat",
            status="deleted",
            confidence=1.0,
        )
        return "forget", [candidate]
    explicit = any(value.startswith(prefix) for prefix in _EXPLICIT_PREFIXES)
    inferred = any(marker in value for marker in _INFERRED_MARKERS)
    if not explicit and not inferred:
        return "none", []
    content = _clean_content(value)
    if len(content) < 3 or contains_sensitive_data(content):
        return "none", []
    category = _category(content)
    candidate = MemoryCandidate(
        category=category,
        normalized_key=_key(category, content),
        title=_title(category, content),
        content=content,
        source_type="explicit_chat" if explicit else "inferred_chat",
        status="active" if explicit else "pending",
        confidence=1.0 if explicit else 0.75,
    )
    return "remember", [candidate]
