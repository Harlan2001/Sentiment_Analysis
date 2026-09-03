from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.common.api_response import ok
from backend.common.pagination import paginated_payload
from backend.config.config import API_PREFIX
from backend.factor.factor_management import get_factors_from_db, get_factors_paged

router = APIRouter(prefix=API_PREFIX, tags=["factors"])

_VALID_CATEGORIES = {"POLICY", "MACRO", "LIQUIDITY", "RISK", "SENTIMENT", "INDUSTRY"}


@router.get("/factors")
@router.get("/factors/activity-overview")
def get_all_factors_api():
    """因子列表；/factors/activity-overview 为同类数据（前端两处消费同一载荷）。"""
    return ok({"factors": get_factors_from_db()})


@router.get("/factors/paged")
def get_factors_paged_api(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页返回因子基础信息（不含新闻活跃度聚合），用于因子库首屏快速加载"""
    data = get_factors_paged(page, page_size)
    return ok(
        paginated_payload(data["factors"], data["total"], data["page"], data["page_size"])
    )


@router.get("/factors/by-category/{category}")
def get_factors_by_category(category: str):
    category_upper = category.upper()
    if category_upper not in _VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"未知的因子大类: {category}，有效类别：{', '.join(sorted(_VALID_CATEGORIES))}",
        )

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
        raise HTTPException(status_code=404, detail=f"类别 {category} 下没有因子")

    return ok({"factors": factors})