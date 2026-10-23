"""政策文件 AI 解读。

沿用研报分析的成果形态（摘要 + 分条要点 + **原文溯源**），但输出字段面向政策：
涉及领域、对债市影响方向与依据。

**硬约束**：影响方向**必须附原文依据** —— 无 evidence 则方向置为 neutral，
避免 AI 凭空判断政策影响（政策解读最易失真的地方）。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from backend.common.llm_call import llm_chat
from backend.common.llm_json import extract_json_string
from backend.config.config import get_analysis_model_info

logger = logging.getLogger(__name__)

# 送入 LLM 的正文上限（政策文件通常不长，留足余量）
LLM_MAX_TEXT_CHARS = 20000

# 模型短名环境变量（缺省跟随默认分析模型）
POLICY_MODEL_ENV = "POLICY_ANALYSIS_MODEL"

# 涉及领域的固定枚举，避免模型自由发挥导致前端无法聚拢
DOMAIN_CHOICES = [
    "货币政策",
    "财政政策",
    "监管政策",
    "产业政策",
    "房地产政策",
    "资本市场政策",
    "外贸与汇率",
    "其他",
]

PROMPT_TEMPLATE = """你是资深固定收益研究员。以下是一份**政策文件**的正文，请按 JSON 格式输出解读结果。

【分析要求】
1. summary：100-200 字核心摘要，说明这份文件"说了什么、要解决什么问题"
2. key_points：3-6 条政策要点，每条 15-40 字，**必须来自文件本身**，不要外推
3. domains：涉及领域，仅可从此列表选择（可多选）：{domains}
4. impact_direction：对**中国债券市场**的影响方向，仅可填 bullish（利多债券/收益率下行）/ bearish（利空债券/收益率上行）/ neutral（中性或无法判断）
5. impact_reason：影响推理，说明"政策 → 中间变量 → 利率方向"的传导链条，60-150 字
6. evidence：**支撑影响方向的原文依据**，2-4 条，每条格式 {{"text":"原文摘录","inference":"由该段得出的判断"}}
   - text：从文件原文中摘录的关键段落（30-120 字），**必须逐字来自原文**
   - inference：基于该段的判断（15-40 字）

【重要约束】
- **若文件中没有足够信息支撑方向判断，impact_direction 必须填 neutral，且 evidence 可为空数组**。
  宁可判中性，也不要为凑答案而编造依据。
- 不要引入文件之外的宏观数据或市场行情（你没有这些数据）。
- 不要给出投资建议或交易指令。

【输出格式】仅输出 JSON，不要 Markdown 代码块，不要任何解释：
{{"summary":"...","key_points":["...","..."],"domains":["..."],"impact_direction":"neutral","impact_reason":"...","evidence":[{{"text":"...","inference":"..."}}]}}

【政策文件正文】
{text}"""


def get_policy_model_name() -> str:
    """政策解读默认模型短名（POLICY_ANALYSIS_MODEL，缺省跟随默认分析模型）。"""
    from backend.config.config import get_default_analysis_model_name

    return os.getenv(POLICY_MODEL_ENV) or get_default_analysis_model_name()


def _normalize_direction(value: Any) -> str:
    """方向归一：只接受三个合法值，其余按 neutral。"""
    normalized = str(value or "").strip().lower()
    if normalized in {"bullish", "bearish"}:
        return normalized
    return "neutral"


def _normalize_domains(value: Any) -> list[str]:
    """领域归一：只保留枚举内的值。"""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item in DOMAIN_CHOICES]


def _normalize_evidence(value: Any) -> list[dict[str, str]]:
    """依据归一：只保留含 text 的项。"""
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        result.append({"text": text, "inference": str(item.get("inference") or "").strip()})
    return result


def _normalize_key_points(value: Any) -> list[str]:
    """要点归一：只保留非空字符串。"""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def analyze_policy_document(full_text: str, model_name: str | None = None) -> dict[str, Any]:
    """解读政策文件正文，返回结构化的分析结果。

    约束落地：**方向判断必须附原文依据** —— 若模型给出了方向但没有 evidence，
    则降级为 neutral，避免无依据的涨跌判断误导用户。
    """
    text = (full_text or "").strip()
    if not text:
        raise ValueError("文件正文为空，无法分析")

    short_name = model_name or get_policy_model_name()
    provider_model = get_analysis_model_info(short_name)["provider_model"]

    prompt = PROMPT_TEMPLATE.format(
        domains=" / ".join(DOMAIN_CHOICES),
        text=text[:LLM_MAX_TEXT_CHARS],
    )

    # 政策解读要求稳定输出，温度取低值（与研报分析的高温度不同）；
    # llm_chat 统一记录 token/延迟，直接返回文本内容。
    raw = llm_chat(
        [{"role": "user", "content": prompt}],
        model=short_name,
        provider_model=provider_model,
        call_source="policy_document",
        temperature=0.3,
        timeout=600.0,
    )
    if not raw:
        raise RuntimeError("模型返回为空")

    json_str = extract_json_string(raw)
    if not json_str:
        raise RuntimeError("模型未返回有效 JSON")

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"模型返回 JSON 解析失败: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("模型返回结构不符合预期")

    evidence = _normalize_evidence(parsed.get("evidence"))
    direction = _normalize_direction(parsed.get("impact_direction"))

    # 硬约束：无原文依据则不给方向
    if direction != "neutral" and not evidence:
        logger.warning("模型给出方向 %s 但无原文依据，降级为 neutral", direction)
        direction = "neutral"

    return {
        "summary": str(parsed.get("summary") or "").strip(),
        "key_points": _normalize_key_points(parsed.get("key_points")),
        "domains": _normalize_domains(parsed.get("domains")),
        "impact_direction": direction,
        "impact_reason": str(parsed.get("impact_reason") or "").strip(),
        "evidence": evidence,
        "model_name": short_name,
    }