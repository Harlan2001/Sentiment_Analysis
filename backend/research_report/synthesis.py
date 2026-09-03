"""多研报综合生成，复用研报分析模块的模型客户端和模型映射。"""

from __future__ import annotations

import time

from backend.common.llm_call import get_llm_client
from backend.research_report.llm import (
    build_usage,
    resolve_provider_model,
    strip_code_fence,
)


def generate_research_synthesis(
    *,
    title: str,
    requirement: str,
    sources: list[dict],
    date_start: str | None = None,
    date_end: str | None = None,
    model: str | None = None,
) -> tuple[str, dict, str]:
    """将多份已分析研报综合为可追溯的 Markdown 报告。"""
    client = get_llm_client()
    if client is None:
        raise RuntimeError("LLM 客户端未初始化（缺少 LLM_API_KEY / LLM_BASE_URL）")
    provider_model = model or resolve_provider_model()
    source_sections: list[str] = []
    for index, source in enumerate(sources, start=1):
        # Prefer the existing structured analysis and keep raw-text context bounded.
        full_text = (source.get("full_text") or "")[:2500]
        source_sections.append(
            f"""## 来源 {index}（研报 ID: {source['id']}）
标题：{source.get('title') or '未命名研报'}
机构：{source.get('institution') or '未知'}
发布日期：{source.get('publish_date') or '未知'}
行业：{source.get('industry') or '未标注'}
类型：{source.get('report_type') or '未标注'}
AI 摘要：{source.get('ai_summary') or ''}
关键要点：{source.get('ai_key_points') or ''}
原文证据：{source.get('ai_evidence') or ''}
正文节选：{full_text}"""
        )

    date_range = (
        f"{date_start or '未限定'} 至 {date_end or '未限定'}"
        if date_start or date_end
        else "未限定"
    )
    prompt = f"""你是资深研究主管，请仅基于下列已入库研报生成一份综合研究报告。

报告标题：{title}
用户要求：{requirement}
筛选日期范围：{date_range}

写作要求：
1. 使用中文 Markdown，必须包含“核心结论”“关键证据”“分歧与共识”“市场影响”“风险提示”“来源研报”章节。
2. 任何事实、数字和判断都必须能够追溯到所给来源；引用时使用“[来源N]”标注，不得补充未提供的外部事实。
3. 对来源间的观点冲突明确并列说明，不要强行合并。
4. “来源研报”章节列出研报 ID、标题、机构和发布日期。
5. 不要输出代码块，不要声称生成了 PDF 或附件。

以下是可用来源：

{chr(10).join(source_sections)}"""

    started_at = time.time()
    # 综合研报只尝试一次并在 90 秒内返回明确状态，避免任务因 SDK 默认重试长期停在生成中。
    response = client.with_options(timeout=90.0, max_retries=0).chat.completions.create(
        model=provider_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=2500,
    )
    latency_ms = int((time.time() - started_at) * 1000)
    content = strip_code_fence(
        (response.choices[0].message.content or "").strip(), "markdown|md"
    )
    usage = build_usage(response, latency_ms)
    if not content:
        raise RuntimeError("模型未返回研报内容")
    return content, usage, provider_model