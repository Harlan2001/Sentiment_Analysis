"""板块一：单篇研报深度拆解的结构校验与空话检测。

规则来源 docs/PRD-研报分析功能细化.md 板块一：
- 六个固定章节按序出现；
- 观点复现区内每张观点卡片五要素齐全；
- 论点 / 论据 / 风险三类要素必须在行内附逐字原文摘录（带页码）
  或显式标注“原文未明确给出”，不再设独立附录；
- AI 解读与作者观点分区，AI 章节标题必须含“非作者观点”；
- 禁止无溯源的空话套话。

``validate_deep_analysis`` 返回违规说明列表（空列表表示合格），
供 LLM 输出入库前做确定性门禁；空话检测函数供生成后提示与测试使用。
"""

from __future__ import annotations

import re

# 固定章节关键词（同时是违规提示文案的一部分，测试依赖这些字样）
REQUIRED_HEADINGS: tuple[str, ...] = (
    "核心论点",
    "论证结构",
    "观点复现",
    "关键证据与数据",
    "风险提示与适用边界",
    "非作者观点",
)

# 观点卡片五要素标签（“风险与边界”以“风险”为匹配前缀）
CARD_ELEMENTS: tuple[str, ...] = (
    "论点",
    "论据",
    "前提假设",
    "推理链路",
    "风险",
)

# 必须溯源或显式承认缺失的三要素
SOURCED_ELEMENTS: tuple[str, ...] = ("论点", "论据", "风险")

# 无信息量的空话套话词表（命中且未附行内原文摘录即判空话）
FLUFF_PHRASES: tuple[str, ...] = (
    "未来可期",
    "后市可期",
    "值得关注",
    "值得期待",
    "持续关注",
    "持续向好",
    "前景广阔",
    "前景光明",
    "长期向好",
    "有望持续",
    "大势所趋",
    "蓄势待发",
)

_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
# 行内逐字原文摘录：中文弯引号或直角引号包裹、至少 4 个字
_INLINE_QUOTE_RE = re.compile(r"[“「][^”」]{4,}[”」]")
_SENTENCE_SPLIT_RE = re.compile(r"[。！；;\n]+")

# 要素行允许的前缀：标题符 / 列表符 / 编号 / 加粗，如「- 论点：」「**论点**：」「1. 论据：」「#### 风险：」
def _element_line_re(label: str) -> re.Pattern[str]:
    # 标签是中文，与前缀字符集不相交；标签与冒号间允许少量后缀文字（如「风险与边界」）
    return re.compile(rf"^\s*[#\-*>•·\d.、)）\s]*{re.escape(label)}[^:：\n]{{0,10}}[:：]")


def _has_verbatim_quote(text: str) -> bool:
    return bool(_INLINE_QUOTE_RE.search(text or ""))


def _is_heading(line: str) -> bool:
    return bool(_HEADING_RE.match(line.strip()))


def _split_sections(markdown: str) -> list[tuple[str, int, int]]:
    """按 ``## `` 二级标题切节，返回 (标题文本, 起始行, 结束行)。"""
    lines = markdown.splitlines()
    sections: list[tuple[str, int, int]] = []
    current: str | None = None
    start = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            if current is not None:
                sections.append((current, start, idx))
            current = stripped[3:].strip()
            start = idx
    if current is not None:
        sections.append((current, start, len(lines)))
    return sections


def validate_deep_analysis(markdown: str) -> list[str]:
    """校验深度拆解 Markdown，返回违规说明列表（空列表 = 合格）。

    入参为空或纯空白时抛 ``ValueError``。
    """
    if not markdown or not markdown.strip():
        raise ValueError("深度拆解内容为空")

    violations: list[str] = []
    lines = markdown.splitlines()
    headings = [line.strip()[1:].lstrip("#").strip()
                for line in lines if _is_heading(line)]
    heading_text = "\n".join(headings)

    # 规则 1：六个必需章节
    for name in REQUIRED_HEADINGS:
        if name not in heading_text:
            violations.append(f"缺少必需章节：{name}")

    # 规则 2/3：观点复现卡片五要素 + 三要素溯源
    sections = _split_sections(markdown)
    reproduction_block = next(
        (lines[s:e] for title, s, e in sections if "观点复现" in title),
        [],
    )
    card_blocks: list[list[str]] = []
    current: list[str] = []
    for line in reproduction_block:
        if line.strip().startswith("### "):
            if current:
                card_blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        card_blocks.append(current)

    for card in card_blocks:
        title = card[0].strip().lstrip("#").strip()
        element_patterns = {label: _element_line_re(label) for label in CARD_ELEMENTS}

        def _find_line(label: str) -> str | None:
            pattern = element_patterns[label]
            for line in card[1:]:
                if pattern.search(line):
                    return line.strip()
            return None

        for element in CARD_ELEMENTS:
            if _find_line(element) is None:
                violations.append(f"观点卡片《{title}》缺少要素：{element}")

        for element in SOURCED_ELEMENTS:
            line = _find_line(element)
            if line and not _has_verbatim_quote(line) and "原文未明确给出" not in line:
                violations.append(
                    f"观点卡片《{title}》的{element}缺少行内原文摘录"
                    f"（需附逐字原文与页码）或显式写明“原文未明确给出”"
                )

    return violations


def find_fluff_sentences(text: str) -> list[str]:
    """找出命中空话词表且未附行内原文摘录的句子。"""
    hits: list[str] = []
    for raw in _SENTENCE_SPLIT_RE.split(text or ""):
        sentence = raw.strip()
        if not sentence:
            continue
        if any(phrase in sentence for phrase in FLUFF_PHRASES) and not _has_verbatim_quote(sentence):
            hits.append(sentence)
    return hits
