"""B1 进度回写单测（不触网）：阶段映射、节流、日志尾部与接收循环回调序列。

- ``_ProgressEmitter``：重复帧丢弃、同阶段日志节流、阶段变化立即投递、
  force 透传、回调异常不外溢；
- ``_backtest_log_tail``：按行数/字符数裁剪；
- ``_run_single_generation``：对端状态帧 1/2/3 驱动阶段推进，结果帧后进入
  回测检查阶段；
- ``generate_strategy``：验收门未过时 validating/revising 阶段按序出现。
"""

from __future__ import annotations

from types import SimpleNamespace

from backend.integrations.dream import service as svc
from backend.integrations.dream.client import (
    EI_ADD_SESSION,
    EI_GET_TEMPLATE,
    EI_PUSH_MESSAGE,
    EI_SEND_PROMPT,
    EI_SUBSCRIBE,
)


class TestBacktestLogTail:
    def test_empty_passes_through(self):
        assert svc._backtest_log_tail("") == ""
        assert svc._backtest_log_tail(None) == ""  # type: ignore[arg-type]

    def test_keeps_last_28_lines(self):
        lines = [f"L{i:02d}" for i in range(40)]
        tail = svc._backtest_log_tail("\n".join(lines))
        kept = tail.splitlines()
        assert len(kept) == svc.LOG_TAIL_MAX_LINES == 28
        assert kept[0] == "L12"
        assert kept[-1] == "L39"

    def test_char_cap(self):
        text = "\n".join("x" * 100 for _ in range(10))
        tail = svc._backtest_log_tail(text)
        assert len(tail) <= svc.LOG_TAIL_MAX_CHARS
        assert tail.endswith("x" * 100)


class TestProgressEmitter:
    def test_duplicate_stage_without_log_is_dropped(self):
        events: list[tuple[str, str | None]] = []
        emitter = svc._ProgressEmitter(lambda stage, tail: events.append((stage, tail)))
        emitter("generating")
        emitter("generating")
        emitter("generating")
        assert events == [("generating", None)]

    def test_same_stage_log_updates_are_throttled(self, monkeypatch):
        clock = {"now": 1000.0}
        monkeypatch.setattr(svc.time, "monotonic", lambda: clock["now"])
        events: list[tuple[str, str | None]] = []
        emitter = svc._ProgressEmitter(lambda stage, tail: events.append((stage, tail)))

        emitter("backtest_checking", "tail-1")
        emitter("backtest_checking", "tail-2")  # 1.5s 内：丢弃
        assert len(events) == 1

        clock["now"] += svc._PROGRESS_MIN_INTERVAL + 0.01
        emitter("backtest_checking", "tail-3")
        assert [tail for _, tail in events] == ["tail-1", "tail-3"]

    def test_stage_change_emits_immediately(self):
        events: list[tuple[str, str | None]] = []
        emitter = svc._ProgressEmitter(lambda stage, tail: events.append((stage, tail)))
        emitter("generating")
        emitter("backtest_checking")  # 即使没有日志也立即投递
        emitter("regenerating")
        assert [stage for stage, _ in events] == [
            "generating",
            "backtest_checking",
            "regenerating",
        ]

    def test_force_bypasses_dedupe_and_throttle(self, monkeypatch):
        clock = {"now": 1000.0}
        monkeypatch.setattr(svc.time, "monotonic", lambda: clock["now"])
        events: list[tuple[str, str | None]] = []
        emitter = svc._ProgressEmitter(lambda stage, tail: events.append((stage, tail)))
        emitter("validating")
        emitter("validating", force=True)
        assert len(events) == 2

    def test_empty_stage_falls_back_to_last_known(self, monkeypatch):
        clock = {"now": 2000.0}
        monkeypatch.setattr(svc.time, "monotonic", lambda: clock["now"])
        events: list[tuple[str, str | None]] = []
        emitter = svc._ProgressEmitter(lambda stage, tail: events.append((stage, tail)))
        emitter("regenerating")
        # 对端推来一帧只有日志、没有可映射状态：沿用最近阶段。
        clock["now"] += svc._PROGRESS_MIN_INTERVAL + 0.01
        emitter("", "tail")
        assert events[-1] == ("regenerating", "tail")

    def test_callback_exception_does_not_break_generation(self):
        def _boom(stage, tail):
            raise RuntimeError("repository down")

        emitter = svc._ProgressEmitter(_boom)
        # 仓储写失败只能记日志：异常绝不能冒进接收循环把生成任务打断。
        emitter("generating")
        emitter("backtest_checking", force=True)

    def test_no_callback_is_safe(self):
        emitter = svc._ProgressEmitter(None)
        emitter("generating", force=True)
        emitter("", "tail")


