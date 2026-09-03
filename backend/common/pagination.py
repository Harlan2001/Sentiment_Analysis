"""分页参数与页码载荷构造的统一工具。

收敛 discover / macro / research / dashboard / factor 手写的
``offset = (page - 1) * page_size``、``total_pages = ceil(total / page_size)``
以及 `COUNT(*)` 配合 `LIMIT x OFFSET y` 的样板。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, TypeVar

from fastapi import Query

T = TypeVar("T")


def page_param(default: int = 1) -> Any:
    """offset 分页的 page 参数（ge=1）。"""
    return Query(default, ge=1)


def page_size_param(default: int = 20, max_size: int = 100) -> Any:
    """offset 分页的 page_size 参数（ge=1, le=max_size）。"""
    return Query(default, ge=1, le=max_size)


def limit_param(default: int = 50, max_size: int = 100) -> Any:
    """keyset/列表查询的 limit 参数（ge=1, le=max_size）。

    收敛各任务类路由重复声明的 ``limit: int = Query(default=50, ge=1, le=100)``。
    """
    return Query(default, ge=1, le=max_size)


def offset(page: int, page_size: int) -> int:
    """SQL OFFSET 计算。"""
    return (page - 1) * page_size


def total_pages(total: int, page_size: int) -> int:
    """页面总数；空结果返回 0。"""
    return math.ceil(total / page_size) if total > 0 else 0


def paginated_payload(
    items: List[T], total: int, page: int, page_size: int
) -> Dict[str, Any]:
    """统一的分页响应载荷：items / total / page / page_size / total_pages。"""
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages(total, page_size),
    }