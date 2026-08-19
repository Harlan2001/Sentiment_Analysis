"""DreamStrategy 的受控后端适配服务。

本模块只复用量化系统已验证的 WebSocket + Protobuf 协议；浏览器不应直接连接
量化服务。调用 ``generate_strategy`` 会在量化环境新建一个聊天会话，并可能生成
策略版本和触发回测，因此只能由明确的生成任务触发。
"""

from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)

# 主消息就绪后，策略版本工件（code）可能稍晚持久化，给予短暂的轮询窗口
_STRATEGY_ARTIFACT_RETRY_SECONDS = 10


# A chat stream may finish before the asynchronous backtest has written its
# result to the strategy template.  Keep this separate from the total request
# timeout so a slow or unavailable backtest cannot hold the worker forever.
DEFAULT_BACKTEST_WAIT_SECONDS = 180


@dataclass(frozen=True)
class DreamStrategySettings:
    """运行时配置；凭据仍只存在量化门户配置和本机环境中。"""

    portal_config_url: str
    template_id: str
    agent: str
    timeout_seconds: int
    backtest_wait_seconds: int = DEFAULT_BACKTEST_WAIT_SECONDS

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
        try:
            backtest_wait_seconds = int(
                os.getenv(
                    "DREAM_BACKTEST_WAIT_SECONDS",
                    str(DEFAULT_BACKTEST_WAIT_SECONDS),
                )
            )
        except ValueError as exc:
            raise ValueError("DREAM_BACKTEST_WAIT_SECONDS 必须为整数") from exc
        if backtest_wait_seconds < 1:
            raise ValueError("DREAM_BACKTEST_WAIT_SECONDS 不能小于 1 秒")

        return cls(
            portal_config_url=portal_config_url,
            template_id=template_id,
            agent=os.getenv("DREAM_AGENT", "deepseek-chat").strip() or "deepseek-chat",
            timeout_seconds=timeout_seconds,
            backtest_wait_seconds=backtest_wait_seconds,
        )


def _ensure_success(operation: str, response: Any) -> None:
    if response.response_info.code != 0:
        raise RuntimeError(
            f"{operation}失败，服务端 code={response.response_info.code}"
        )


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


def _connect_and_login(
    url: str, token: str, timeout_seconds: int, common_pb2: Any
) -> DreamClient:
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
            common_pb2.LoginRequest(
                access_token=session_key_message.session_key + token
            ),
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


def _fetch_final_message(
    client: DreamClient,
    extension_pb2: Any,
    template_id: str,
    session_id: str,
    generation_message_id: str,
) -> Any | None:
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
    _ensure_success("Read DreamStrategy final message", response)
    candidates = [
        message
        for message in response.messages
        if message.role == 2
        and len(str(message.content or "").strip()) > 1
        and not str(message.content or "").strip().isdigit()
    ]
    return candidates[-1] if candidates else None


def _fetch_strategy(
    client: DreamClient,
    extension_pb2: Any,
    template_id: str,
    version_id: str,
) -> dict[str, Any] | None:
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
        "backtest_log": template.backtest_log,
        "backtest_passed": template.backtest_passed,
        "backtest_exit_code": template.backtest_exit_code,
    }


def _backtest_is_complete(strategy: dict[str, Any] | None) -> bool:
    """A non-negative exit code is Dream's terminal-backtest contract.

    ``bool`` protobuf fields default to ``False`` when omitted, so they cannot
    distinguish a failed backtest from a backtest that has not started yet.
    The protocol documents ``-1`` as the non-terminal exit code.
    """

    if not strategy:
        return False
    exit_code = strategy.get("backtest_exit_code")
    # Incomplete protobuf messages omit all backtest fields, leaving scalar
    # defaults that look like ``False`` and ``0``. Dream emits the log during
    # checking/completion, so require it before treating an exit code as final.
    return (
        isinstance(exit_code, int)
        and exit_code >= 0
        and bool(str(strategy.get("backtest_log") or "").strip())
    )


def _wait_for_strategy_backtest(
    client: DreamClient,
    extension_pb2: Any,
    template_id: str,
    version_id: str,
    deadline: float,
) -> dict[str, Any] | None:
    """Poll the persisted template until its code and terminal test result exist."""

    latest: dict[str, Any] | None = None
    while True:
        try:
            candidate = _fetch_strategy(
                client, extension_pb2, template_id, version_id
            )
            if candidate:
                latest = candidate
                if str(candidate.get("code") or "").strip() and _backtest_is_complete(
                    candidate
                ):
                    return candidate
        except Exception as exc:
            logger.warning("DreamStrategy strategy/backtest artifact is not ready: %s", exc)
        if time.monotonic() >= deadline:
            return latest
        time.sleep(min(1, max(0.0, deadline - time.monotonic())))


