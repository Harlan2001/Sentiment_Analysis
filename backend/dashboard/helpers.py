"""
看板工具函数
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request

from backend.common.database import execute_query
from backend.config.config import ALL_PAGE_ROUTES, PAGE_TITLES


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
            (username,),
            one=True,
        )
    except Exception:
        # 兼容 company 列不存在的情况
        row = execute_query(
            "SELECT department FROM users WHERE username=%s AND role='manager'",
            (username,),
            one=True,
        )
        if row and row[0]:
            return {"department": row[0], "company": ""}
        raise HTTPException(403, detail="经理未分配部门，请联系管理员")
    if not row or not row[0]:
        raise HTTPException(403, detail="经理未分配部门，请联系管理员")
    return {"department": row[0], "company": row[1] or ""}


def fmt_dt(value: Any, fmt: str = "%Y-%m-%d") -> Optional[str]:
    """日期格式化为字符串"""
    return (
        value.strftime(fmt)
        if hasattr(value, "strftime")
        else str(value) if value else None
    )


def fmt_dt2(value: Any) -> Optional[str]:
    """日期时间格式化为字符串（精确到秒）"""
    return (
        value.strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(value, "strftime") and value
        else None
    )


def to_iso(value: Any) -> Optional[str]:
    """时间值转 ISO 字符串；None 保持 None（收敛各处 isoformat 三元表达式）"""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def pct(numerator: int, denominator: int) -> float:
    """计算百分比，分母为0时返回0"""
    return round(numerator / denominator * 100, 1) if denominator > 0 else 0


def safe_one(sql: str, *params: Any) -> int:
    """执行 COUNT/聚合查询并返回单个整数值"""
    row = execute_query(sql, params, one=True)
    return row[0] if row else 0


def normalize_route(route: str) -> str:
    """路由归一化：将动态路由聚合到统一 key（看板统计口径的唯一入口）

    - `/`、`/news` → `/news`
    - `/research/<任意>` → `/research`
    - `/ai-strategy-generation<任意>` → `/ai-strategy-generation`
    - 其余原样返回
    """
    if not route:
        return route
    if route in ("/", "/news"):
        return "/news"
    if route.startswith("/research/"):
        return "/research"
    if route.startswith("/ai-strategy-generation"):
        return "/ai-strategy-generation"
    return route


def page_title(route: str) -> str:
    """路由 → 中文页面标题"""
    norm = normalize_route(route)
    if norm.startswith("/news"):
        return PAGE_TITLES["/news"]
    if norm in PAGE_TITLES:
        return PAGE_TITLES[norm]
    # 兜底：匹配任意前缀页面（如 /forecast/detail → 预测）
    for path, title in PAGE_TITLES.items():
        if norm.startswith(path):
            return title
    return norm


def pad_page_routes(
    items: List[Dict[str, Any]], count_key: str = "count"
) -> List[Dict[str, Any]]:
    """补全 page_distribution / page_avg_duration 中未访问页面的零值条目"""
    existing = {item.get("page_route", "") for item in items}
    for route in ALL_PAGE_ROUTES:
        if route not in existing:
            items.append(
                {"page_route": route, "page_title": page_title(route), count_key: 0}
            )
    return items


def assemble_trend(
    rows: List[tuple],
    key_map: Optional[Dict[str, str]] = None,
    total: bool = False,
    unknown: str = "unknown",
) -> List[Dict[str, Any]]:
    """将 (date, key, count) 行组装为趋势图数据
    [{date, key1:cnt, key2:cnt, ...}, ...]；
    total=True 时按日追加合计字段；key 为 None 时归入 unknown 标签。
    """
    bucket: Dict[str, Dict[str, int]] = {}
    for d, k, cnt in rows:
        ds = fmt_dt(d)
        name = (key_map or {}).get(k, k)
        name = name if name is not None else unknown
        bucket.setdefault(ds, {})[name] = cnt
    out = []
    for ds in sorted(bucket):
        entry = {"date": ds, **bucket[ds]}
        if total:
            entry["total"] = sum(bucket[ds].values())
        out.append(entry)
    return out
