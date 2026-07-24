"""
宏观数据查询 API 路由
提供指标元数据和时序数据查询接口。
从 macro_indicator_data 表动态发现指标，无需硬编码。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.config.config import API_PREFIX
from backend.common.database import get_db_connection

router = APIRouter(prefix=f"{API_PREFIX}/macro-data", tags=["macro-data"])

# ═══════════════════════════════════════════════════════════════════════════
# 分类标签（前端展示用）
# ═══════════════════════════════════════════════════════════════════════════

CATEGORY_LABELS: dict[str, str] = {
    "strong": "双向强相关",
    "medium": "双向中等相关",
    "weak": "双向弱相关",
    "precious": "贵金属",
    "bond": "国债侧重",
    "general": "通用",
}


def _resolve_category(row_category: str | None) -> str:
    """将 DB 中的 category 值归一化到标签表中存在的 key。"""
    if row_category and row_category in CATEGORY_LABELS:
        return row_category
    return "general"


@router.get("/indicators")
def get_macro_indicators():
    """从数据库动态发现所有宏观指标元数据。"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        # 优先读取 category / description 列，不存在则回退
        try:
            cur.execute(
                "SELECT DISTINCT zbcode, name, category, description "
                "FROM macro_indicator_data ORDER BY zbcode"
            )
            rows = cur.fetchall()
        except Exception:
            # 兼容尚未添加 category/description 列的表结构
            cur.execute(
                "SELECT DISTINCT zbcode, name FROM macro_indicator_data ORDER BY zbcode"
            )
            rows = [(r[0], r[1], None, None) for r in cur.fetchall()]

    indicators: list[dict] = []
    for row in rows:
        code = row[0]
        name = row[1]
        db_category = row[2] if len(row) > 2 else None
        db_desc = row[3] if len(row) > 3 else None
        indicators.append({
            "code": code,
            "name": name,
            "category": _resolve_category(db_category),
            "desc": db_desc or "",
        })

    return {
        "indicators": indicators,
        "categories": [
            {"key": k, "label": v} for k, v in CATEGORY_LABELS.items()
        ],
        "total": len(indicators),
    }


@router.get("/data")
def get_macro_data(
    zbcode: str = Query(..., description="指标代码，多个用逗号分隔，如 A010101,A010301"),
    start: str = Query(None, description="起始月份，格式 YYYYMM"),
    end: str = Query(None, description="结束月份，格式 YYYYMM"),
):
    """查询宏观指标时序数据。不校验代码白名单，数据库中有什么就查什么。"""
    codes = [c.strip() for c in zbcode.split(",") if c.strip()]
    if not codes:
        raise HTTPException(status_code=400, detail="zbcode 不能为空")

    conditions = ["zbcode IN ({})".format(",".join(["%s"] * len(codes)))]
    params: list = codes.copy()

    if start:
        conditions.append("datestr >= %s")
        params.append(start)
    if end:
        conditions.append("datestr <= %s")
        params.append(end)

    where_clause = " AND ".join(conditions)

    with get_db_connection() as conn:
        cur = conn.cursor()
        # 同时查询 category 列（如果存在），否则回退
        try:
            cur.execute(
                f"SELECT zbcode, name, datestr, value, category FROM macro_indicator_data "
                f"WHERE {where_clause} ORDER BY zbcode, datestr",
                params,
            )
            rows = cur.fetchall()
            has_category = True
        except Exception:
            cur.execute(
                f"SELECT zbcode, name, datestr, value FROM macro_indicator_data "
                f"WHERE {where_clause} ORDER BY zbcode, datestr",
                params,
            )
            rows = cur.fetchall()
            has_category = False

    # 按指标分组返回
    result: dict[str, dict] = {}
    for row in rows:
        code = row[0]
        if code not in result:
            db_category = row[4] if has_category and len(row) > 4 else None
            result[code] = {
                "zbcode": code,
                "name": row[1],
                "category": _resolve_category(db_category),
                "data": [],
            }
        result[code]["data"].append({
            "datestr": row[2],
            "value": float(row[3]) if row[3] is not None else None,
        })

    # 保持请求顺序
    ordered = [result[code] for code in codes if code in result]

    return {
        "indicators": ordered,
        "query": {"zbcode": zbcode, "start": start, "end": end},
    }
