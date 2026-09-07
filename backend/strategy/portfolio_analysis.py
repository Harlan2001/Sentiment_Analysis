"""组合策略分析服务：按目标新闻日情绪生成债券组合配置约束建议。

读取目标日期的新闻 AI 分析（``reason`` 非空），调用 LLM 产出组合配置约束
（久期区间、单券权重、最低评级、组合资金、类别与利率债/信用债分布区间），
结果写入 ``portfolio_strategy_analysis_cache`` 缓存，命中即复用。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import date, datetime, timedelta
from datetime import time as dtime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, create_model, model_validator

from backend.common.database import execute_query, get_db_connection
from backend.common.db_analysis import AnalysisQueries
from backend.common.llm_call import llm_chat_async
from backend.common.llm_json import extract_json_string
from backend.config.config import (
    PORTFOLIO_TZ,
    get_analysis_model_info,
    get_default_analysis_model_name,
)
from backend.repositories.portfolio_analysis_repository import (
    PortfolioAnalysisRepository,
)

logger = logging.getLogger(__name__)

# 输出契约数据版本：改动 prompt 或输出结构时递增，使旧的缓存键自然失效
DATA_VERSION = "v2"
# 送入 LLM 的目标日新闻上限
MAX_NEWS_IN_PROMPT = 50

# 最低评级枚举（与 docs/组合策略API.md 一致）
MIN_RATING_CHOICES = ("不限", "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+")
MinRatingType = Literal[
    "不限", "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+"
]

# 债券类别分布键名（9 类）与中文名
CATEGORY_KEYS: tuple[str, ...] = (
    "gov_bond",
    "local_gov_bond",
    "corp_credit_bond",
    "financial_bond_non_policy",
    "other_bond",
    "policy_financial_bond",
    "gov_supported_institution_bond",
    "cd",
    "abs",
)
CATEGORY_LABELS: dict[str, str] = {
    "gov_bond": "国债",
    "local_gov_bond": "地方政府债",
    "corp_credit_bond": "公司信用债",
    "financial_bond_non_policy": "金融债(不含政策性)",
    "other_bond": "其它债券",
    "policy_financial_bond": "政策性金融债",
    "gov_supported_institution_bond": "政府支持机构债",
    "cd": "同业存单",
    "abs": "资产支持证券",
}

# 按市场属性分组的分布键名
TYPE_KEYS: tuple[str, ...] = ("interest_rate_bond", "credit_bond")
TYPE_LABELS: dict[str, str] = {"interest_rate_bond": "利率债", "credit_bond": "信用债"}


class PortfolioAnalysisError(RuntimeError):
    """组合策略分析失败（目标日无数据 / LLM 输出无效等），路由映射为 500。"""


# ============== 输出契约（Pydantic 校验） ==============


class RangeModel(BaseModel):
    """百分比或年限区间，min 不得超过 max。"""

    min: float = Field(..., ge=0)
    max: float = Field(..., ge=0)

    def model_post_init(self, __context) -> None:
        if self.min > self.max:
            raise ValueError("min 不能大于 max")


class GeneralConfig(BaseModel):
    duration_years: RangeModel
    single_bond_weight_pct: RangeModel
    min_rating: MinRatingType
    portfolio_fund_wan: float = Field(..., gt=0)


# 固定键集合的动态模型：模型只接收约定键，未知键会被 Pydantic 忽略
DistributionByCategory = create_model(
    "DistributionByCategory",
    **{key: (RangeModel, Field(...)) for key in CATEGORY_KEYS},
)
DistributionByType = create_model(
    "DistributionByType",
    **{key: (RangeModel, Field(...)) for key in TYPE_KEYS},
)


class PortfolioAnalysisResult(BaseModel):
    general: GeneralConfig
    distribution_by_category: DistributionByCategory
    distribution_by_type: DistributionByType

    @model_validator(mode="after")
    def validate_distribution_sums(self) -> "PortfolioAnalysisResult":
        """分布区间总和校验（docs/组合策略字段说明.md 规则 3）。

        按「按种类」与「按类型」两组分别校验：各 min 之和 ≤ 100 且
        各 max 之和 ≥ 100，保证区间组合可达、可落地为组合仓位。
        """
        for name, group in (
            ("distribution_by_category", self.distribution_by_category),
            ("distribution_by_type", self.distribution_by_type),
        ):
            ranges = group.model_dump().values()
            if sum(item["min"] for item in ranges) > 100:
                raise ValueError(f"{name} 各 min 之和不能超过 100")
            if sum(item["max"] for item in ranges) < 100:
                raise ValueError(f"{name} 各 max 之和不能低于 100")
        return self


# ============== 数据获取 ==============


def resolve_target_news_date(
    reference_date: Optional[date] = None,
) -> Optional[date]:
    """解析目标新闻日：北京时间今天之前最近一个有新闻的日期。

    普通工作日即昨天；周一/节假日自动取上一交易日，避免非交易日落空。
    无任何新闻返回 None（由编排层抛错）。
    """
    today = reference_date or datetime.now(PORTFOLIO_TZ).date()
    day_start = datetime.combine(today, dtime.min)
    row = execute_query(
        "SELECT DATE(MAX(pub_time)) FROM news WHERE pub_time<%s",
        (day_start,),
        one=True,
    )
    value = row[0] if row else None
    if value is None:
        return None
    # MySQL DATE() 可能返回 datetime 或 date，统一归一为 date
    return value.date() if isinstance(value, datetime) else value


def fetch_news_for_date(
    target_date: date,
    limit: int = MAX_NEWS_IN_PROMPT,
) -> list[dict[str, Any]]:
    """读取目标日期、reason 非空的新闻分析（每条取最高优先级模型）。

    返回按 pub_time 倒序的列表，每项含 news_id/title/direction/horizon/
    reason/pub_time。
    """
    join_sql = AnalysisQueries.best_analysis_join()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT n.id, n.title, COALESCE(a.direction, '中性') AS direction,
                           COALESCE(a.horizon, '短期') AS horizon,
                           COALESCE(a.reason, '') AS reason, n.pub_time
                    FROM news n {join_sql}
                    WHERE DATE(n.pub_time)=%s AND COALESCE(a.reason,'')<>''
                    ORDER BY n.pub_time DESC
                    LIMIT %s""",
                (target_date, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "news_id": news_id,
            "title": title,
            "direction": direction,
            "horizon": horizon,
            "reason": reason,
            "pub_time": pub_time,
        }
        for news_id, title, direction, horizon, reason, pub_time in rows
    ]


