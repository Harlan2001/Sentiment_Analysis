"""
研报 AI 分析模块
- 使用 OpenAI 兼容协议调用多模态模型
- 输入：研报全文 + 关键图表（base64）
- 输出：单篇深度拆解 Markdown（板块一六节骨架）+ 观点元数据
"""

import base64
import json
import logging
import os
import re
import time
from pathlib import Path

import openai

from backend.common.llm_call import get_llm_client
from backend.common.llm_json import extract_json_string
from backend.config.config import get_analysis_model_info
from backend.research_report.constants import FIGURE_MAX_PER_REPORT, LLM_MAX_TEXT_CHARS
from backend.research_report.deep_analysis import validate_deep_analysis

logger = logging.getLogger(__name__)

# 研报模块默认模型短名（provider model 映射统一收敛到 config.ANALYSIS_MODEL_REGISTRY）
RESEARCH_MODEL_ENV = "RESEARCH_ANALYSIS_MODEL"

# 单次请求超时（秒）与重试退避（秒）；批量分析受并发闸门保护，失败以瞬时错误为主
REQUEST_TIMEOUT_SECONDS = 600.0
RETRY_DELAYS = (5.0, 12.0)

PROMPT_TEMPLATE = """你是资深卖方研究员。请对下面这篇研报做**深度拆解与观点复现**，严格区分作者观点与你的分析。

【铁律】
1. 第一、二、三、四、五章只能客观还原作者观点，不得混入你自己的判断；你的独立解读只能放在第六章。
2. 每个论点、论据、风险都必须能溯源到原文：在该行内直接附逐字原文摘录与页码，格式：（原文：“逐字摘录”，第N页）。原文确实没写的，写“原文未明确给出”，禁止编造。不要使用 [Qn] 之类的编号引用。
3. 观点复现必须还原完整推理：论点 + 论据（具体数据/事实）+ 前提假设 + 推理链路 + 作者写明的风险与边界，五要素缺一不可。
4. 禁止“未来可期/值得关注/持续向好”这类无信息量空话；所有判断必须落到数据、逻辑或原文措辞。
5. markdown 字段必须严格使用下面的六节标题（标题文字不得改动），输出可直接导出 PDF/DOCX 的 Markdown。
6. markdown 正文中所有引用一律使用中文引号“”，**严禁出现英文半角双引号 "**；JSON 本身的结构性引号由你正常序列化。
7. 控制篇幅：观点卡片按重要性保留 3-6 张，每张卡片论据不超过 3 条；不要复述原文大段文字，摘录只保留支撑判断所需的最小片段。

【markdown 字段骨架】
# {{报告标题}} · 深度拆解
## 一、核心论点（作者观点）
## 二、论证结构（观点树）
## 三、观点复现
（每个观点一张卡片，标题格式 ### 观点N：xxx，卡片内含五行：
 - 论点：…（原文：“……”，第N页）
 - 论据：…（具体数据）（原文：“……”，第N页）
 - 前提假设：…（原文：“……”，第N页）或 原文未明确给出
 - 推理链路：A→B→C→结论
 - 风险与边界：…（原文：“……”，第N页）或 原文未明确给出）
## 四、关键证据与数据
（Markdown 表格：指标 | 数值 | 原文出处，出处列写逐字摘录+页码）
## 五、作者风险提示与适用边界
## 六、AI 分析解读（非作者观点）
（你作为分析师的独立解读：隐含假设、逻辑薄弱点、与其他研报/常识的分歧、可证伪条件；引用原文时同样在行内附逐字摘录与页码）

【输出格式】仅输出一个 JSON 对象，不要 Markdown 代码块，不要任何解释：
{{"markdown":"完整七节 Markdown 字符串","short_summary":"120字以内中性摘要","key_points":["4-7条关键要点"],"symbols":[{{"code":"601318.SH","name":"中国平安","polarity":"bullish","weight":0.8}}],"industries":["银行"],"market_view":"bullish","view_strength":0.8,"time_horizon":"medium"}}
- symbols 仅收录原文明确提及的标的；code 为 6 位代码 + .SH/.SZ 后缀
- market_view 仅可取 bullish/bearish/neutral；view_strength 0-1（neutral 填 0.5）
- time_horizon：short（<1月）/medium（1-6月）/long（>6月）

【研报全文】
{text}

【图表说明】附加图片为研报中的关键图表，请结合图表数据辅助拆解。"""

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


# markdown 字段正文里混入未转义英文引号时的兜底修复：
# 定位 markdown 值，把内部裸双引号成对替换成中文引号，再重新解析
_MARKDOWN_VALUE_RE = re.compile(
    r'("markdown"\s*:\s*")(.*?)("\s*,\s*"'
    r'(?:short_summary|key_points|symbols|industries|market_view|view_strength|time_horizon)"\s*:)',
    re.DOTALL,
)
_QUOTE_PROTECTOR = "␟"