class _FakePush:
    """最小 PushAiStrategyV2TemplateChatMessage：把帧对象自身当作 payload。"""

    def ParseFromString(self, payload):
        self.template_id = payload.template_id
        self.session_id = payload.session_id
        self.message = payload.message


class _KwArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _frame(
    *,
    role=2,
    content_type=0,
    status=0,
    version_id="",
    backtest_log="",
    open_id="",
    version_no=0,
    content="",
):
    return SimpleNamespace(
        role=role,
        content_type=content_type,
        strategy_generation_status=status,
        template_version_id=version_id,
        template_version_no=version_no,
        backtest_log=backtest_log,
        open_id=open_id,
        content=content,
    )


class _FakeGenerationClient:
    """按脚本回放推送帧；request 按命令号返回成功响应。"""

    def __init__(self, frames, *, complete_template_on_poll=True):
        self._frames = list(frames)
        self._complete = complete_template_on_poll
        self.closed = False

    def set_receive_timeout(self, timeout):
        pass

    def receive(self):
        frame = self._frames.pop(0)
        payload = SimpleNamespace(
            template_id="tpl-1", session_id="sess-1", message=frame
        )
        return (None, EI_PUSH_MESSAGE, payload)

    def request(self, command_no, request, response_type):
        ok_info = SimpleNamespace(code=0)
        if command_no == EI_SEND_PROMPT:
            return SimpleNamespace(response_info=ok_info)
        if command_no == EI_GET_TEMPLATE:
            template = SimpleNamespace(
                name="demo",
                description="demo 策略",
                code="self.MarketOrder('FCT_T_MAIN', 1)",
                backtest_log="STATISTICS:: Total Orders 3\n" if self._complete else "",
                backtest_passed=True,
                backtest_exit_code=0 if self._complete else -1,
            )
            return SimpleNamespace(response_info=ok_info, template=template)
        raise AssertionError(f"unexpected command {command_no}")

    def close(self):
        self.closed = True


def _ext_pb2():
    return SimpleNamespace(
        PushAiStrategyV2TemplateChatMessage=_FakePush,
        AddAiStrategyV2TemplateChatMessageRequest=_KwArgs,
        AddAiStrategyV2TemplateChatMessageResponse=object,
        GetAiStrategyV2TemplateRequest=_KwArgs,
        GetAiStrategyV2TemplateResponse=object,
    )


def _settings():
    return svc.DreamStrategySettings(
        portal_config_url="http://example/config.json",
        template_id="tpl-1",
        agent="deepseek-chat",
        timeout_seconds=900,
        backtest_wait_seconds=1,
    )


class TestRunSingleGenerationProgress:
    def test_remote_status_frames_drive_stage_sequence(self):
        frames = [
            _frame(status=1),  # 对端：生成中（与本地 force 阶段相同，不重复回写）
            _frame(status=2, backtest_log="BT-LOG-1\nBT-LOG-2\n"),  # 检查回测中 + 日志
            _frame(status=3),  # 对端自动重生
            _frame(
                content_type=4, version_id="ver-1", open_id="m1", version_no=1
            ),  # 策略结果帧
        ]
        client = _FakeGenerationClient(frames)
        events: list[tuple[str, str | None]] = []
        emitter = svc._ProgressEmitter(
            lambda stage, tail: events.append((stage, tail))
        )

        result = svc._run_single_generation(
            client,
            _ext_pb2(),
            _settings(),
            "sess-1",
            "请生成策略",
            svc.time.monotonic(),
            emitter,
        )

        stages = [stage for stage, _ in events]
        assert stages == [
            "generating",  # 发送成功立即进入
            "backtest_checking",  # 状态帧 2（阶段变化立即回写）
            "regenerating",  # 状态帧 3
            "backtest_checking",  # 结果帧后轮询产物
        ]
        # 状态帧 2 携带的日志尾部被带出。
        tails = [tail for _, tail in events if tail]
        assert tails == ["BT-LOG-1\nBT-LOG-2"]
        assert result["template_version_id"] == "ver-1"
        assert result["backtest_exit_code"] == 0

    def test_non_assistant_frames_are_ignored_for_progress(self):
        frames = [
            _frame(role=1, status=2),  # 非 assistant 非结果帧：跳过
            _frame(status=1),
            _frame(content_type=4, version_id="ver-2", open_id="m2", version_no=1),
        ]
        client = _FakeGenerationClient(frames)
        events: list[tuple[str, str | None]] = []
        svc._run_single_generation(
            client,
            _ext_pb2(),
            _settings(),
            "sess-1",
            "p",
            svc.time.monotonic(),
            svc._ProgressEmitter(lambda stage, tail: events.append((stage, tail))),
        )
        # role=1 的状态帧不得把阶段提前推到 backtest_checking。
        assert [stage for stage, _ in events][:2] == [
            "generating",
            "backtest_checking",
        ]

    def test_unknown_remote_status_does_not_map_stage(self):
        assert svc._REMOTE_STAGE_BY_STATUS.get(0) is None
        assert svc._REMOTE_STAGE_BY_STATUS.get(4) is None
        assert svc._REMOTE_STAGE_BY_STATUS[1] == "generating"


