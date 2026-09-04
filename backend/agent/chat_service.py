"""Agent 对话共享服务：统一 LLM 客户端、系统提示词与流式内容产出。

供工作台（``/sapi/workbench/conversations``）使用，
避免多处各自维护一套 LLM 调用与 SSE 解析逻辑。
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from backend.agent.agent_loop import run_agent_loop
from backend.common.database import execute_query
from backend.common.llm_call import get_async_llm_client
from backend.config.config import (
    get_analysis_model_info,
    get_chat_model_name,
)


class AgentGenerationError(RuntimeError):
    """Agent 生成失败（LLM 返回 error 事件或异常）。"""

    def __init__(self, message: str, code: str = "AGENT_GENERATION_FAILED"):
        super().__init__(message)
        self.code = code


# ── 聊天默认模型 ──
# CHAT_MODEL_NAME 填注册表短名（如 glm），与分析模型命名统一；
# 这里解析成 provider model 供 OpenAI 客户端使用。缺省跟随默认分析模型。
CHAT_MODEL = get_analysis_model_info(get_chat_model_name())["provider_model"]


# ── 系统提示词 ──
def _build_system_prompt() -> str:
    from backend.agent.spec import filter_agent_operations, load_spec

    spec = load_spec()
    agent_ops = filter_agent_operations(spec)

    group_tools: dict[str, list[str]] = {}
    for op in agent_ops:
        tool_name = f"{op.group}_{op.name}".replace("-", "_")
        group_tools.setdefault(op.group, []).append(tool_name)

    group_descriptions = {
        "news": "新闻搜索与分析：按日期/来源搜索新闻、查看新闻详情和AI分析、"
        "搜索语义相似新闻、查看新闻关联的收益率变化",
        "factors": "因子分析：列出所有影响因子、按类别过滤"
        "（POLICY/MACRO/LIQUIDITY/RISK/SENTIMENT/INDUSTRY）",
        "forecast": "行情预测：获取最新预测报告、查看历史预测记录",
        "macro": "宏观信号：计算因子的存在性/方向性信号（带时间衰减加权）、查看信号计算日志",
        "strategy": "策略快照：获取当前策略配置快照",
        "recommend": "AI策略推荐：获取最新AI投资策略推荐、查看推荐历史、列出可用策略",
        "change": "变动监控：查看策略变动快照时间线",
        "graph": "知识图谱：查询新闻关联的知识图谱增强数据",
        "feishu": "飞书 MCP：在用户已连接飞书后，检索文档、多维表格、群组与群消息（只读）",
    }

    groups_text = []
    for gname in sorted(group_tools):
        desc = group_descriptions.get(gname, f"{gname} 相关数据查询")
        groups_text.append(f"- {desc}（工具: {', '.join(group_tools[gname])}）")

    feishu_tools = "feishu_search_docs、feishu_get_doc_content、feishu_get_bitable_metadata、feishu_list_bitable_records、feishu_list_chats、feishu_list_messages"
    return f"""你是一个专业的中国债券市场智能分析助手。

你可以使用工具来获取实时数据：
{chr(10).join(groups_text)}
- 飞书 MCP：{group_descriptions['feishu']}（工具：{feishu_tools}）

回复要求：
1. **必须先调用工具**获取真实数据，再回答用户问题——不要凭空编造数据
2. 使用 Markdown 格式回复（标题、列表、表格、**加粗**等）
3. 提供总结归纳，而非逐条复述原始数据
4. 使用 "→" 符号展示因果逻辑链
5. 保持客观中立，不做具体投资建议
6. 如果工具返回空结果或无数据，如实告知用户"""


CHAT_SYSTEM_PROMPT = _build_system_prompt()


def _resolve_user_id(username: str) -> int:
    if not username or username == "anonymous":
        return 0
    try:
        row = execute_query(
            "SELECT id FROM users WHERE username=%s", (username,), one=True
        )
        return row[0] if row else 0
    except Exception:
        return 0


async def agent_chat_stream(
    messages: list[dict], username: str, project_context: str | None = None, skills: list[dict] | None = None
) -> AsyncIterator[str]:
    """运行 Agent 循环，逐段产出最终回复的 content 增量（不含 SSE 包装）。

    遇到 LLM error 事件时抛出 :class:`AgentGenerationError`。
    """
    selected_skills = skills or []
    skill_context = "\n\n".join(
        f"### {skill['name']}\n{skill['instructions']}"
        for skill in selected_skills
    )
    system_prompt = (
        f"{CHAT_SYSTEM_PROMPT}\n\n{project_context}\n\n"
        "项目记忆可能过时；回答时应以实时工具数据为准，并在冲突时明确指出。"
        if project_context
        else CHAT_SYSTEM_PROMPT
    )
    if skill_context:
        system_prompt += (
            "\n\n本次回答中，用户明确选择了以下 Skills。请遵循其分析步骤、范围与输出要求；"
            "若与更高优先级指令冲突，以更高优先级指令为准。\n\n"
            + skill_context
        )

    llm_client = get_async_llm_client()
    if llm_client is None:
        raise AgentGenerationError(
            "LLM 客户端未初始化（缺少 LLM_API_KEY / LLM_BASE_URL）"
        )

    async for sse_event in run_agent_loop(
        messages=messages,
        system_prompt=system_prompt,
        client=llm_client,
        model=CHAT_MODEL,
        model_name=get_chat_model_name(),
        user_id=_resolve_user_id(username),
        username=username or "anonymous",
    ):
        if sse_event.startswith("data: ") and not sse_event.startswith(
            "data: [DONE]"
        ):
            try:
                data = json.loads(sse_event[6:])
            except json.JSONDecodeError:
                continue
            if data.get("type") == "content" and data.get("content"):
                yield str(data["content"])
            elif data.get("type") == "error":
                raise AgentGenerationError(
                    str(data.get("message") or "Agent 生成失败")
                )
