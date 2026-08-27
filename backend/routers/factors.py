from __future__ import annotations

from fastapi import APIRouter, Query

from backend.config.config import API_PREFIX
from backend.factor.factor_management import get_factors_from_db, get_factors_paged

router = APIRouter(prefix=API_PREFIX, tags=["factors"])


@router.get("/factors")
def get_all_factors_api():
    return {"factors": get_factors_from_db()}


@router.get("/factors/activity-overview")
def get_factor_activity_overview_api():
    """返回因子首页所需的方向、热度和多周期活跃度数据。"""
    return {"factors": get_factors_from_db()}


@router.get("/factors/paged")
def get_factors_paged_api(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页返回因子基础信息（不含新闻活跃度聚合），用于因子库首屏快速加载"""
    return get_factors_paged(page, page_size)


@router.get("/factors/by-category/{category}")
def get_factors_by_category(category: str):
    category_upper = category.upper()
    valid_categories = {"POLICY", "MACRO", "LIQUIDITY", "RISK", "SENTIMENT", "INDUSTRY"}
    if category_upper not in valid_categories:
        return {
            "error": f"未知的因子大类: {category}，有效类别：{', '.join(valid_categories)}",
            "factors": [],
        }

    all_factors = get_factors_from_db()
    factors = []
    for factor in all_factors:
        if factor["category"].upper() == category_upper:
            factors.append(
                {
                    "code": factor["code"],
                    "name": factor["name"],
                    "category": category_upper,
                    "factor_type": factor["factor_type"],
                }
            )

    if not factors:
        return {"error": f"类别 {category} 下没有因子", "factors": []}

    return {"factors": factors}
