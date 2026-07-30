"""
研报 AI 分析模块
- 使用 kingstar API（OpenAI 兼容）调用多模态模型
- 输入：研报全文 + 关键图表（base64）
- 输出：摘要、要点、标的、行业、情感判断
"""
import json
import logging
import os
import re
import base64
import time
from pathlib import Path
from typing import Optional
from openai import OpenAI

from backend.config.config import create_openai_http_client, BASE_DIR
from backend.research_report.constants import FIGURE_MAX_PER_REPORT, LLM_MAX_TEXT_CHARS

logger = logging.getLogger(__name__)

kingstar_API_KEY = os.getenv("kingstar_API_KEY")
kingstar_BASE_URL = os.getenv("kingstar_BASE_URL")

_client = OpenAI(
    api_key=kingstar_API_KEY,
    base_url=kingstar_BASE_URL,
    http_client=create_openai_http_client(),
)

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

# 模型短名 → provider/model
MODEL_OPTIONS = {
    "doubao": "volcengine/doubao-seed-2-0-code-preview-260215",
    "glm": "aliyun/glm-5.2",
    "deepseek": "deepseek/deepseek-v4-pro",
    "qwen": "aliyun/qwen3.6-flash",
}

DEFAULT_MODEL = os.getenv("RESEARCH_ANALYSIS_MODEL", "doubao")


def _encode_image(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _resolve_model(short_name: str) -> str:
    return MODEL_OPTIONS.get(short_name, MODEL_OPTIONS["doubao"])


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
    text = full_text[:LLM_MAX_TEXT_CHARS]
    model = model or _resolve_model(DEFAULT_MODEL)

    content = [{"type": "text", "text": PROMPT_TEMPLATE.format(text=text)}]

    # 图片
    if figure_paths:
        for fp in figure_paths[:FIGURE_MAX_PER_REPORT]:
            if not fp.exists():
                continue
            try:
                b64 = _encode_image(fp)
                ext = fp.suffix.lower().lstrip(".")
                media_type = "png" if ext == "png" else "jpeg" if ext in ("jpg", "jpeg") else "png"
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/{media_type};base64,{b64}"},
                })
            except Exception:
                logger.warning("图片编码失败: %s", fp)

    t0 = time.time()
    resp = _client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        temperature=0.2,
        max_tokens=3000,
    )
    latency_ms = int((time.time() - t0) * 1000)

    usage = {
        "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
        "total_tokens": resp.usage.total_tokens if resp.usage else 0,
    }

    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except json.JSONDecodeError:
                parsed = {"error": "JSON解析失败", "raw": raw[:500]}
        else:
            parsed = {"error": "JSON解析失败", "raw": raw[:500]}

    return parsed, raw, usage
