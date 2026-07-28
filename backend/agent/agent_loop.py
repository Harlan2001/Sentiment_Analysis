"""
Agent 循环模块

核心编排逻辑：LLM + 工具调用 + SSE 流式输出。
异步生成器，产出 SSE 事件字符串供 StreamingResponse 消费。

策略：工具调用阶段用非流式（兼容性好），最终回复用真流式（体验好）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Any

from openai import OpenAI

from backend.agent.tools import TOOL_DEFINITIONS
from backend.agent.tool_executor import TOOL_EXECUTORS
from backend.common.llm_logger import log_llm_usage

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5


def _log_token(
    response,
    call_source: str = "chat",
    model_name: str = "doubao",
    provider_model: str = "",
    user_id: int = 0,
    username: str = "system",
    success: bool = True,
    latency_ms: int = 0,
) -> None:
    """从 OpenAI response 提取 usage 并记录"""
    try:
        usage = response.usage
        log_llm_usage(
            call_source=call_source,
            model_name=model_name,
            provider_model=provider_model,
            user_id=user_id,
            username=username,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            success=success,
            latency_ms=latency_ms,
        )
    except Exception:
        logger.exception("Token 日志记录失败（不影响 Agent 流程）")


def _sse(data: dict) -> str:
    """将 dict 格式化为 SSE data 行。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def run_agent_loop(
    messages: list[dict],
    system_prompt: str,
    client: OpenAI,
    model: str,
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
    model_name: str = "doubao",
    user_id: int = 0,
    username: str = "system",
) -> AsyncGenerator[str, None]:
    """
    运行 Agent 循环，异步产出 SSE 事件字符串。

    Parameters
    ----------
    messages : list[dict]
        对话历史，不含 system message。每项 {"role": "user"|"assistant", "content": "..."}
    system_prompt : str
        系统提示词
    client : OpenAI
        Kingstar (OpenAI 兼容) 客户端
    model : str
        模型标识符，如 volcengine/doubao-seed-2-0-code-preview-260215
    max_tool_rounds : int
        最大工具调用轮数，防止死循环
    model_name : str
        模型短名（如 doubao），用于 token 日志
    user_id : int
        调用用户ID
    username : str
        调用用户名
    """
    # 构建完整消息列表
    full_messages: list[dict] = [
        {"role": "system", "content": system_prompt},
    ]
    for msg in messages:
        role = msg.get("role", "user")
        if role not in ("user", "assistant"):
            role = "user"
        full_messages.append({"role": role, "content": msg.get("content", "")})

    try:
        # ── 工具调用循环（非流式） ──
        for round_num in range(max_tool_rounds):
            yield _sse({"type": "thinking"})

            response = client.chat.completions.create(
                model=model,
                messages=full_messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.7,
                stream=False,
            )
            _log_token(response, call_source="chat", model_name=model_name,
                       provider_model=model, user_id=user_id, username=username)

            choice = response.choices[0]
            finish_reason = choice.finish_reason

            # 有工具调用 → 执行工具
            if finish_reason == "tool_calls" and choice.message.tool_calls:
                tool_calls = choice.message.tool_calls

                # 产出 tool_call 事件
                tc_list = []
                for tc in tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {"raw": tc.function.arguments}
                    tc_list.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": args,
                    })
                yield _sse({"type": "tool_call", "tool_calls": tc_list})

                # 把 assistant 的 tool_call 消息加入历史
                full_messages.append({
                    "role": "assistant",
                    "content": choice.message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })

                # 执行每个工具
                for tc in tool_calls:
                    tool_name = tc.function.name
                    try:
                        arguments = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                    # 产出 tool_executing 事件
                    yield _sse({
                        "type": "tool_executing",
                        "tool_call_id": tc.id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                    })

                    # 执行工具
                    executor = TOOL_EXECUTORS.get(tool_name)
                    t_start = time.monotonic()
                    if executor:
                        try:
                            result = await asyncio.to_thread(executor, **arguments)
                        except Exception as exc:
                            logger.exception("工具 %s 执行异常", tool_name)
                            result = {"error": f"工具执行失败: {str(exc)}"}
                        duration_ms = round((time.monotonic() - t_start) * 1000)
                    else:
                        result = {"error": f"未知工具: {tool_name}"}
                        duration_ms = 0

                    # 产出 tool_result 事件
                    result_event: dict = {
                        "type": "tool_result",
                        "tool_call_id": tc.id,
                        "tool_name": tool_name,
                        "duration_ms": duration_ms,
                    }
                    if "error" in result:
                        result_event["error"] = result["error"]
                    else:
                        result_event["result"] = result
                    yield _sse(result_event)

                    # 把工具结果加入历史
                    full_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                continue  # 回到循环开头，让模型处理工具结果

            # 没有工具调用 → 流式输出最终回复
            if finish_reason == "stop" or not finish_reason:

                # 如果有 content 但没有 tool_calls，非流式也够 → 但我们用流式来获得更好体验
                if choice.message.content:
                    # 已经拿到非流式回复，不用再调一次流式
                    yield _sse({"type": "content", "content": choice.message.content})
                    usage = response.usage
                    yield _sse({
                        "type": "done",
                        "usage": {
                            "prompt_tokens": usage.prompt_tokens if usage else 0,
                            "completion_tokens": usage.completion_tokens if usage else 0,
                            "total_tokens": usage.total_tokens if usage else 0,
                        } if usage else None,
                    })
                    yield "data: [DONE]\n\n"
                    return

            # 正常情况下不应到这里，但保险起见
            break

        # ── 达到最大轮数，强制请求回复 ──
        full_messages.append({
            "role": "user",
            "content": "你已经达到了工具调用的最大轮次，请基于现有信息用中文回答用户的问题。",
        })
        response = client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=0.7,
            stream=False,
        )
        _log_token(response, call_source="chat", model_name=model_name,
                   provider_model=model, user_id=user_id, username=username)
        content = response.choices[0].message.content or ""
        yield _sse({"type": "content", "content": content})
        usage = response.usage
        yield _sse({
            "type": "done",
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            } if usage else None,
        })
        yield "data: [DONE]\n\n"

    except Exception as exc:
        logger.exception("Agent 循环异常")
        yield _sse({"type": "error", "message": str(exc), "code": "AGENT_LOOP_ERROR"})
        yield "data: [DONE]\n\n"
