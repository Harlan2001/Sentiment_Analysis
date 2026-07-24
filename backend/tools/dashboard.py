"""
看板工具函数
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request

from backend.common.database import execute_query
from backend.config.config import PAGE_TITLES


def admin_check(request: Request) -> bool:
    """校验管理员权限，非管理员抛出 403"""
    if not getattr(request.state, "is_admin", False):
        raise HTTPException(403, detail="需要管理员权限")
    return True


def manager_check(request: Request) -> dict:
    """校验管理员/经理权限，返回 {'department': str, 'company': str}
    - admin: department='', company=''（查看全部）
    - manager: 返回本部门+本公司
    """
    role = getattr(request.state, "role", "user")
    if role == "admin":
        return {"department": "", "company": ""}
    if role == "manager":
        return _get_manager_context(request)
    raise HTTPException(403, detail="需要管理员或经理权限")


def _get_manager_context(request: Request) -> dict:
    """获取当前 manager 的部门+公司"""
    username = getattr(request.state, "username", "")
    if not username:
        raise HTTPException(403, detail="无法识别用户身份")
    try:
        row = execute_query(
            "SELECT department, COALESCE(company,'') FROM users WHERE username=%s AND role='manager'",
            (username,), one=True,
        )
    except Exception:
        # 兼容 company 列不存在的情况
        row = execute_query(
            "SELECT department FROM users WHERE username=%s AND role='manager'",
            (username,), one=True,
        )
        if row and row[0]:
            return {"department": row[0], "company": ""}
        raise HTTPException(403, detail="经理未分配部门，请联系管理员")
    if not row or not row[0]:
        raise HTTPException(403, detail="经理未分配部门，请联系管理员")
    return {"department": row[0], "company": row[1] or ""}


def fmt_dt(value: Any, fmt: str = "%Y-%m-%d") -> Optional[str]:
    """日期格式化为字符串"""
    return value.strftime(fmt) if hasattr(value, "strftime") else str(value) if value else None


def fmt_dt2(value: Any) -> Optional[str]:
    """日期时间格式化为字符串（精确到秒）"""
    return value.strftime("%Y-%m-%d %H:%M:%S") if hasattr(value, "strftime") and value else None


def pct(numerator: int, denominator: int) -> float:
    """计算百分比，分母为0时返回0"""
    return round(numerator / denominator * 100, 1) if denominator > 0 else 0


def safe_one(sql: str, *params: Any) -> int:
    """执行 COUNT/聚合查询并返回单个整数值"""
    row = execute_query(sql, params, one=True)
    return row[0] if row else 0


def page_title(route: str) -> str:
    """路由 → 中文页面标题"""
    if route == "/" or (route or "").startswith("/news"):
        return "新闻"
    for path, title in PAGE_TITLES.items():
        if route == path or route.startswith(path):
            return title
    return route


def assemble_trend(rows: List[tuple], key_map: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """将 (date, key, count) 行组装为趋势图数据 [{date, key1:cnt, key2:cnt}, ...]"""
    bucket: Dict[str, Dict[str, int]] = {}
    for d, k, cnt in rows:
        ds = fmt_dt(d)
        name = key_map.get(k, k) if key_map else k
        bucket.setdefault(ds, {})[name] = cnt
    return [{"date": ds, **bucket[ds]} for ds in sorted(bucket)]
