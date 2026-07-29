"""DreamStrategy 的受控后端适配服务。

本模块只复用量化系统已验证的 WebSocket + Protobuf 协议；浏览器不应直接连接
量化服务。调用 ``generate_strategy`` 会在量化环境新建一个聊天会话，并可能生成
策略版本和触发回测，因此只能由明确的生成任务触发。
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from backend.integrations.dream.client import (
    CI_LOGIN,
    CI_PUSH_SESSION_KEY,
    EI_ADD_SESSION,
    EI_GET_TEMPLATE,
    EI_LIST_MESSAGES,
    EI_PUSH_MESSAGE,
    EI_SEND_PROMPT,
    EI_SUBSCRIBE,
    DreamClient,
    prepare_protobuf_modules,
)


@dataclass(frozen=True)
class DreamStrategySettings:
    """运行时配置；凭据仍只存在量化门户配置和本机环境中。"""

    portal_config_url: str
    template_id: str
    agent: str
    timeout_seconds: int

    @classmethod
    def from_environment(cls) -> "DreamStrategySettings":
        portal_config_url = os.getenv("DREAM_PORTAL_CONFIG_URL", "").strip()
        template_id = os.getenv("DREAM_TEMPLATE_ID", "").strip()
        if not portal_config_url:
            raise ValueError("缺少 DREAM_PORTAL_CONFIG_URL 配置")
        if not template_id:
            raise ValueError("缺少 DREAM_TEMPLATE_ID 配置")

        try:
            timeout_seconds = int(os.getenv("DREAM_TIMEOUT_SECONDS", "900"))
        except ValueError as exc:
            raise ValueError("DREAM_TIMEOUT_SECONDS 必须为整数") from exc
        if timeout_seconds < 30:
            raise ValueError("DREAM_TIMEOUT_SECONDS 不能小于 30 秒")

        return cls(
            portal_config_url=portal_config_url,
            template_id=template_id,
            agent=os.getenv("DREAM_AGENT", "deepseek-chat").strip() or "deepseek-chat",
            timeout_seconds=timeout_seconds,
        )


def _ensure_success(operation: str, response: Any) -> None:
    if response.response_info.code != 0:
        raise RuntimeError(f"{operation}失败，服务端 code={response.response_info.code}")


def _load_portal_connection(settings: DreamStrategySettings) -> tuple[str, str]:
    """读取量化门户公开配置，不复制或记录其中的临时访问令牌。"""

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(settings.portal_config_url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    config = payload.get("default", payload)
    if not isinstance(config, dict):
        raise RuntimeError("量化门户 config.json 格式无效")

    token = str(config.get("publicKey", "")).strip()
    ws_base_url = str(config.get("wsAiUrl") or config.get("wsUrl") or "").strip()
    if not token or not ws_base_url:
        raise RuntimeError("量化门户配置缺少 wsAiUrl/wsUrl 或 publicKey")
    if not ws_base_url.startswith(("ws://", "wss://")):
        raise RuntimeError("量化门户返回的 WebSocket 地址无效")
    return f"{ws_base_url.rstrip('/')}/{token}", token


def _connect_and_login(url: str, token: str, timeout_seconds: int, common_pb2: Any) -> DreamClient:
    client = DreamClient(url, timeout_seconds)
    try:
        while True:
            _, command, payload = client.receive()
            if command != CI_PUSH_SESSION_KEY:
                continue
            session_key_message = common_pb2.PushSessionKey()
            session_key_message.ParseFromString(payload)
            break

        response = client.request(
            CI_LOGIN,
            common_pb2.LoginRequest(access_token=session_key_message.session_key + token),
            common_pb2.LoginResponse,
        )
        _ensure_success("DreamStrategy 登录", response)
        return client
    except BaseException:
        client.close()
        raise


def _create_session(client: DreamClient, extension_pb2: Any, template_id: str) -> str:
    response = client.request(
        EI_ADD_SESSION,
        extension_pb2.AddAiStrategyV2TemplateChatSessionRequest(
            template_id=template_id,
            name=f"Sentiment-{time.strftime('%Y%m%d-%H%M%S')}",
        ),
        extension_pb2.AddAiStrategyV2TemplateChatSessionResponse,
    )
    _ensure_success("创建 DreamStrategy 会话", response)
    if not response.session.open_id:
        raise RuntimeError("创建 DreamStrategy 会话后未返回 session_id")
    return response.session.open_id


def _fetch_final_answer(
    client: DreamClient,
    extension_pb2: Any,
    template_id: str,
    session_id: str,
    generation_message_id: str,
) -> str:
    response = client.request(
        EI_LIST_MESSAGES,
        extension_pb2.ListAiStrategyV2TemplateChatMessageRequest(
            template_id=template_id,
            session_id=session_id,
            count=100,
            start_pos=0,
            return_total_count=False,
        ),
        extension_pb2.ListAiStrategyV2TemplateChatMessageResponse,
    )
    _ensure_success("读取 DreamStrategy 最终消息", response)
    if generation_message_id:
        for message in response.messages:
            if message.open_id == generation_message_id:
                return message.content
    return next((message.content for message in reversed(response.messages) if message.role == 2), "")


def _fetch_strategy(
    client: DreamClient,
    extension_pb2: Any,
    template_id: str,
    version_id: str,
) -> dict[str, str] | None:
    if not version_id:
        return None
    response = client.request(
        EI_GET_TEMPLATE,
        extension_pb2.GetAiStrategyV2TemplateRequest(
            template_id=template_id,
            include_history=False,
            version_id=version_id,
        ),
        extension_pb2.GetAiStrategyV2TemplateResponse,
    )
    _ensure_success("读取 DreamStrategy 策略版本", response)
    template = response.template
    if not template.code:
        return None
    return {
        "name": template.name,
        "description": template.description,
        "code": template.code,
    }


def _summarize_backtest_log(backtest_log: str) -> str:
    """保留用户可读的末尾诊断，避免保存过长原始控制台文本。"""

    lines = [line.strip() for line in backtest_log.splitlines() if line.strip()]
    return "\n".join(lines[-8:])[:1600]


def _merge_backtest_log(previous: str, incoming: str) -> str:
    """Merge Dream's incremental console pushes without losing earlier statistics.

    Dream may alternately send a complete snapshot or only the next console
    chunk. Full snapshots replace the previous value; true increments are
    appended with the shared boundary removed.
    """

    if not incoming:
        return previous
    if not previous or incoming == previous:
        return incoming or previous
    if incoming.startswith(previous):
        return incoming
    if previous.endswith(incoming):
        return previous

    max_overlap = min(len(previous), len(incoming))
    for overlap in range(max_overlap, 0, -1):
        if previous[-overlap:] == incoming[:overlap]:
            return previous + incoming[overlap:]
    return previous.rstrip() + "\n" + incoming.lstrip()


_BACKTEST_STATISTIC_NAMES = (
    "Total Orders", "Average Win", "Average Loss", "Compounding Annual Return",
    "Drawdown", "Expectancy", "Start Equity", "End Equity", "Net Profit",
    "Sharpe Ratio", "Sortino Ratio", "Probabilistic Sharpe Ratio", "Loss Rate",
    "Win Rate", "Profit-Loss Ratio", "Alpha", "Beta", "Annual Standard Deviation",
    "Annual Variance", "Information Ratio", "Tracking Error", "Treynor Ratio",
    "Total Fees", "Estimated Strategy Capacity", "Lowest Capacity Asset",
    "Portfolio Turnover", "Drawdown Recovery",
)


def _parse_backtest_metrics(backtest_log: str) -> list[dict[str, str]]:
    """Extract the structured Lean STATISTICS block from a Dream backtest log."""

    metrics: list[dict[str, str]] = []
    for line in backtest_log.splitlines():
        if "STATISTICS::" not in line:
            continue
        statistic = line.split("STATISTICS::", 1)[1].strip()
        for label in _BACKTEST_STATISTIC_NAMES:
            if statistic == label or statistic.startswith(f"{label} "):
                value = statistic[len(label):].strip()
                metrics.append({
                    "key": re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_"),
                    "label": label,
                    "value": value,
                })
                break
    return metrics


def generate_strategy(
    prompt: str,
    settings: DreamStrategySettings | None = None,
    session_id: str | None = None,
    on_session_created: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """提交一次真实 DreamStrategy 生成并取回可展示的公开结果。

    此函数会创建远程会话、生成策略版本，并可能触发回测；调用方负责在调用前
    获得业务授权并保存任务状态。不会返回 strategy_generation_trace。
    """

    if not prompt.strip():
        raise ValueError("策略提示词不能为空")
    settings = settings or DreamStrategySettings.from_environment()
    common_pb2, extension_pb2 = prepare_protobuf_modules()
    ws_url, token = _load_portal_connection(settings)
    client = _connect_and_login(ws_url, token, settings.timeout_seconds, common_pb2)
    started_at = time.monotonic()
    try:
        if not session_id:
            session_id = _create_session(client, extension_pb2, settings.template_id)
            if on_session_created:
                on_session_created(session_id)
        subscribe_response = client.request(
            EI_SUBSCRIBE,
            extension_pb2.SubscribeAiStrategyV2TemplateChatMessageRequest(
                template_id=settings.template_id,
                session_id=session_id,
                unsubscribe=False,
            ),
            extension_pb2.SubscribeAiStrategyV2TemplateChatMessageResponse,
        )
        _ensure_success("订阅 DreamStrategy 消息", subscribe_response)

        send_response = client.request(
            EI_SEND_PROMPT,
            extension_pb2.AddAiStrategyV2TemplateChatMessageRequest(
                template_id=settings.template_id,
                session_id=session_id,
                content=prompt,
                agent=settings.agent,
            ),
            extension_pb2.AddAiStrategyV2TemplateChatMessageResponse,
        )
        _ensure_success("发送 DreamStrategy 提示词", send_response)

        generation_message_id = ""
        streamed_answer_parts: list[str] = []
        final_message: Any | None = None
        backtest_log = ""
        while True:
            if time.monotonic() - started_at >= settings.timeout_seconds:
                raise TimeoutError(f"DreamStrategy 生成超过 {settings.timeout_seconds} 秒")
            client.ws.settimeout(max(0.1, settings.timeout_seconds - (time.monotonic() - started_at)))
            _, command, payload = client.receive()
            if command != EI_PUSH_MESSAGE:
                continue
            push = extension_pb2.PushAiStrategyV2TemplateChatMessage()
            push.ParseFromString(payload)
            if push.template_id != settings.template_id or push.session_id != session_id:
                continue

            message = push.message
            if message.content:
                streamed_answer_parts.append(message.content)
            if not generation_message_id and not message.backtest_log:
                generation_message_id = message.open_id
            if message.backtest_log:
                backtest_log = _merge_backtest_log(backtest_log, message.backtest_log)
            if push.done and (message.open_id == generation_message_id or message.content_type == 5):
                final_message = message
                break

        if final_message is None:
            raise RuntimeError("DreamStrategy 未返回完成消息")
        answer = _fetch_final_answer(
            client,
            extension_pb2,
            settings.template_id,
            session_id,
            generation_message_id,
        ) or "".join(streamed_answer_parts)
        strategy = _fetch_strategy(
            client,
            extension_pb2,
            settings.template_id,
            final_message.template_version_id,
        )

        # A completed chat message is not sufficient: Sentiment only persists a successful version when Dream returned executable strategy artifacts.
        if not str(answer or "").strip():
            raise RuntimeError("DreamStrategy completed without a final answer")
        if not final_message.open_id or not final_message.template_version_id:
            raise RuntimeError("DreamStrategy completed without a message or strategy version id")
        if not strategy or not str(strategy.get("code") or "").strip():
            raise RuntimeError("DreamStrategy completed without strategy code")

        return {
            "template_id": settings.template_id,
            "session_id": session_id,
            "message_id": final_message.open_id,
            "agent": settings.agent,
            "summary": answer,
            "strategy": strategy,
            "template_version_id": final_message.template_version_id,
            "template_version_no": final_message.template_version_no,
            "generation_status": final_message.strategy_generation_status,
            "backtest_passed": final_message.backtest_passed,
            "backtest_exit_code": final_message.backtest_exit_code,
            "backtest_summary": _summarize_backtest_log(backtest_log),
            "backtest_metrics": _parse_backtest_metrics(backtest_log),
            "elapsed_seconds": round(time.monotonic() - started_at, 3),
        }
    finally:
        client.close()
