"""业务仓储共享基础设施：连接上下文、行序列化、工厂方法。

收敛各仓库重复的 ``_connection`` / ``from_environment`` / ``_serialize_row`` /
``_json_default`` 样板（news_summary / report_generation / research_report 等）。
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterator

from backend.common.database import get_repo_connection


def serialize_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """将 DictCursor 行转换为可 JSON 化字典。

    - ``date`` / ``datetime`` → ISO 字符串
    - ``*_json`` 列（字符串）→ 尝试反序列化为结构
    """
    if row is None:
        return None
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (date, datetime)):
            result[key] = value.isoformat()
        elif key.endswith("_json") and isinstance(value, str):
            try:
                result[key] = json.loads(value)
            except json.JSONDecodeError:
                result[key] = value
        else:
            result[key] = value
    return result


def json_default(value: Any) -> str:
    """``json.dumps`` 的 ``default`` 钩子：``date`` / ``datetime`` 序列化为 ISO 字符串。"""
    return value.isoformat() if isinstance(value, (date, datetime)) else str(value)


class BaseRepository:
    """提供面向 repositories/ 的共享连接管理与工厂方法，避免各仓储重复样板。"""

    @classmethod
    def from_environment(cls) -> "BaseRepository":
        return cls()

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        with get_repo_connection() as connection:
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise