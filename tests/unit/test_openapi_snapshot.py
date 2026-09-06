"""契约测试: 后端 OpenAPI 快照对比, 防止路由/请求字段/响应结构的无意识漂移。

用法:
    普通运行(对比快照):  uv run pytest tests/unit/test_openapi_snapshot.py
    有意的 API 变更后更新快照并提交:

        UPDATE_SNAPSHOT=1 uv run pytest tests/unit/test_openapi_snapshot.py
        git add tests/snapshots/openapi.json

注意: 本测试 import 整个 backend.app(不触发 lifespan), 每次对比 OpenAPI schema;
服务端细节变动应主动更新快照, 而不是静默漂移。
"""

import json
import os
from pathlib import Path

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "snapshots"
SNAPSHOT = SNAPSHOT_DIR / "openapi.json"


def _current_openapi() -> dict:
    from backend.app import app

    return app.openapi()


def _write_snapshot(current: dict) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(
        json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_openapi_contract_snapshot():
    current = _current_openapi()

    if os.getenv("UPDATE_SNAPSHOT"):
        _write_snapshot(current)
        print(f"[snapshot] 已更新 {SNAPSHOT}")
        return

    if not SNAPSHOT.exists():
        _write_snapshot(current)
        import pytest

        pytest.fail(
            "OpenAPI 快照不存在, 已自动生成; 请人工确认结构后提交 tests/snapshots/openapi.json"
        )

    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert current == expected, (
        "OpenAPI 结构发生变化(路由/字段/方法增减), 契约可能漂移。"
        "若这是有意的 API 变更, 请执行 UPDATE_SNAPSHOT=1 更新并提交快照;"
        "否则修复这次意外改动。"
    )