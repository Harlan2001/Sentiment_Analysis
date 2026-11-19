from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from backend.common.api_response import ok
from backend.common.pagination import (
    page_param,
    page_size_param,
    paginated_payload,
)
from backend.config.config import API_PREFIX
from backend.factor.factor_management import get_factors_from_db, get_factors_paged
from backend.repositories.factor_event_repository import FactorEventRepository

router = APIRouter(prefix=API_PREFIX, tags=["factors"])

_VALID_CATEGORIES = {"POLICY", "MACRO", "LIQUIDITY", "RISK", "SENTIMENT", "INDUSTRY"}
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _normalize_shanghai_naive(value: datetime) -> datetime:
    """按存储约定返回上海墙钟的 naive datetime。"""
    if value.tzinfo is not None:
        return value.astimezone(_SHANGHAI_TZ).replace(tzinfo=None)
    return value


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


@router.get("/factors/events")
def get_factor_events_api(
    factor_code: str | None = Query(None, description="因子代码，多个用逗号分隔；不传为全部"),
    start_time: datetime = Query(..., description="新闻发布时间起点，ISO 格式，闭区间"),
    end_time: datetime = Query(..., description="新闻发布时间终点，ISO 格式，闭区间"),
    model: str = Query("glm", description="事件抽取模型；每次查询仅使用一个模型"),
    include_neutral: bool = Query(False, description="无 direction 过滤时是否包含 neutral"),
    direction: str | None = Query(None, description="可选方向过滤：positive | negative"),
    page: int = page_param(),
    page_size: int = page_size_param(default=500, max_size=500),
):
    """读取原始因子事件时序；时间锚点固定为 news_factor.pub_time。"""
    selected_model = model.strip()
    if not selected_model:
        raise HTTPException(status_code=400, detail="model 不能为空")

    selected_direction = direction.strip().lower() if direction and direction.strip() else None
    if selected_direction not in {None, "positive", "negative"}:
        raise HTTPException(status_code=400, detail="direction 必须为 positive 或 negative")

    start_dt = _normalize_shanghai_naive(start_time)
    end_dt = _normalize_shanghai_naive(end_time)
    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_time 不能晚于 end_time")

    factor_codes = (
        list(dict.fromkeys(code.strip() for code in factor_code.split(",") if code.strip()))
        if factor_code
        else []
    )

    result = FactorEventRepository.from_environment().list_events(
        factor_codes=factor_codes,
        start_time=start_dt,
        end_time=end_dt,
        model=selected_model,
        include_neutral=include_neutral,
        direction=selected_direction,
        page=page,
        page_size=page_size,
    )
    return ok(paginated_payload(result["items"], result["total"], page, page_size))


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

@router.get("/factors/{factor_code}/performance")
def get_factor_performance(factor_code: str):
    """因子历史表现（事件研究结果）。

    用 news_factor 做事件研究：某因子出现后 T+1/T+5/T+20 的 10Y 收益率变动。
    同时给出**多数类基准**作对照 —— 方向命中率的正确参照不是 50%，
    而是"无后猜多数方向"的命中率，两者同屏由用户自行判断。
    """
    from backend.repositories.factor_event_study_repository import (
        FactorEventStudyRepository,
    )

    return ok(
        FactorEventStudyRepository.from_environment().get_factor_performance(factor_code)
    )


@router.get("/factors/backtest-overview")
def get_backtest_overview(
    holding_days: int = Query(5, ge=1, le=60),
    min_samples: int = Query(20, ge=1, le=1000),
):
    """回测仿真总览：各因子的历史表现 + 整体分布。

    用于回测仿真页一屏查看多个因子。与因子详情页的单因子视角互补。
    """
    from backend.repositories.factor_event_study_repository import (
        FactorEventStudyRepository,
    )

    return ok(
        FactorEventStudyRepository.from_environment().list_overview(
            holding_days=holding_days, min_samples=min_samples
        )
    )
