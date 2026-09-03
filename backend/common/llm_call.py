"""LLM 调用统一封装（OpenAI 兼容协议）。

收敛各模块对 LLM 调用样板（client 创建、超时、计时、log_llm_usage 成功/失败记录）
的重复实现。客户端按需惰性创建并缓存，避免每次调用重建连接池；
密钥在首次调用时从环境读取，避免 import 时机的问题。
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

import openai
from openai import AsyncOpenAI, OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.common.llm_logger import log_llm_usage
from backend.config.config import (
    create_openai_async_http_client,
    create_openai_http_client,
    get_llm_api_key,
    get_llm_base_url,
)

_sync_client: Optional[OpenAI] = None
_sync_lock = threading.Lock()
_async_client: Optional[AsyncOpenAI] = None
_async_lock = threading.Lock()


def get_llm_client() -> Optional[OpenAI]:
    """获取缓存的同步 LLM 客户端；未配置 LLM_API_KEY / LLM_BASE_URL 时返回 None。"""
    global _sync_client
    if _sync_client is not None:
        return _sync_client
    with _sync_lock:
        if _sync_client is None:
            api_key, base_url = get_llm_api_key(), get_llm_base_url()
            if not (api_key and base_url):
                return None
            _sync_client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                http_client=create_openai_http_client(),
            )
    return _sync_client


def get_async_llm_client() -> Optional[AsyncOpenAI]:
    """获取缓存的异步 LLM 客户端；未配置密钥时返回 None。"""
    global _async_client
    if _async_client is not None:
        return _async_client
    with _async_lock:
        if _async_client is None:
            api_key, base_url = get_llm_api_key(), get_llm_base_url()
            if not (api_key and base_url):
                return None
            _async_client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                http_client=create_openai_async_http_client(),
            )
    return _async_client


def _log_failure(
    call_source: str,
    model: str,
    provider_model: str,
    latency_ms: int,
    error_message: str,
) -> None:
    log_llm_usage(
        call_source=call_source,
        model_name=model,
        provider_model=provider_model,
        success=False,
        error_message=error_message,
        latency_ms=latency_ms,
    )


def _log_success(
    call_source: str, model: str, provider_model: str, latency_ms: int, response: Any
) -> None:
    if not response.usage:
        return
    log_llm_usage(
        call_source=call_source,
        model_name=model,
        provider_model=provider_model,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens,
        success=True,
        latency_ms=latency_ms,
    )


def llm_chat(
    messages: List[Dict[str, str]],
    *,
    model: str,
    provider_model: str,
    call_source: str,
    temperature: float = 0.7,
    timeout: float = 600.0,
    client: Optional[OpenAI] = None,
) -> str:
    """发起一次同步 LLM 调用并统一记录 token/延迟，返回 response content 文本。

    失败时记录错误日志后原样抛出。
    可用于外部传入 custom client 的场景（如需要自定义 retry/headers）。
    """
    llm_client = client if client is not None else get_llm_client()
    if llm_client is None:
        raise RuntimeError("LLM 客户端未初始化（缺少 LLM_API_KEY / LLM_BASE_URL）")

    t0 = time.time()
    try:
        response = llm_client.chat.completions.create(
            model=provider_model,
            messages=messages,
            temperature=temperature,
            timeout=timeout,
        )
    except Exception as exc:
        _log_failure(
            call_source, model, provider_model, int((time.time() - t0) * 1000), str(exc)
        )
        raise

    latency_ms = int((time.time() - t0) * 1000)
    _log_success(call_source, model, provider_model, latency_ms, response)
    return response.choices[0].message.content or ""


async def llm_chat_async(
    messages: List[Dict[str, str]],
    *,
    model: str,
    provider_model: str,
    call_source: str,
    temperature: float = 0.7,
    timeout: float = 600.0,
    max_tokens: Optional[int] = None,
    retry: bool = False,
    client: Optional[AsyncOpenAI] = None,
) -> str:
    """异步版 llm_chat；``retry=True`` 时走 ``llm_completion_with_retry``（指数退避重试）。"""
    llm_client = client if client is not None else get_async_llm_client()
    if llm_client is None:
        raise RuntimeError("LLM 客户端未初始化（缺少 LLM_API_KEY / LLM_BASE_URL）")

    call_params: Dict[str, Any] = {
        "model": provider_model,
        "messages": messages,
        "temperature": temperature,
        "timeout": timeout,
    }
    if max_tokens is not None:
        call_params["max_tokens"] = max_tokens

    t0 = time.time()
    try:
        if retry:
            response = await llm_completion_with_retry(llm_client, **call_params)
        else:
            response = await llm_client.chat.completions.create(**call_params)
    except Exception as exc:
        _log_failure(
            call_source, model, provider_model, int((time.time() - t0) * 1000), str(exc)
        )
        raise

    latency_ms = int((time.time() - t0) * 1000)
    _log_success(call_source, model, provider_model, latency_ms, response)
    return response.choices[0].message.content or ""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (openai.APIError, openai.APIConnectionError, openai.RateLimitError)
    ),
    reraise=True,
)
async def llm_completion_with_retry(client, **kwargs):
    """带指数退避重试的异步 chat.completions 调用（最多重试 3 次）。

    收敛 analyzer 中同名的 LLM 重试装饰器。
    client 为 None（未配置密钥）时直接抛错，不参与重试。
    """
    if client is None:
        raise RuntimeError("LLM 客户端未初始化（缺少 LLM_API_KEY / LLM_BASE_URL）")
    return await client.chat.completions.create(**kwargs)


async def async_chat_completion(client: Optional[AsyncOpenAI] = None, **kwargs):
    """带指数退避重试的异步 chat.completions 调用（不写 usage 日志，由调用方记录）。

    收敛 analyzer 中各自的同名薄包装；
    client 缺省时取缓存的异步客户端，供各调用方统一使用。
    """
    return await llm_completion_with_retry(client or get_async_llm_client(), **kwargs)
