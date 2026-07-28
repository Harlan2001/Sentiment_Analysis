from __future__ import annotations

import json
import os
from typing import List

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

from backend.agent.agent_loop import run_agent_loop
from backend.config.config import API_PREFIX, create_openai_http_client
from backend.common.database import execute_query

router = APIRouter(prefix=f"{API_PREFIX}/chat", tags=["chat"])

# ── LLM 客户端 ──
kingstar_API_KEY = os.getenv("kingstar_API_KEY")
if not kingstar_API_KEY:
    raise ValueError("kingstar_API_KEY environment variable is not set. Please set it in your .env file.")
kingstar_BASE_URL = os.getenv("kingstar_BASE_URL")
kingstar_client = OpenAI(
    api_key=kingstar_API_KEY,
    base_url=kingstar_BASE_URL,
    http_client=create_openai_http_client(),
)

CHAT_MODEL = os.getenv("CHAT_MODEL_NAME") or "volcengine/doubao-seed-2-0-code-preview-260215"

# ── 系统提示词 ──
def _build_system_prompt() -> str:
    from backend.agent.spec import load_spec, filter_agent_operations

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
    }

    groups_text = []
    for gname in sorted(group_tools):
        desc = group_descriptions.get(gname, f"{gname} 相关数据查询")
        groups_text.append(f"- {desc}（工具: {', '.join(group_tools[gname])}）")

    return f"""你是一个专业的中国债券市场智能分析助手。

你可以使用工具来获取实时数据：
{chr(10).join(groups_text)}

回复要求：
1. **必须先调用工具**获取真实数据，再回答用户问题——不要凭空编造数据
2. 使用 Markdown 格式回复（标题、列表、表格、**加粗**等）
3. 提供总结归纳，而非逐条复述原始数据
4. 使用 "→" 符号展示因果逻辑链
5. 保持客观中立，不做具体投资建议
6. 如果工具返回空结果或无数据，如实告知用户"""

CHAT_SYSTEM_PROMPT = _build_system_prompt()


# ── 请求模型 ──
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream: bool = True


# ── 路由 ──
@router.post("")
async def chat(request: ChatRequest, req: Request):
    """统一的 Agent 对话接口，支持 SSE 流式和非流式两种模式。"""

    # 解析用户身份
    username = getattr(req.state, 'username', 'anonymous')
    user_id = 0
    if username and username != 'anonymous':
        try:
            r = execute_query("SELECT id FROM users WHERE username=%s", (username,), one=True)
            if r:
                user_id = r[0]
        except Exception:
            pass

    if request.stream:
        async def event_stream():
            async for sse_event in run_agent_loop(
                messages=[m.model_dump() for m in request.messages],
                system_prompt=CHAT_SYSTEM_PROMPT,
                client=kingstar_client,
                model=CHAT_MODEL,
                model_name="doubao",
                user_id=user_id,
                username=username or "anonymous",
            ):
                yield sse_event

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 非流式模式：收集所有 SSE 事件，组装最终 JSON 响应
    content_parts: list[str] = []
    tool_results: list[dict] = []
    error_msg: str | None = None

    async for sse_event in run_agent_loop(
        messages=[m.model_dump() for m in request.messages],
        system_prompt=CHAT_SYSTEM_PROMPT,
        client=kingstar_client,
        model=CHAT_MODEL,
        model_name="doubao",
        user_id=user_id,
        username=username or "anonymous",
    ):
        if sse_event.startswith("data: ") and not sse_event.startswith("data: [DONE]"):
            try:
                data = json.loads(sse_event[6:])
                if data.get("type") == "content":
                    content_parts.append(data["content"])
                elif data.get("type") == "tool_result":
                    tool_results.append(data)
                elif data.get("type") == "error":
                    error_msg = data.get("message", "未知错误")
            except json.JSONDecodeError:
                pass

    return {
        "content": "".join(content_parts),
        "tool_results": tool_results if tool_results else None,
        "error": error_msg,
    }