def build_prompt(
    news_items: list[dict[str, Any]],
    target_date: date,
    model_name: str,
) -> str:
    """构建组合策略分析的 LLM 提示词（输出契约同步见 DATA_VERSION）。"""
    news_section = "\n\n".join(
        f"【新闻{i + 1}】{item['title']}\n"
        f"方向: {item['direction']} | 时间范围: {item['horizon']}\n"
        f"逻辑: {item['reason']}"
        for i, item in enumerate(news_items)
    )
    category_enum = "\n".join(
        f"- {key}（{CATEGORY_LABELS[key]}）" for key in CATEGORY_KEYS
    )
    return f"""你是中国债券市场的组合配置分析师。基于目标新闻日的 AI 新闻研判，
给出债券组合策略配置约束建议（覆盖久期、单券集中度、评级与各类别/属性分布）。

【目标新闻日】{target_date}
【分析模型】{model_name}
【新闻研判共 {len(news_items)} 条】
{news_section}

【输出要求】
1. 仅输出有效 JSON，无任何解释性文字。
2. 基于新闻情绪、方向与逻辑设置合理区间；给出保守但可执行的组合约束。
3. 所有 min 不超过 max，且 0 <= min < max <= 100（duration_years 以年为单位）。
4. distribution_by_category 与 distribution_by_type 各自满足：所有 min 之和 <= 100，且所有 max 之和 >= 100。
5. min_rating 只能是以下枚举之一：{' / '.join(MIN_RATING_CHOICES)}
6. distribution_by_category 必须包含且只包含以下 9 个键名：
{category_enum}

【输出结构】
{{
  "general": {{
    "duration_years": {{"min": <number>, "max": <number>}},
    "single_bond_weight_pct": {{"min": <number>, "max": <number>}},
    "min_rating": "<枚举值，如 AA+>",
    "portfolio_fund_wan": <number>
  }},
  "distribution_by_category": {{
    "gov_bond": {{"min": <number>, "max": <number>}},
    "local_gov_bond": {{"min": <number>, "max": <number>}},
    "corp_credit_bond": {{"min": <number>, "max": <number>}},
    "financial_bond_non_policy": {{"min": <number>, "max": <number>}},
    "other_bond": {{"min": <number>, "max": <number>}},
    "policy_financial_bond": {{"min": <number>, "max": <number>}},
    "gov_supported_institution_bond": {{"min": <number>, "max": <number>}},
    "cd": {{"min": <number>, "max": <number>}},
    "abs": {{"min": <number>, "max": <number>}}
  }},
  "distribution_by_type": {{
    "interest_rate_bond": {{"min": <number>, "max": <number>}},
    "credit_bond": {{"min": <number>, "max": <number>}}
  }}
}}
"""


# ============== 编排 ==============


def _time_str(value: Any) -> Optional[str]:
    """datetime/date 统一格式化为 ``YYYY-MM-DD HH:MM:SS``（文档展示风格）。"""
    if value is None:
        return None
    return (
        value.strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(value, "strftime")
        else str(value)
    )


