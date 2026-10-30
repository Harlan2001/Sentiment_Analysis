"""DreamServer WebSocket 协议与 Protobuf 模块加载。"""

from __future__ import annotations

import struct
import sys
import tempfile
import threading
import time
import zlib
from collections import deque
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# 与服务端 Protobuf 协议对应的命令编号。
CI_HEARTBEAT = 110001
CI_LOGIN = 110003
CI_PUSH_SESSION_KEY = 310001
EI_LIST_TEMPLATE = 160053
EI_GET_TEMPLATE = 160054
EI_BACKTEST = 160055
EI_ADD_SESSION = 160060
EI_SEND_PROMPT = 160070
EI_LIST_MESSAGES = 160073
EI_SUBSCRIBE = 260060
EI_PUSH_MESSAGE = 360060


def prepare_protobuf_modules():
    """协议变化时重新生成 Python 模块，否则复用已有文件。"""

    proto_dir = PROJECT_ROOT / "proto"
    if not proto_dir.exists():
        raise RuntimeError(f"找不到 proto 目录: {proto_dir}")

    generated_dir = Path(tempfile.gettempdir()) / "sentiment_dream_generated_proto"
    generated_dir.mkdir(exist_ok=True)
    proto_files = [
        proto_dir / name
        for name in ("common.proto", "market.proto", "trade.proto", "extension.proto")
    ]
    generated_files = [generated_dir / f"{path.stem}_pb2.py" for path in proto_files]
    generated_is_stale = not all(path.exists() for path in generated_files) or (
        min(path.stat().st_mtime for path in generated_files)
        < max(path.stat().st_mtime for path in proto_files)
    )

    if generated_is_stale:
        try:
            from grpc_tools import protoc
        except ImportError as exc:
            raise RuntimeError(
                "缺少 grpcio-tools，请执行: uv pip install grpcio-tools protobuf"
            ) from exc

        arguments = [
            "grpc_tools.protoc",
            f"-I{proto_dir}",
            f"--python_out={generated_dir}",
            *(str(path) for path in proto_files),
        ]
        if protoc.main(arguments) != 0:
            raise RuntimeError("proto 编译失败")

    generated_path = str(generated_dir)
    if generated_path not in sys.path:
        sys.path.insert(0, generated_path)
    import common_pb2  # type: ignore
    import extension_pb2  # type: ignore

    return common_pb2, extension_pb2


class DreamClient:
    """封装 DreamServer 的二进制帧、心跳和请求响应匹配。"""

    def __init__(self, url: str, timeout: int):
        try:
            import websocket
        except ImportError as exc:
            raise RuntimeError("缺少依赖 websocket-client") from exc

        # Keep proxy handling local to Dream; changing NO_PROXY here would affect all backend clients.
        # http_proxy_host=None alone does NOT disable the proxy — websocket-client falls back to the
        # HTTP_PROXY/HTTPS_PROXY env vars, which hijack this connection to an unreachable proxy.
        # no_proxy=["*"] forces a direct connection regardless of the destination host.
        self.ws = websocket.create_connection(url, timeout=15, http_no_proxy=["*"])
        self.ws.settimeout(timeout)
        self.flow_no = 0
        self.closed = False
        self._send_lock = threading.Lock()
        self._pending_frames: deque[tuple[int, int, bytes]] = deque()
        self._heartbeat = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat.start()

    @staticmethod
    def build_frame(flow_no: int, command_no: int, payload: bytes = b"") -> bytes:
        return (
            struct.pack(">BBiiiI", 66, 70, flow_no, command_no, 0, len(payload))
            + payload
        )

    @staticmethod
    def parse_frame(frame: bytes) -> tuple[int, int, bytes]:
        if len(frame) < 18:
            raise RuntimeError("数据帧长度不足")
        tag0, tag1, flow_no, command_no, data_type, length = struct.unpack(
            ">BBiiiI", frame[:18]
        )
        if tag0 != 66 or tag1 != 70 or length != len(frame) - 18:
            raise RuntimeError("数据帧格式错误")
        payload = frame[18:]
        return (
            flow_no,
            command_no,
            zlib.decompress(payload) if data_type == 1 else payload,
        )

    def _heartbeat_loop(self) -> None:
        while not self.closed:
            try:
                self._send(self.build_frame(0, CI_HEARTBEAT))
            except Exception:
                return
            time.sleep(20)

    def _send(self, frame: bytes) -> None:
        # websocket-client 不保证多个线程同时 send 的帧边界安全。
        with self._send_lock:
            self.ws.send_binary(frame)

    def _receive_socket(self) -> tuple[int, int, bytes]:
        frame = self.ws.recv()
        if not isinstance(frame, bytes):
            raise RuntimeError("收到非二进制消息")
        return self.parse_frame(frame)

    def receive(self) -> tuple[int, int, bytes]:
        if self._pending_frames:
            return self._pending_frames.popleft()
        return self._receive_socket()

    def set_receive_timeout(self, timeout: float) -> None:
        """Bound how long a single blocked :meth:`receive` waits on the socket."""
        self.ws.settimeout(timeout)

    def request(self, command_no: int, message, response_type):
        self.flow_no += 1
        flow_no = self.flow_no
        self._send(self.build_frame(flow_no, command_no, message.SerializeToString()))

        while True:
            response_flow, response_command, payload = self._receive_socket()
            if response_flow == flow_no and response_command == command_no:
                response = response_type()
                response.ParseFromString(payload)
                return response
            # 请求响应和订阅推送共用连接，不能丢弃先到达的推送。
            self._pending_frames.append((response_flow, response_command, payload))

    def close(self) -> None:
        self.closed = True
        self.ws.close()
