"""统一 API 响应壳与错误构造。

与进行中的重构方向一致：较新的仓储系路由已返回 ``{"data": <payload>}``，
旧路由的 ``{"success": True, "data": ...}`` 逐步收敛到 ``ok()``。
"""

from __future__ import annotations

from typing import Any, Dict


def ok(data: Any) -> Dict[str, Any]:
    """标准成功响应壳：``{"data": <payload>}``。"""
    return {"data": data}