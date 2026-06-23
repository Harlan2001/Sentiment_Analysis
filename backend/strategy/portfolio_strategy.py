from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from openai import OpenAI

from backend.config.config import (
    CATEGORY_KEYS,
    PORTFOLIO_MODEL,
    PORTFOLIO_TZ,
    RATING_ENUM,
    TYPE_KEYS,
)
from backend.common.db_operations import DBOperations
from backend.tools.portfolio_utils import (
    build_cache_key,
    build_data_version,
    distribution_sum_check,
    extract_json_text,
    format_datetime,
    range_to_datetime_window,
    to_decimal_2,
    validate_range,
)


@dataclass
class PortfolioRuntimeConfig:
    """组合策略运行时配置，默认值来自全局常量。"""
    model: str = PORTFOLIO_MODEL
    tz: "ZoneInfo" = PORTFOLIO_TZ  # type: ignore[name-defined]


class PortfolioStrategyService:
    """组合策略分析服务。

    根据指定日期的新闻分析结果，调用 LLM 生成组合筛选建议（久期、评级、分布等），
    并通过缓存表实现幂等与结果复用。
    """

    def __init__(self, llm_client: OpenAI, runtime_config: Optional[PortfolioRuntimeConfig] = None):
        self._llm_client = llm_client
        self._cfg = runtime_config or PortfolioRuntimeConfig()

    # ------------------------------------------------------------------
    # 输出校验 — 业务逻辑层，依赖工具函数与常量
    # ------------------------------------------------------------------

    def _normalize_and_validate_output(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """校验并规范化 LLM 输出的组合筛选 JSON。

        Args:
            payload: LLM 返回并解析后的原始字典

        Returns:
            规范化后的输出字典

        Raises:
            ValueError: 结构缺失、字段非法或分布区间违反约束
        """
        if not isinstance(payload, dict):
            raise ValueError("输出必须是 JSON object")

        general = payload.get("general")
        by_category = payload.get("distribution_by_category")
        by_type = payload.get("distribution_by_type")

        if not isinstance(general, dict):
            raise ValueError("缺少 general 对象")
        if not isinstance(by_category, dict):
            raise ValueError("缺少 distribution_by_category 对象")
        if not isinstance(by_type, dict):
            raise ValueError("缺少 distribution_by_type 对象")

        duration = validate_range(general.get("duration_years") or {}, "组合久期")
        single_weight = validate_range(general.get("single_bond_weight_pct") or {}, "单券权重")

        min_rating = str(general.get("min_rating", "不限")).strip() or "不限"
        if min_rating not in RATING_ENUM:
            raise ValueError(f"最低评级不合法：{min_rating}")

        fund = to_decimal_2(general.get("portfolio_fund_wan", 0.0))
        if fund < 0:
            raise ValueError("组合资金必须 >= 0")

        normalized_by_category: Dict[str, Dict[str, float]] = {}
        for key in CATEGORY_KEYS:
            if key not in by_category:
                raise ValueError(f"按种类缺少字段：{key}")
            normalized_by_category[key] = validate_range(by_category[key], f"按种类/{key}")

        normalized_by_type: Dict[str, Dict[str, float]] = {}
        for key in TYPE_KEYS:
            if key not in by_type:
                raise ValueError(f"按类型缺少字段：{key}")
            normalized_by_type[key] = validate_range(by_type[key], f"按类型/{key}")

        distribution_sum_check(normalized_by_category, "按种类")
        distribution_sum_check(normalized_by_type, "按类型")

        return {
            "general": {
                "duration_years": duration,
                "single_bond_weight_pct": single_weight,
                "min_rating": min_rating,
                "portfolio_fund_wan": fund,
            },
            "distribution_by_category": normalized_by_category,
            "distribution_by_type": normalized_by_type,
        }

    # ------------------------------------------------------------------
    # 提示词构建 — 业务逻辑层
    # ------------------------------------------------------------------

    @staticmethod
    def _build_news_material(rows: List[Dict[str, Any]]) -> str:
        """将新闻与分析结果格式化为 LLM 提示词素材。

        Args:
            rows: 新闻行列表，每行含 pub_time / title / direction / reason

        Returns:
            编号后的新闻素材字符串
        """
        lines: List[str] = []
        for i, item in enumerate(rows, start=1):
            pub_time = item["pub_time"]
            ts = pub_time.strftime("%Y-%m-%d %H:%M") if isinstance(pub_time, datetime) else str(pub_time)
            lines.append(
                f"{i}. 时间: {ts} | 标题: {item['title']} | 方向: {item['direction']} | 原因: {item['reason']}"
            )
        return "\n".join(lines)

    def _build_prompt(
        self,
        target_news_date: date,
        rows: List[Dict[str, Any]],
        correction_hint: str = "",
    ) -> str:
        """构建组合策略分析 LLM 提示词。

        Args:
            target_news_date: 目标新闻日期
            rows: 新闻分析行列表
            correction_hint: 上次校验失败的错误信息，用于二次修正

        Returns:
            完整的提示词字符串
        """
        material = self._build_news_material(rows)
        correction_section = f"\n校验错误修正提示：{correction_hint}\n" if correction_hint else ""
        return f"""
你是中国债券市场组合分析助手。请根据新闻及其分析原因，输出"组合筛选字段"的 JSON。

严格要求：
1) 只能输出 JSON，不要 Markdown，不要解释文字。
2) 顶层必须包含 general、distribution_by_category、distribution_by_type。
3) general 字段：
   - duration_years: {{"min": number, "max": number}}
   - single_bond_weight_pct: {{"min": number, "max": number}}
   - min_rating: string，枚举仅允许：不限, AAA, AA+, AA, AA-, A+, A, A-, BBB+
   - portfolio_fund_wan: number
4) distribution_by_category 必须包含以下9个对象，且每个对象都为 {{"min": number, "max": number}}：
   gov_bond, local_gov_bond, corp_credit_bond, financial_bond_non_policy, other_bond,
   policy_financial_bond, gov_supported_institution_bond, cd, abs
5) distribution_by_type 必须包含以下2个对象，且每个对象都为 {{"min": number, "max": number}}：
   interest_rate_bond, credit_bond
6) 所有区间都要满足 0 <= min/max <= 100 且 min <= max。
7) 按种类和按类型都要满足：sum(min) <= 100 且 sum(max) >= 100。
8) 所有数字保留两位小数。

目标新闻日期：{target_news_date.isoformat()}
新闻条数：{len(rows)}
{correction_section}
新闻材料：
{material}
"""

    # ------------------------------------------------------------------
    # LLM 调用与输出生成
    # ------------------------------------------------------------------

    def _call_llm_once(self, prompt: str) -> str:
        """单次调用 LLM，返回清洗后的文本内容。

        Args:
            prompt: 提示词

        Returns:
            模型返回的文本（已去首尾空白）
        """
        response = self._llm_client.chat.completions.create(
            model=self._cfg.model,
            messages=[
                {"role": "system", "content": "你是严格输出 JSON 的债券组合分析助手。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return (response.choices[0].message.content or "").strip()

    def _generate_output_sync(
        self,
        target_news_date: date,
        rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """同步生成并校验 LLM 输出，支持一次失败后带修正提示重试。

        Args:
            target_news_date: 目标新闻日期
            rows: 新闻分析行列表

        Returns:
            校验通过的规范化输出字典

        Raises:
            ValueError / json.JSONDecodeError: 两次尝试均失败
        """
        first_prompt = self._build_prompt(target_news_date, rows)
        first_content = self._call_llm_once(first_prompt)

        try:
            parsed = json.loads(extract_json_text(first_content))
            return self._normalize_and_validate_output(parsed)
        except Exception as first_error:
            second_prompt = self._build_prompt(
                target_news_date, rows, correction_hint=str(first_error)
            )
            second_content = self._call_llm_once(second_prompt)
            parsed_second = json.loads(extract_json_text(second_content))
            return self._normalize_and_validate_output(parsed_second)

    # ------------------------------------------------------------------
    # 公共入口 — 异步编排：查询 → 缓存 → LLM → 落库
    # ------------------------------------------------------------------

    async def analyze(self, force_refresh: bool = False) -> Dict[str, Any]:
        """执行组合策略分析（主入口）。

        流程：
        1. 取昨天日期，查询当日新闻及分析原因
        2. 构建缓存键，优先返回已成功缓存的结果
        3. 缓存未命中时写入 running 状态，调用 LLM 生成输出
        4. 成功/失败均更新缓存表状态

        Args:
            force_refresh: 是否强制刷新，跳过缓存

        Returns:
            {"data": {...}, "meta": {...}} 分析结果与元信息

        Raises:
            RuntimeError: 目标日期无可用新闻数据
        """
        target_news_date = (datetime.now(self._cfg.tz) - timedelta(days=1)).date()
        window_start, window_end = range_to_datetime_window(target_news_date)

        rows, latest_news_pub_time = await asyncio.to_thread(
            DBOperations.get_news_reason_rows, target_news_date
        )
        if not rows:
            raise RuntimeError("目标新闻日没有可分析的新闻或 reason 数据为空")

        news_ids = [int(item["news_id"]) for item in rows]
        data_version = build_data_version(latest_news_pub_time)
        cache_key = build_cache_key(target_news_date, self._cfg.model, data_version)

        # 缓存命中直接返回
        if not force_refresh:
            cached = await asyncio.to_thread(
                DBOperations.load_portfolio_strategy_cache, cache_key
            )
            if cached:
                return cached

        started_at = datetime.now(self._cfg.tz)
        request_id = str(uuid.uuid4())

        # 写入运行中状态
        await asyncio.to_thread(
            DBOperations.upsert_portfolio_strategy_running,
            cache_key,
            target_news_date,
            self._cfg.model,
            request_id,
            news_ids,
            len(news_ids),
            window_start,
            window_end,
            latest_news_pub_time,
        )

        try:
            output = await asyncio.to_thread(
                self._generate_output_sync, target_news_date, rows
            )
            latency_ms = int(
                (datetime.now(self._cfg.tz) - started_at).total_seconds() * 1000
            )
            await asyncio.to_thread(
                DBOperations.finish_portfolio_strategy_success,
                cache_key,
                output,
                latency_ms,
            )
            return {
                "data": output,
                "meta": {
                    "cache_hit": False,
                    "request_id": request_id,
                    "model_name": self._cfg.model,
                    "news_count": len(news_ids),
                    "window_start": format_datetime(window_start),
                    "window_end": format_datetime(window_end),
                    "latest_news_pub_time": format_datetime(latest_news_pub_time),
                    "latency_ms": latency_ms,
                },
            }
        except Exception as exc:
            latency_ms = int(
                (datetime.now(self._cfg.tz) - started_at).total_seconds() * 1000
            )
            with contextlib.suppress(Exception):
                await asyncio.to_thread(
                    DBOperations.finish_portfolio_strategy_fail,
                    cache_key,
                    str(exc),
                    latency_ms,
                )
            raise


_service_instance: Optional[PortfolioStrategyService] = None


def get_portfolio_strategy_service(llm_client: OpenAI) -> PortfolioStrategyService:
    """获取组合策略服务的模块级单例。

    Args:
        llm_client: OpenAI 兼容客户端实例

    Returns:
        PortfolioStrategyService 全局唯一实例
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = PortfolioStrategyService(llm_client=llm_client)
    return _service_instance