class _FakeFullClient(_FakeGenerationClient):
    """generate_strategy 全链路用：建会话/订阅成功，每轮都回放同一结果帧。"""

    def request(self, command_no, request, response_type):
        ok_info = SimpleNamespace(code=0)
        if command_no == EI_ADD_SESSION:
            return SimpleNamespace(
                response_info=ok_info, session=SimpleNamespace(open_id="sess-1")
            )
        if command_no == EI_SUBSCRIBE:
            return SimpleNamespace(response_info=ok_info)
        return super().request(command_no, request, response_type)

    def receive(self):
        # 每一轮生成都立刻给结果帧；队列不随轮次耗尽。
        payload = SimpleNamespace(
            template_id="tpl-1",
            session_id="sess-1",
            message=_frame(
                content_type=4, version_id="ver-1", open_id="m1", version_no=1
            ),
        )
        return (None, EI_PUSH_MESSAGE, payload)


def _full_ext_pb2():
    pb2 = _ext_pb2()
    pb2.AddAiStrategyV2TemplateChatSessionRequest = _KwArgs
    pb2.AddAiStrategyV2TemplateChatSessionResponse = object
    pb2.SubscribeAiStrategyV2TemplateChatMessageRequest = _KwArgs
    pb2.SubscribeAiStrategyV2TemplateChatMessageResponse = object
    return pb2


class TestGenerateStrategyValidationStages:
    def test_revising_round_emits_validating_and_revising(self, monkeypatch):
        pb2 = _full_ext_pb2()
        monkeypatch.setattr(
            svc, "prepare_protobuf_modules", lambda: (object(), pb2)
        )
        monkeypatch.setattr(
            svc, "_load_portal_connection", lambda settings: ("ws://x", "tok")
        )
        monkeypatch.setattr(
            svc, "_connect_and_login", lambda *a: _FakeFullClient([])
        )

        failed = SimpleNamespace(
            passed=False,
            retryable=True,
            verdict="no_trade",
            reason="回测区间内无成交",
            to_dict=lambda: {"passed": False, "verdict": "no_trade"},
        )
        passed = SimpleNamespace(
            passed=True,
            retryable=False,
            verdict="passed",
            reason="",
            to_dict=lambda: {"passed": True, "verdict": "passed"},
        )
        verdicts = [failed, passed]
        monkeypatch.setattr(
            svc,
            "validate_strategy_result",
            lambda *a, **kw: verdicts.pop(0),
        )
        monkeypatch.setattr(
            svc, "build_retry_feedback", lambda validation, result: "请修正：无成交"
        )

        events: list[tuple[str, str | None]] = []
        result = svc.generate_strategy(
            "请生成有成交的策略",
            settings=_settings(),
            validation_context={
                "expected_instrument": "FCT_T_MAIN",
                "whitelist": frozenset({"FCT_T_MAIN"}),
            },
            max_regenerations=2,
            on_progress=lambda stage, tail: events.append((stage, tail)),
        )

        stages = [stage for stage, _ in events]
        assert stages == [
            "generating",  # 第一轮发送
            "backtest_checking",  # 结果帧后轮询产物
            "validating",  # 强制立即回写
            "revising",  # 验收不过，带原因重生
            "generating",  # 第二轮发送
            "backtest_checking",
            "validating",
        ]
        assert result["validation"]["passed"] is True
        assert result["regenerations"] == [
            {"attempt": 1, "verdict": "no_trade", "reason": "回测区间内无成交"}
        ]