def _repair_unescaped_quotes(json_str: str) -> str | None:
    def _fix(match: re.Match[str]) -> str:
        body = match.group(2).replace('\\"', _QUOTE_PROTECTOR)
        chars: list[str] = []
        opening = True
        for ch in body:
            if ch == '"':
                chars.append("“" if opening else "”")
                opening = not opening
            else:
                chars.append(ch)
        repaired_body = "".join(chars).replace(_QUOTE_PROTECTOR, "“")
        return match.group(1) + repaired_body + match.group(3)

    repaired, count = _MARKDOWN_VALUE_RE.subn(_fix, json_str, count=1)
    return repaired if count else None


def _parse_envelope(raw: str) -> dict:
    """从模型原始输出解析 JSON 信封；裸引号导致解析失败时做一次兜底修复。"""
    json_str = extract_json_string(raw)
    if not json_str:
        raise RuntimeError("模型返回中未找到 JSON 对象")
    try:
        envelope = json.loads(json_str)
    except json.JSONDecodeError as exc:
        repaired = _repair_unescaped_quotes(json_str)
        if repaired is not None:
            try:
                envelope = json.loads(repaired)
                logger.info("JSON 裸引号兜底修复成功")
            except json.JSONDecodeError:
                raise RuntimeError(f"模型返回不是合法 JSON：{str(exc)[:120]}") from exc
        else:
            raise RuntimeError(f"模型返回不是合法 JSON：{str(exc)[:120]}") from exc
    if not isinstance(envelope, dict):
        raise RuntimeError("模型返回未通过解析（缺少 JSON 对象信封）")
    return envelope


def analyze_report(
    full_text: str,
    figure_paths: list[Path] | None = None,
    model: str | None = None,
) -> tuple[str, dict, dict]:
    """
    对单份研报做深度拆解。

    参数:
        full_text: 研报全文
        figure_paths: 图表文件**绝对路径**列表（最多取前 FIGURE_MAX_PER_REPORT 张）
        model: provider/model 格式的模型名，None 则用默认

    返回:
        (深度拆解 Markdown, 观点元数据 dict, usage_info)

    模型未返回内容、JSON 无法解析、markdown 为空或未通过结构校验时抛 RuntimeError
    （由调用方把任务标记为 failed，不再产出假成功结果）。
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

    # 自带重试（不依赖 SDK 内置重试，便于记录与退避）：
    # - 网络/超时/限流/空响应：原样重试
    # - JSON 或结构校验不过：把违规点回灌给模型做一次纠正重试
    messages: list[dict] = [{"role": "user", "content": content}]
    attempts = 1 + len(RETRY_DELAYS)
    last_error = "未知错误"

    for attempt in range(attempts):
        retry_hint = ""
        try:
            resp = client.with_options(
                timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0
            ).chat.completions.create(
                model=provider_model,
                messages=messages,
                temperature=0.2,
                max_tokens=12000,
            )
            usage = build_usage(resp)

            raw = strip_code_fence(resp.choices[0].message.content or "", "json").strip()
            if not raw:
                raise RuntimeError("模型未返回任何内容")

            envelope = _parse_envelope(raw)
            markdown = str(envelope.get("markdown") or "").strip()
            if not markdown:
                raise RuntimeError("模型返回缺少 markdown 字段（深度拆解为空）")

            violations = validate_deep_analysis(markdown)
            if violations:
                logger.warning(
                    "深度拆解结构校验未通过（第 %d 次尝试）: %s",
                    attempt + 1, "；".join(violations[:5]),
                )
                retry_hint = (
                    "你上次的输出未通过结构校验，问题："
                    + "；".join(violations[:5])
                    + "。请只修正这些问题，并重新输出完整 JSON。"
                )
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": retry_hint})
                last_error = "深度拆解未通过结构校验：" + "；".join(violations[:5])
                raise RuntimeError(last_error)

            meta = {
                "summary": str(envelope.get("short_summary") or "")[:1024],
                "key_points": envelope.get("key_points") or [],
                "symbols": envelope.get("symbols") or [],
                "industries": envelope.get("industries") or [],
                "market_view": envelope.get("market_view") or "neutral",
                "view_strength": envelope.get("view_strength", 0.5),
                "time_horizon": envelope.get("time_horizon") or "medium",
                "evidence": envelope.get("evidence") or [],
            }
            if attempt > 0:
                logger.info("深度拆解在第 %d 次尝试后成功", attempt + 1)
            return markdown, meta, usage

        except (
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.InternalServerError,
        ) as exc:
            last_error = f"模型请求失败（{type(exc).__name__}）"
        except RuntimeError as exc:
            last_error = str(exc)

        if attempt < attempts - 1:
            delay = RETRY_DELAYS[attempt]
            logger.warning(
                "研报分析第 %d/%d 次尝试失败（%s），%.0f 秒后重试",
                attempt + 1, attempts, last_error[:100], delay,
            )
            time.sleep(delay)

    raise RuntimeError(f"连续 {attempts} 次分析失败：{last_error[:200]}")