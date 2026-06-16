from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from openai import OpenAI

from backend.config.config import ANALYSIS_MODEL_PRIORITY
from backend.common.database import get_db_connection


PORTFOLIO_TZ = ZoneInfo("Asia/Shanghai")
PORTFOLIO_MODEL = os.getenv("PORTFOLIO_STRATEGY_MODEL", "volcengine/doubao-seed-2-0-code-preview-260215")

RATING_ENUM = {"不限", "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+"}
CATEGORY_KEYS = [
    "gov_bond",
    "local_gov_bond",
    "corp_credit_bond",
    "financial_bond_non_policy",
    "other_bond",
    "policy_financial_bond",
    "gov_supported_institution_bond",
    "cd",
    "abs",
]
TYPE_KEYS = ["interest_rate_bond", "credit_bond"]


@dataclass
class PortfolioRuntimeConfig:
    model: str = PORTFOLIO_MODEL
    tz: ZoneInfo = PORTFOLIO_TZ


class PortfolioStrategyService:
    def __init__(self, llm_client: OpenAI, runtime_config: Optional[PortfolioRuntimeConfig] = None):
        self._llm_client = llm_client
        self._cfg = runtime_config or PortfolioRuntimeConfig()

    @staticmethod
    def _to_decimal_2(value: Any) -> float:
        d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return float(d)

    @staticmethod
    def _range_to_datetime_window(target_date: date) -> Tuple[datetime, datetime]:
        return (
            datetime.combine(target_date, time(0, 0, 0)),
            datetime.combine(target_date, time(23, 59, 59)),
        )

    @staticmethod
    def _extract_json_text(content: str) -> str:
        text = (content or "").strip()
        if not text:
            return ""
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return ""
        return text[start : end + 1]

    @staticmethod
    def _distribution_sum_check(block: Dict[str, Dict[str, float]], block_name: str) -> None:
        min_sum = sum(v["min"] for v in block.values())
        max_sum = sum(v["max"] for v in block.values())
        if min_sum > 100.0:
            raise ValueError(f"{block_name} min 总和必须 <= 100，当前 {min_sum:.2f}")
        if max_sum < 100.0:
            raise ValueError(f"{block_name} max 总和必须 >= 100，当前 {max_sum:.2f}")

    def _validate_range(self, node: Dict[str, Any], name: str) -> Dict[str, float]:
        if "min" not in node or "max" not in node:
            raise ValueError(f"{name} 缺少 min 或 max 字段")
        min_v = self._to_decimal_2(node["min"])
        max_v = self._to_decimal_2(node["max"])
        if min_v < 0 or max_v < 0 or min_v > 100 or max_v > 100:
            raise ValueError(f"{name} 必须满足 0<=min/max<=100")
        if min_v > max_v:
            raise ValueError(f"{name} 必须满足 min<=max")
        return {"min": min_v, "max": max_v}

    def _normalize_and_validate_output(self, payload: Dict[str, Any]) -> Dict[str, Any]:
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

        duration = self._validate_range(general.get("duration_years") or {}, "组合久期")
        single_weight = self._validate_range(general.get("single_bond_weight_pct") or {}, "单券权重")

        min_rating = str(general.get("min_rating", "不限")).strip() or "不限"
        if min_rating not in RATING_ENUM:
            raise ValueError(f"最低评级不合法：{min_rating}")

        fund = self._to_decimal_2(general.get("portfolio_fund_wan", 0.0))
        if fund < 0:
            raise ValueError("组合资金必须 >= 0")

        normalized_by_category: Dict[str, Dict[str, float]] = {}
        for key in CATEGORY_KEYS:
            if key not in by_category:
                raise ValueError(f"按种类缺少字段：{key}")
            normalized_by_category[key] = self._validate_range(by_category[key], f"按种类/{key}")

        normalized_by_type: Dict[str, Dict[str, float]] = {}
        for key in TYPE_KEYS:
            if key not in by_type:
                raise ValueError(f"按类型缺少字段：{key}")
            normalized_by_type[key] = self._validate_range(by_type[key], f"按类型/{key}")

        self._distribution_sum_check(normalized_by_category, "按种类")
        self._distribution_sum_check(normalized_by_type, "按类型")

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

    def _priority_case_sql(self) -> str:
        return " ".join([f"WHEN '{m}' THEN {i}" for i, m in enumerate(ANALYSIS_MODEL_PRIORITY)])

    def _query_news_reason_rows(self, target_news_date: date) -> Tuple[List[Dict[str, Any]], Optional[datetime]]:
        priority_cases = self._priority_case_sql()
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT n.id, n.title, n.pub_time,
                           COALESCE(a.direction, '') AS direction,
                           COALESCE(a.reason, '') AS reason,
                           a.model
                    FROM news n
                    JOIN analysis a ON a.news_id = n.id
                    WHERE DATE(n.pub_time) = %s
                      AND a.reason IS NOT NULL
                      AND TRIM(a.reason) <> ''
                      AND a.model = (
                          SELECT a2.model
                          FROM analysis a2
                          WHERE a2.news_id = n.id
                          ORDER BY CASE a2.model
                              {priority_cases}
                              ELSE 999
                          END
                          LIMIT 1
                      )
                    ORDER BY n.pub_time ASC
                    """,
                    (target_news_date,),
                )
                rows = cur.fetchall()

        items: List[Dict[str, Any]] = []
        latest_pub_time: Optional[datetime] = None
        for row in rows:
            pub_time = row[2]
            if isinstance(pub_time, datetime):
                latest_pub_time = pub_time if latest_pub_time is None else max(latest_pub_time, pub_time)
            items.append(
                {
                    "news_id": row[0],
                    "title": row[1],
                    "pub_time": row[2],
                    "direction": row[3],
                    "reason": row[4],
                    "model": row[5],
                }
            )
        return items, latest_pub_time

    @staticmethod
    def _build_data_version(latest_news_pub_time: Optional[datetime]) -> str:
        if not isinstance(latest_news_pub_time, datetime):
            return "none"
        return latest_news_pub_time.strftime("%Y%m%d%H")

    @staticmethod
    def _build_cache_key(target_news_date: date, model_name: str, data_version: str) -> str:
        raw = f"{target_news_date.isoformat()}|{model_name}|schema_v1|{data_version}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _format_dt(value: Optional[datetime]) -> Optional[str]:
        if not isinstance(value, datetime):
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")

    def _load_cached_success(self, cache_key: str) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT output_json, model_name, news_count, window_start, window_end,
                           latest_news_pub_time, latency_ms, request_id
                    FROM portfolio_strategy_analysis_cache
                    WHERE cache_key = %s AND status = 'success'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (cache_key,),
                )
                row = cur.fetchone()

        if not row:
            return None
        output_json = row[0]
        if isinstance(output_json, str):
            output_json = json.loads(output_json)

        return {
            "data": output_json,
            "meta": {
                "cache_hit": True,
                "model_name": row[1],
                "news_count": row[2] or 0,
                "window_start": self._format_dt(row[3]),
                "window_end": self._format_dt(row[4]),
                "latest_news_pub_time": self._format_dt(row[5]),
                "latency_ms": row[6],
                "request_id": row[7],
            },
        }

    def _upsert_running(
        self,
        cache_key: str,
        target_news_date: date,
        request_id: str,
        news_ids: List[int],
        news_count: int,
        window_start: datetime,
        window_end: datetime,
        latest_news_pub_time: Optional[datetime],
    ) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO portfolio_strategy_analysis_cache (
                        cache_key, target_news_date, model_name, status, output_json,
                        news_count, news_ids_json, window_start, window_end,
                        latest_news_pub_time, request_id, error_message,
                        started_at, finished_at, latency_ms
                    ) VALUES (%s, %s, %s, 'running', NULL, %s, %s, %s, %s, %s, %s, NULL, NOW(), NULL, NULL)
                    ON DUPLICATE KEY UPDATE
                        target_news_date = VALUES(target_news_date),
                        model_name = VALUES(model_name),
                        status = 'running',
                        output_json = NULL,
                        news_count = VALUES(news_count),
                        news_ids_json = VALUES(news_ids_json),
                        window_start = VALUES(window_start),
                        window_end = VALUES(window_end),
                        latest_news_pub_time = VALUES(latest_news_pub_time),
                        request_id = VALUES(request_id),
                        error_message = NULL,
                        started_at = NOW(),
                        finished_at = NULL,
                        latency_ms = NULL
                    """,
                    (
                        cache_key,
                        target_news_date,
                        self._cfg.model,
                        news_count,
                        json.dumps(news_ids, ensure_ascii=False),
                        window_start,
                        window_end,
                        latest_news_pub_time,
                        request_id,
                    ),
                )
            conn.commit()

    def _finish_success(
        self,
        cache_key: str,
        output_data: Dict[str, Any],
        latency_ms: int,
    ) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE portfolio_strategy_analysis_cache
                    SET status = 'success',
                        output_json = %s,
                        error_message = NULL,
                        finished_at = NOW(),
                        latency_ms = %s
                    WHERE cache_key = %s
                    """,
                    (json.dumps(output_data, ensure_ascii=False), latency_ms, cache_key),
                )
            conn.commit()

    def _finish_fail(self, cache_key: str, error_message: str, latency_ms: int) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE portfolio_strategy_analysis_cache
                    SET status = 'fail',
                        error_message = %s,
                        finished_at = NOW(),
                        latency_ms = %s
                    WHERE cache_key = %s
                    """,
                    (error_message[:65535], latency_ms, cache_key),
                )
            conn.commit()

    def _build_news_material(self, rows: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for i, item in enumerate(rows, start=1):
            pub_time = item["pub_time"]
            ts = pub_time.strftime("%Y-%m-%d %H:%M") if isinstance(pub_time, datetime) else str(pub_time)
            lines.append(
                f"{i}. 时间: {ts} | 标题: {item['title']} | 方向: {item['direction']} | 原因: {item['reason']}"
            )
        return "\n".join(lines)

    def _build_prompt(self, target_news_date: date, rows: List[Dict[str, Any]], correction_hint: str = "") -> str:
        material = self._build_news_material(rows)
        correction_section = f"\n校验错误修正提示：{correction_hint}\n" if correction_hint else ""
        return f"""
你是中国债券市场组合分析助手。请根据新闻及其分析原因，输出“组合筛选字段”的 JSON。

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

    def _call_llm_once(self, prompt: str) -> str:
        response = self._llm_client.chat.completions.create(
            model=self._cfg.model,
            messages=[
                {"role": "system", "content": "你是严格输出 JSON 的债券组合分析助手。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return (response.choices[0].message.content or "").strip()

    def _generate_output_sync(self, target_news_date: date, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        first_prompt = self._build_prompt(target_news_date, rows)
        first_content = self._call_llm_once(first_prompt)

        try:
            parsed = json.loads(self._extract_json_text(first_content))
            return self._normalize_and_validate_output(parsed)
        except Exception as first_error:
            second_prompt = self._build_prompt(target_news_date, rows, correction_hint=str(first_error))
            second_content = self._call_llm_once(second_prompt)
            parsed_second = json.loads(self._extract_json_text(second_content))
            return self._normalize_and_validate_output(parsed_second)

    async def analyze(self, force_refresh: bool = False) -> Dict[str, Any]:
        target_news_date = (datetime.now(self._cfg.tz) - timedelta(days=1)).date()
        window_start, window_end = self._range_to_datetime_window(target_news_date)

        rows, latest_news_pub_time = await asyncio.to_thread(self._query_news_reason_rows, target_news_date)
        if not rows:
            raise RuntimeError("目标新闻日没有可分析的新闻或 reason 数据为空")

        news_ids = [int(item["news_id"]) for item in rows]
        data_version = self._build_data_version(latest_news_pub_time)
        cache_key = self._build_cache_key(target_news_date, self._cfg.model, data_version)

        if not force_refresh:
            cached = await asyncio.to_thread(self._load_cached_success, cache_key)
            if cached:
                return cached

        started_at = datetime.now(self._cfg.tz)
        request_id = str(uuid.uuid4())
        await asyncio.to_thread(
            self._upsert_running,
            cache_key,
            target_news_date,
            request_id,
            news_ids,
            len(news_ids),
            window_start,
            window_end,
            latest_news_pub_time,
        )

        try:
            output = await asyncio.to_thread(self._generate_output_sync, target_news_date, rows)
            latency_ms = int((datetime.now(self._cfg.tz) - started_at).total_seconds() * 1000)
            await asyncio.to_thread(self._finish_success, cache_key, output, latency_ms)
            return {
                "data": output,
                "meta": {
                    "cache_hit": False,
                    "request_id": request_id,
                    "model_name": self._cfg.model,
                    "news_count": len(news_ids),
                    "window_start": self._format_dt(window_start),
                    "window_end": self._format_dt(window_end),
                    "latest_news_pub_time": self._format_dt(latest_news_pub_time),
                    "latency_ms": latency_ms,
                },
            }
        except Exception as exc:
            latency_ms = int((datetime.now(self._cfg.tz) - started_at).total_seconds() * 1000)
            with contextlib.suppress(Exception):
                await asyncio.to_thread(self._finish_fail, cache_key, str(exc), latency_ms)
            raise


_service_instance: Optional[PortfolioStrategyService] = None


def get_portfolio_strategy_service(llm_client: OpenAI) -> PortfolioStrategyService:
    global _service_instance
    if _service_instance is None:
        _service_instance = PortfolioStrategyService(llm_client=llm_client)
    return _service_instance
