"""跨模块日期/时间格式化工具。

收敛各路由里手写的 `strftime if hasattr(value, "strftime") else str(value)` 三元
（returns / discover / news / macro 等），以及 dashboard/helpers 中原本只有一
处使用的 fmt_dt / fmt_dt2 / to_iso。
"""

from __future__ import annotations

from typing import Any, Optional


def fmt_dt(value: Any, fmt: str = "%Y-%m-%d") -> Optional[str]:
    """日期/时间格式化为字符串；空值返回 None。"""
    return (
        value.strftime(fmt)
        if hasattr(value, "strftime")
        else str(value) if value else None
    )


def fmt_dt2(value: Any) -> Optional[str]:
    """日期/时间格式化为字符串（精确到秒）；空值返回 None。"""
    return (
        value.strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(value, "strftime") and value
        else None
    )


def safe_fmt_dt(value: Any, fmt: str = "%Y-%m-%d") -> str:
    """将可能为 datetime 的值格式化为字符串；非 datetime 值直接 ``str()``。

    ``fmt_dt`` / ``to_iso`` 在空值/None 上返回 None，而旧 router 的三元表达式
    语义是 ``str(None) == "None"``；本函数保真旧语义，用于替换这些内联三元。
    """
    if hasattr(value, "strftime"):
        return value.strftime(fmt)
    return str(value)


def to_iso(value: Any) -> Optional[str]:
    """时间值转 ISO 字符串；None 保持 None（收敛各处 isoformat 三元表达式）。"""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)