def _meta_from_cache(cached: dict[str, Any]) -> dict[str, Any]:
    return {
        "cache_hit": True,
        "request_id": cached.get("request_id"),
        "model_name": cached.get("model_name"),
        "news_count": cached.get("news_count"),
        "window_start": _time_str(cached.get("window_start")),
        "window_end": _time_str(cached.get("window_end")),
        "latest_news_pub_time": _time_str(cached.get("latest_news_pub_time")),
        "latency_ms": cached.get("latency_ms"),
    }


async def analyze_portfolio_strategy(
    target_news_date: Optional[date] = None,
    model_name: Optional[str] = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """编排一次组合策略分析，返回 ``{"analysis": ..., "meta": ...}``。

    - 默认目标日期 = 今天之前最近一个有新闻的日期（可显式传入供单测/调用方使用）。
    - 命中 ``portfolio_strategy_analysis_cache`` 成功缓存且非强刷则直接复用。
    - 失败统一抛 :class:`PortfolioAnalysisError`，由路由映射为 HTTP 500。
    """
    started_at = datetime.now(PORTFOLIO_TZ)
    request_id = uuid.uuid4().hex[:12]
    selected_model = model_name or get_default_analysis_model_name()

    if target_news_date is None:
        target_news_date = resolve_target_news_date()
    if target_news_date is None:
        raise PortfolioAnalysisError("无可用新闻数据：新闻表为空")

    cache_key = (
        f"portfolio-analysis:{target_news_date}:{selected_model}:{DATA_VERSION}"
    )
    repo = PortfolioAnalysisRepository()

    # 1) 缓存命中：非强刷且存在成功结果时直接返回
    if not force_refresh:
        cached = repo.get_by_cache_key(cache_key)
        if cached and cached["status"] == "success" and cached["output"]:
            return {"analysis": cached["output"], "meta": _meta_from_cache(cached)}

    # 2) 取目标日新闻
    news_items = fetch_news_for_date(target_news_date)
    if not news_items:
        raise PortfolioAnalysisError(
            "目标新闻日没有可分析的新闻或 reason 数据为空"
        )

    latest_news_pub_time = max(item["pub_time"] for item in news_items)
    window_start = datetime.combine(target_news_date, dtime.min)
    window_end = window_start + timedelta(days=1)

    # 3) 调用 LLM 生成约束
    provider_model = get_analysis_model_info(selected_model)["provider_model"]
    prompt = build_prompt(news_items, target_news_date, selected_model)
    t0 = time.monotonic()
    try:
        response_text = await llm_chat_async(
            [
                {
                    "role": "system",
                    "content": (
                        "你是中国债券市场组合配置分析师，擅长从新闻情绪与事件"
                        "逻辑推导保守可执行的组合配置约束。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            model=selected_model,
            provider_model=provider_model,
            call_source="portfolio_strategy_analysis",
            temperature=0.7,
            timeout=600,
            retry=True,
        )
    except Exception as exc:
        raise PortfolioAnalysisError(f"LLM 调用失败: {exc}") from exc
    latency_ms = int((time.monotonic() - t0) * 1000)

    # 4) 解析 + 结构校验（失败记录缓存后统一由路由映射 500）
    try:
        json_str = extract_json_string(response_text)
        if not json_str:
            raise PortfolioAnalysisError("模型输出非 JSON 或不满足校验规则")
        try:
            analysis = PortfolioAnalysisResult.model_validate(
                json.loads(json_str)
            ).model_dump()
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("组合策略分析输出校验失败: %s", exc)
            raise PortfolioAnalysisError(
                "模型输出非 JSON 或不满足校验规则"
            ) from exc
    except PortfolioAnalysisError as exc:
        try:
            repo.save_failure(
                cache_key=cache_key,
                target_news_date=target_news_date,
                model_name=selected_model,
                request_id=request_id,
                error_message=str(exc),
                started_at=started_at,
                finished_at=datetime.now(PORTFOLIO_TZ),
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception:
            logger.warning("组合策略分析失败缓存写入失败（不影响报错）", exc_info=True)
        raise

    # 5) 写成功缓存（写失败不影响本次结果返回）
    try:
        repo.save_success(
            cache_key=cache_key,
            target_news_date=target_news_date,
            model_name=selected_model,
            analysis=analysis,
            news_ids=[item["news_id"] for item in news_items],
            news_count=len(news_items),
            window_start=window_start,
            window_end=window_end,
            latest_news_pub_time=latest_news_pub_time,
            request_id=request_id,
            started_at=started_at,
            finished_at=datetime.now(PORTFOLIO_TZ),
            latency_ms=latency_ms,
        )
    except Exception:
        logger.warning("组合策略分析缓存写入失败（不影响本次结果）", exc_info=True)

    return {
        "analysis": analysis,
        "meta": {
            "cache_hit": False,
            "request_id": request_id,
            "model_name": selected_model,
            "news_count": len(news_items),
            "window_start": _time_str(window_start),
            "window_end": _time_str(window_end),
            "latest_news_pub_time": _time_str(latest_news_pub_time),
            "latency_ms": latency_ms,
        },
    }