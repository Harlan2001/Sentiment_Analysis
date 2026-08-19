"""
Agent 循环模块

核心编排逻辑：LLM + 工具调用 + SSE 流式输出。
异步生成器，产出 SSE 事件字符串供 StreamingResponse 消费。

所有 LLM 调用（含工具调用轮与最终回复）均使用真流式（stream=True），内容逐 chunk
产出 SSE `content` 事件；工具调用轮同时累积 tool_calls 增量并执行工具。流式调用默认
携带 token 用量统计，兼容服务不支持 ``stream_options`` 时自动降级重试。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from openai import AsyncOpenAI, BadRequestError

from backend.agent.tool_executor import TOOL_EXECUTORS
from backend.agent.tools import TOOL_DEFINITIONS
from backend.common.llm_logger import log_llm_usage

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
MODEL_REQUEST_TIMEOUT_SECONDS = 45.0


async def _request_stream(client: AsyncOpenAI, **kwargs) -> AsyncGenerator:
    """发起流式请求，逐 chunk 产出。

    默认携带 ``stream_options={"include_usage": True}`` 统计 token；部分 OpenAI 兼容
    服务不接受该参数（请求阶段即返回 400），确认后去掉参数降级重试一次。
    """
    configured_client = client.with_options(
        timeout=MODEL_REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )
    try:
        stream = await configured_client.chat.completions.create(
            **kwargs,
            stream=True,
            stream_options={"include_usage": True},
        )
    except BadRequestError as exc:
        # 仅在确实由 stream_options 触发的 400 时降级，避免掩盖其他参数错误
        if "stream_options" not in str(exc) and "include_usage" not in str(exc):
            raise
        logger.warning(
            "LLM 服务拒绝 stream_options/include_usage，降级为无 token 统计重试: %.100s",
            exc,
        )
        stream = await configured_client.chat.completions.create(
            **kwargs,
            stream=True,
        )
    async for chunk in stream:
        yield chunk


def _process_chunk(chunk, acc: dict) -> str | None:
    """累积单个流式 chunk，返回需要产出的 content SSE 文本（无则返回 None）。

    ``acc`` 形如
    ``{"content_parts": list[str], "tool_calls": {index: {...}}, "finish_reason", "usage"}``。
    """
    if chunk.usage:
        acc["usage"] = chunk.usage

    choice = chunk.choices[0] if chunk.choices else None
    delta = choice.delta if choice is not None else None
    if choice is not None and choice.finish_reason:
        acc["finish_reason"] = choice.finish_reason

    content_sse = None
    if delta is not None:
        if delta.content:
            acc["content_parts"].append(delta.content)
            content_sse = _sse({"type": "content", "content": delta.content})
        for tc in delta.tool_calls or []:
            slot = acc["tool_calls"].setdefault(
                tc.index, {"id": None, "name": "", "arguments": ""}
            )
            if tc.id:
                slot["id"] = tc.id
            fn = tc.function
            if fn is not None:
                if fn.name:
                    slot["name"] += fn.name
                if fn.arguments:
                    slot["arguments"] += fn.arguments

    return content_sse


def _usage_dict(usage) -> dict | None:
    """从流式 usage 构建 done 事件的用量字段。"""
    if not usage:
        return None
    return {
        "prompt_tokens": usage.prompt_tokens or 0,
        "completion_tokens": usage.completion_tokens or 0,
        "total_tokens": usage.total_tokens or 0,
    }


def _log_token(
    usage,
    call_source: str = "chat",
    model_name: str = "glm",
    provider_model: str = "",
    user_id: int = 0,
    username: str = "system",
    success: bool = True,
    latency_ms: int = 0,
) -> None:
    """从流式 usage（正常情况为末 chunk 的 CompletionUsage）记录 token 用量。"""
    try:
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
        logger.warning("Token 日志记录失败（不影响 Agent 流程）")


def _sse(data: dict) -> str:
    """将 dict 格式化为 SSE data 行。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def run_agent_loop(
    messages: list[dict],
    system_prompt: str,
    client: AsyncOpenAI,
    model: str,
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
    model_name: str = "glm",
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
    client : AsyncOpenAI
        Kingstar (OpenAI 兼容) 异步客户端
    model : str
        模型标识符，如 aliyun/glm-5.2
    max_tool_rounds : int
        最大工具调用轮数，防止死循环
    model_name : str
        模型短名（如 glm），用于 token 日志
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

    def _empty_acc() -> dict:
        return {
            "content_parts": [],
            "tool_calls": {},
            "finish_reason": None,
            "usage": None,
        }

    try:
        # ── 工具调用循环（全程流式） ──
        for _round_num in range(max_tool_rounds):
            yield _sse({"type": "thinking"})

            acc = _empty_acc()
            async for chunk in _request_stream(
                client,
                model=model,
                messages=full_messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.7,
            ):
                content_sse = _process_chunk(chunk, acc)
                if content_sse:
                    yield content_sse
            if acc["usage"]:
                _log_token(
                    acc["usage"],
                    call_source="chat",
                    model_name=model_name,
                    provider_model=model,
                    user_id=user_id,
                    username=username,
                )

            if acc["tool_calls"]:
                # 工具调用轮：内容（通常为空的前导文）已流式产出，继续执行工具
                entries = [acc["tool_calls"][i] for i in sorted(acc["tool_calls"])]

                tc_list = []
                for e in entries:
                    try:
                        args = json.loads(e["arguments"])
                    except (json.JSONDecodeError, TypeError):
                        args = {"raw": e["arguments"]}
                    tc_list.append({"id": e["id"], "name": e["name"], "arguments": args})
                yield _sse({"type": "tool_call", "tool_calls": tc_list})

                # 把 assistant 的 tool_call 消息加入历史（arguments 保留原始字符串）
                full_messages.append(
                    {
                        "role": "assistant",
                        "content": "".join(acc["content_parts"]),
                        "tool_calls": [
                            {
                                "id": e["id"],
                                "type": "function",
                                "function": {
                                    "name": e["name"],
                                    "arguments": e["arguments"],
                                },
                            }
                            for e in entries
                        ],
                    }
                )

                # 执行每个工具
                for e in entries:
                    tool_name = e["name"]
                    try:
                        arguments = json.loads(e["arguments"])
                    except (json.JSONDecodeError, TypeError):
                        arguments = {}

                    # 产出 tool_executing 事件
                    yield _sse(
                        {
                            "type": "tool_executing",
                            "tool_call_id": e["id"],
                            "tool_name": tool_name,
                            "arguments": arguments,
                        }
                    )

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
                        "tool_call_id": e["id"],
                        "tool_name": tool_name,
                        "duration_ms": duration_ms,
                    }
                    if "error" in result:
                        result_event["error"] = result["error"]
                    else:
                        result_event["result"] = result
                    yield _sse(result_event)

                    # 把工具结果加入历史
                    full_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": e["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )

                continue  # 回到循环开头，让模型处理工具结果

            # 最终回复：内容已逐 chunk 流式产出，收尾
            yield _sse({"type": "done", "usage": _usage_dict(acc["usage"])})
            yield "data: [DONE]\n\n"
            return

        # ── 达到最大轮数，强制请求最终回复（流式） ──
        full_messages.append(
            {
                "role": "user",
                "content": "你已经达到了工具调用的最大轮次，请基于现有信息用中文回答用户的问题。",
            }
        )
        acc = _empty_acc()
        async for chunk in _request_stream(
            client,
            model=model,
            messages=full_messages,
            temperature=0.7,
        ):
            content_sse = _process_chunk(chunk, acc)
            if content_sse:
                yield content_sse
        if acc["usage"]:
            _log_token(
                acc["usage"],
                call_source="chat",
                model_name=model_name,
                provider_model=model,
                user_id=user_id,
                username=username,
            )
        yield _sse({"type": "done", "usage": _usage_dict(acc["usage"])})
        yield "data: [DONE]\n\n"

    except Exception as exc:
        logger.exception("Agent 循环异常")
        yield _sse({"type": "error", "message": str(exc), "code": "AGENT_LOOP_ERROR"})
        yield "data: [DONE]\n\n"