"""
研报 AI 分析模块
- 使用 OpenAI 兼容协议调用多模态模型
- 输入：研报全文 + 关键图表（base64）
- 输出：摘要、要点、标的、行业、情感判断
"""

import base64
import json
import logging
import os
import re
from pathlib import Path

from backend.common.llm_call import get_llm_client
from backend.common.llm_json import extract_json_string
from backend.config.config import get_analysis_model_info
from backend.research_report.constants import FIGURE_MAX_PER_REPORT, LLM_MAX_TEXT_CHARS

logger = logging.getLogger(__name__)

# 研报模块默认模型短名（provider model 映射统一收敛到 config.ANALYSIS_MODEL_REGISTRY）
RESEARCH_MODEL_ENV = "RESEARCH_ANALYSIS_MODEL"

PROMPT_TEMPLATE = """你是资深卖方研究员。请仔细阅读以下研报全文及图表，按 JSON 格式输出分析结果。

【分析要求】
1. summary：100-200字核心摘要，金字塔结构（核心结论→关键论据→风险提示→投资建议）
2. key_points：4-7条关键要点，每条1-2句话（20-50字），包含具体数据或逻辑判断
3. evidence：3-5条原文溯源，每条格式 {{"text":"原文关键段落摘录","inference":"AI从该段得出的判断"}}
   - text：从研报原文中摘录的关键段落（50-150字），优先摘录含数据、结论、评级的关键句
   - inference：基于该段落得出的投资判断（20-40字）
4. symbols：仅输出文中**明确提及**的具体股票，格式 ["code":"601318.SH","name":"中国平安","polarity":"bullish","weight":0.85]
   - code：6位数字+交易所后缀（.SH/.SZ），不确定后缀时用 .SH
   - polarity：bullish(看多)/bearish(看空)/neutral(中性)
   - weight：0-1置信度
5. industries：文中分析的主要行业，如 ["银行","有色金属"]
6. market_view：研报整体观点 bullish/bearish/neutral（仅这三个值）
7. view_strength：观点强度 0-1（neutral 时填 0.5）
8. time_horizon：short(短期<1月)/medium(中期1-6月)/long(长期>6月)

【输出格式】仅输出 JSON，不要 Markdown 代码块，不要解释：
{{"summary":"...","key_points":["...","..."],"evidence":[{{"text":"...","inference":"..."}}],"symbols":[{{"code":"xxx.SH","name":"xxx","polarity":"bullish","weight":0.8}}],"industries":["..."],"market_view":"...","view_strength":0.0,"time_horizon":"..."}}

【研报全文】
{text}

【图表说明】附加图片为研报中的关键图表，请结合图表数据辅助分析。"""

# 图片扩展名 → data URL media type
_MEDIA_TYPES = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg"}


def get_research_model_name() -> str:
    """研报分析默认模型短名（RESEARCH_ANALYSIS_MODEL，缺省 glm）。"""
    return os.getenv(RESEARCH_MODEL_ENV) or "glm"


def resolve_provider_model(short_name: str | None = None) -> str:
    """模型短名 → provider model 全名，缺省取研报默认模型。"""
    return get_analysis_model_info(short_name or get_research_model_name())[
        "provider_model"
    ]


def strip_code_fence(text: str, lang: str = "") -> str:
    """剥离首尾 fenced code block 标记（如 ```json ... ```）。"""
    text = re.sub(rf"^```(?:{lang})?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text


def build_usage(response, latency_ms: int = 0) -> dict:
    """从 chat.completions 响应提取 token 用量统计。"""
    usage = response.usage
    return {
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
        "latency_ms": latency_ms,
    }


def _encode_image(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_report(
    full_text: str,
    figure_paths: list[Path] | None = None,
    model: str | None = None,
) -> tuple[dict, str, dict]:
    """
    分析单份研报。

    参数:
        full_text: 研报全文
        figure_paths: 图表文件**绝对路径**列表（最多取前 FIGURE_MAX_PER_REPORT 张）
        model: provider/model 格式的模型名，None 则用默认

    返回:
        (解析后dict, LLM原始返回字符串, usage_info)
    """
    client = get_llm_client()
    if client is None:
        raise RuntimeError("LLM 客户端未初始化（缺少 LLM_API_KEY / LLM_BASE_URL）")

    text = full_text[:LLM_MAX_TEXT_CHARS]
    provider_model = model or resolve_provider_model()

    content = [{"type": "text", "text": PROMPT_TEMPLATE.format(text=text)}]

    # 图片
    if figure_paths:
        for fp in figure_paths[:FIGURE_MAX_PER_REPORT]:
            if not fp.exists():
                continue
            try:
                b64 = _encode_image(fp)
                ext = fp.suffix.lower().lstrip(".")
                media_type = _MEDIA_TYPES.get(ext, "png")
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{media_type};base64,{b64}"},
                    }
                )
            except Exception:
                logger.warning("图片编码失败: %s", fp)

    resp = client.chat.completions.create(
        model=provider_model,
        messages=[{"role": "user", "content": content}],
        temperature=0.2,
        max_tokens=3000,
    )
    usage = build_usage(resp)

    raw = strip_code_fence(resp.choices[0].message.content or "", "json").strip()
    json_str = extract_json_string(raw)
    parsed = None
    if json_str:
        try:
            candidate = json.loads(json_str)
            if isinstance(candidate, dict):
                parsed = candidate
        except json.JSONDecodeError:
            parsed = None
    if parsed is None:
        parsed = {"error": "JSON解析失败", "raw": raw[:500]}

    return parsed, raw, usage