def _summarize_backtest_log(backtest_log: str) -> str:
    """Persist the complete policy log for the scrollable strategy result UI.

    A hard cap protects the history database from an unexpectedly noisy remote
    runner, without dropping normal ksquant-piloppolicy output or statistics.
    """

    return str(backtest_log or "").strip()[:100_000]


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
    "Total Orders",
    "Average Win",
    "Average Loss",
    "Compounding Annual Return",
    "Drawdown",
    "Expectancy",
    "Start Equity",
    "End Equity",
    "Net Profit",
    "Sharpe Ratio",
    "Sortino Ratio",
    "Probabilistic Sharpe Ratio",
    "Loss Rate",
    "Win Rate",
    "Profit-Loss Ratio",
    "Alpha",
    "Beta",
    "Annual Standard Deviation",
    "Annual Variance",
    "Information Ratio",
    "Tracking Error",
    "Treynor Ratio",
    "Total Fees",
    "Estimated Strategy Capacity",
    "Lowest Capacity Asset",
    "Portfolio Turnover",
    "Drawdown Recovery",
    "OrderListHash",
)


def _parse_backtest_metrics(backtest_log: str) -> list[dict[str, str]]:
    """Extract every structured statistic emitted by ksquant-piloppolicy.

    Known labels preserve their exact multi-word names. Unknown labels are
    retained as well, rather than silently dropping platform-added metrics.
    """

    metrics: list[dict[str, str]] = []
    for line in backtest_log.splitlines():
        if "STATISTICS::" not in line:
            continue
        statistic = line.split("STATISTICS::", 1)[1].strip()
        for label in _BACKTEST_STATISTIC_NAMES:
            if statistic == label or statistic.startswith(f"{label} "):
                value = statistic[len(label) :].strip()
                metrics.append(
                    {
                        "key": re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_"),
                        "label": label,
                        "value": value,
                    }
                )
                break
        else:
            # Keep fields added by new policy versions without inventing their
            # values. The usual format is ``label: value`` or ``label  value``.
            matched = re.match(r"^(.*?)(?:\s*[:=]\s*|\s{2,})(.+)$", statistic)
            if matched:
                label, value = (part.strip() for part in matched.groups())
            else:
                label, value = statistic, ""
            if label:
                metrics.append(
                    {
                        "key": re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_"),
                        "label": label,
                        "value": value,
                    }
                )
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
    settings = DreamStrategySettings(
        portal_config_url=settings.portal_config_url,
        template_id=settings.template_id,
        agent=settings.agent,
        timeout_seconds=settings.timeout_seconds,
        backtest_wait_seconds=settings.backtest_wait_seconds,
    )
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
                raise TimeoutError(
                    f"DreamStrategy 生成超过 {settings.timeout_seconds} 秒"
                )
            client.ws.settimeout(
                max(0.1, settings.timeout_seconds - (time.monotonic() - started_at))
            )
            _, command, payload = client.receive()
            if command != EI_PUSH_MESSAGE:
                continue
            push = extension_pb2.PushAiStrategyV2TemplateChatMessage()
            push.ParseFromString(payload)
            if (
                push.template_id != settings.template_id
                or push.session_id != session_id
            ):
                continue

            message = push.message
            # Dream may push a user echo before the assistant result.
            if message.role != 2:
                continue
            if message.content:
                streamed_answer_parts.append(message.content)
            if not generation_message_id and message.open_id:
                generation_message_id = message.open_id
            if message.backtest_log:
                backtest_log = _merge_backtest_log(backtest_log, message.backtest_log)
            if push.done:
                final_message = message
                break

        if final_message is None:
            raise RuntimeError("DreamStrategy 未返回完成消息")
        hydrated_message = _fetch_final_message(
            client,
            extension_pb2,
            settings.template_id,
            session_id,
            generation_message_id,
        )
        if hydrated_message:
            final_message = hydrated_message
        answer = (final_message.content or "") or "".join(streamed_answer_parts)
        artifact_deadline = time.monotonic() + _STRATEGY_ARTIFACT_RETRY_SECONDS
        strategy: dict[str, Any] | None = None
        while True:
            try:
                strategy = _fetch_strategy(
                    client,
                    extension_pb2,
                    settings.template_id,
                    final_message.template_version_id,
                )
                if strategy and str(strategy.get("code") or "").strip():
                    break
            except Exception as exc:
                logger.warning(
                    "DreamStrategy reply has no readable strategy artifact: %s", exc
                )
            if time.monotonic() >= artifact_deadline:
                break
            time.sleep(1)
        # 保留junlin.li分支：从strategy回填合并backtest_log
        if strategy and strategy.get("backtest_log"):
            backtest_log = _merge_backtest_log(
                backtest_log, str(strategy["backtest_log"])
            )


        # Persist an assistant reply even when Dream does not attach code.
        if not str(answer or "").strip():
            raise RuntimeError("DreamStrategy completed without a final answer")
        # Text-only assistant replies may not include persistent strategy identifiers.
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
            # Template fields are the durable, per-version backtest result. A
            # chat message can be emitted before the asynchronous test finishes.
            "backtest_passed": (
                strategy.get("backtest_passed")
                if _backtest_is_complete(strategy)
                else None
            ),
            "backtest_exit_code": (
                strategy.get("backtest_exit_code")
                if _backtest_is_complete(strategy)
                else None
            ),
            "backtest_summary": _summarize_backtest_log(backtest_log),
            "backtest_metrics": _parse_backtest_metrics(backtest_log),
            "elapsed_seconds": round(time.monotonic() - started_at, 3),
        }
    finally:
        client.close()
