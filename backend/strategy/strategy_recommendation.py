"""
AI目标与策略推荐服务。
必需的外部API环境变量：
- STRATEGY_API_BASE_URL 或 EXTERNAL_API_BASE_URL
- BOND_API_BASE_URL 或 EXTERNAL_API_BASE_URL
- KINGSTAR_EMPLOYEE_NO（仅在策略列表API中需要）
可选参数：
- AI_RECOMMENDATION_MAX_TARGETS，默认值为300
- BOND_API_PAGE_SIZE，默认值为10000
"""

import json
import os
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import openai
import requests
from requests import HTTPError

from backend.common.database import get_db_connection
from backend.common.llm_call import get_async_llm_client, llm_completion_with_retry
from backend.common.llm_json import extract_json
from backend.common.llm_logger import log_llm_usage

# 【临时兼容】SaaS 本地快照模式配置
# 通过 config 模块动态读取，而非模块级导入，以便快照脚本能在运行时覆盖
from backend.config import config as _config
from backend.config.config import (
    PORTFOLIO_TZ,
    get_analysis_model_info,
    get_default_analysis_model_name,
    get_requests_proxies,
)

MODEL_NAME = get_default_analysis_model_name()

# 【临时兼容】离线模式下不需要 LLM API key（不走 LLM 调用）
llm_api_key = _config.get_llm_api_key()
if not _config.USE_LOCAL_SNAPSHOT and not llm_api_key:
    raise ValueError("LLM_API_KEY environment variable is not set.")

# 复用 common.llm_call 的缓存异步客户端；离线模式无密钥时返回 None
async_client = get_async_llm_client()

STRATEGY_LIST_PATH = "/v1/strategy/follow_price_point_strategy/list"
BOND_LIST_PATH = "/v1/bondBasisInfo/query"
QUANT_STRATEGY_LIST_PATH = "/qt-research/core/factor/factorBulletinBoard/list/page"
DEFAULT_HTTP_TIMEOUT = 30

# 量化策略API配置（从环境变量读取）
QUANT_STRATEGY_BASE_URL = os.getenv("QUANT_STRATEGY_BASE_URL")
if not _config.USE_LOCAL_SNAPSHOT and not QUANT_STRATEGY_BASE_URL:
    raise ValueError("QUANT_STRATEGY_BASE_URL environment variable is not set.")

QUANT_STRATEGY_TOKEN = os.getenv("QUANT_STRATEGY_TOKEN")
if not _config.USE_LOCAL_SNAPSHOT and not QUANT_STRATEGY_TOKEN:
    raise ValueError("QUANT_STRATEGY_TOKEN environment variable is not set.")


# 带重试的异步 API 调用（最多重试 3 次，指数退避 1s→10s）；
# 重试逻辑收敛到 common.llm_call.llm_completion_with_retry。
async def async_chat_completion(**kwargs):
    """带重试的异步 API 调用"""
    return await llm_completion_with_retry(async_client, **kwargs)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _get_required_base_url(primary_env: str) -> str:
    base_url = (
        os.getenv(primary_env)
        or os.getenv("EXTERNAL_API_BASE_URL")
        or _config.get_llm_base_url()
    )
    if not base_url:
        raise RuntimeError(
            f"{primary_env}, EXTERNAL_API_BASE_URL, or LLM_BASE_URL is required for AI strategy recommendation."
        )
    return base_url


def _get_employee_no() -> str:
    employee_no = os.getenv("KINGSTAR_EMPLOYEE_NO")
    if not employee_no:
        raise RuntimeError("KINGSTAR_EMPLOYEE_NO is required for strategy list API.")
    return employee_no


def _post_json(
    url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=DEFAULT_HTTP_TIMEOUT,
        proxies=get_requests_proxies(),
    )
    try:
        response.raise_for_status()
    except HTTPError as exc:
        raise RuntimeError(
            f"外部业务接口请求失败: HTTP {response.status_code}, url={url}, body={response.text[:500]}"
        ) from exc
    return response.json()


def _day_range(target_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)
    return start, end


def get_news_reasons_for_date(
    target_date: date, model_name: Optional[str] = None
) -> List[str]:
    selected_model = model_name or MODEL_NAME
    start, end = _day_range(target_date)

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT a.reason
                FROM analysis a
                JOIN news n ON n.id = a.news_id
                WHERE n.pub_time >= %s
                  AND n.pub_time < %s
                  AND a.model = %s
                  AND a.reason IS NOT NULL
                  AND TRIM(a.reason) <> ''
                ORDER BY n.pub_time DESC, a.created_at DESC, a.news_id DESC
                """,
                (start, end, selected_model),
            )
            rows = cur.fetchall()
    except Exception as exc:
        raise RuntimeError(
            f"查询新闻分析原因数据库失败 (analysis_date={target_date}, model={selected_model}, "
            f"start={start}, end={end}): {exc}"
        ) from exc

    return [row[0] for row in rows]


# =============================================================================
# 字段编码映射表（用于前端展示）
# =============================================================================

# 量化策略 - 因子分类映射
FACTOR_CATEGORY_MAP = {
    "39001": "技术因子",
    "39002": "基本面因子",
    "39003": "自定义因子",
}

# 量化策略 - 因子类型映射
FACTOR_TYPE_MAP = {
    "3": "现券因子",
    "4": "自定义因子",
    "1559114009792917505": "特定因子类型1",
    "1559114009792917506": "特定因子类型2",
    "1567429037549928448": "宏观因子",
    "1564142752714371072": "其他因子类型",
}

# 量化策略 - 研究状态映射
RESEARCH_STATUS_MAP = {
    "38001": "研究中",
    "38003": "已发布",
}

# 量化策略 - 数据频率映射
FREQUENCY_MAP = {
    "59001": "日频",
    "59002": "分钟频",
    "59005": "其他频率",
}

# 量化策略 - 数据源映射
DATA_SOURCE_MAP = {
    "76003": "数据源76003",
    "76004": "期货数据",
    "76014": "外部数据源",
    "76015": "现券数据",
}

# 原有策略 - 策略类型映射
STRATEGY_TYPE_MAP = {
    "1": "follow_price_point (跟价点策略)",
    "2": "interest_rate_spread (利率价差策略)",
    "3": "multi_benchmark (多基准策略)",
}


def _map_code(code: Any, mapping: Dict[str, str], default: str = "未知") -> str:
    """将数字编码映射为可读名称"""
    return mapping.get(str(code), default)


def _strategy_type_name(strategy_type: Any) -> str:
    return _map_code(strategy_type, STRATEGY_TYPE_MAP)


def _normalize_strategy(item: Dict[str, Any]) -> Dict[str, Any]:
    """标准化原有交易策略数据"""
    definition = item.get("strategyDefinition") or {}
    strategy_type = item.get("strategyType") or definition.get("strategyType")
    strategy_type_str = str(strategy_type or "")

    description_parts = [
        f"type={_strategy_type_name(strategy_type)}",
        f"version={item.get('version') or definition.get('version') or ''}",
        f"scope={definition.get('scope') or ''}",
        f"reference={definition.get('reference') or definition.get('referenceSecurityID') or ''}",
    ]

    return {
        "id": str(item.get("id") or definition.get("strategyId") or ""),
        "name": item.get("strategyName") or definition.get("strategyName") or "",
        # 统一字段名
        "category": _strategy_type_name(strategy_type),
        "category_code": strategy_type_str,
        "sub_category": "",
        "source_type": "trading_strategy",
        "source_type_label": "交易策略",
        "status": "active",
        "status_label": "启用",
        "risk_level": "medium",
        "description": "; ".join(
            part for part in description_parts if part.split("=", 1)[1]
        ),
        # 详情字段
        "details": {
            "strategy_type": strategy_type_str,
            "strategy_type_label": _strategy_type_name(strategy_type),
            "version": item.get("version") or definition.get("version") or "",
            "scope": definition.get("scope") or "",
            "reference": definition.get("reference")
            or definition.get("referenceSecurityID")
            or "",
            "product_type": item.get("productType") or "",
            "approval_status": item.get("approvalStatus") or "",
        },
        "create_time": item.get("createTime") or "",
        "modify_time": item.get("lastUpdatedDate") or "",
        "raw": item,
    }


def get_available_strategies() -> List[Dict[str, Any]]:
    # 【临时兼容】SaaS 无法访问内网 API，从本地快照文件读取策略列表
    if _config.USE_LOCAL_SNAPSHOT:
        snapshot_path = _config.SNAPSHOT_DIR / "trading_strategies.json"
        if not snapshot_path.exists():
            raise RuntimeError(
                f"本地快照文件不存在: {snapshot_path}，请先在内网环境运行"
                f" scripts/generate_snapshot.py 生成快照"
            )
        with open(snapshot_path, "r", encoding="utf-8") as f:
            return json.load(f)

    base_url = _get_required_base_url("STRATEGY_API_BASE_URL")
    employee_no = _get_employee_no()
    payload: Dict[str, Any] = {}
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "x-kingstar-employee-no": employee_no,
    }
    url = _join_url(base_url, STRATEGY_LIST_PATH)
    result = _post_json(url, payload, headers)

    rows = result.get("data") or []
    if not isinstance(rows, list):
        raise RuntimeError(
            f"策略列表接口返回 data 字段不是数组 (url={url}, data_type={type(rows).__name__})"
        )
    return [_normalize_strategy(row) for row in rows if isinstance(row, dict)]


def _normalize_quant_strategy(item: Dict[str, Any]) -> Dict[str, Any]:
    """标准化量化策略数据

    将数字编码字段转换为可读的中文名称，便于前端直接展示。
    字段设计与原有策略的 _normalize_strategy 保持统一。
    """
    factor_type = item.get("factor_type") or ""
    factor_category = item.get("factor_category") or ""
    research_status = item.get("research_status") or ""
    frequency = item.get("frequency") or ""
    data_source = item.get("data_source") or ""

    factor_type_str = str(factor_type)
    factor_category_str = str(factor_category)
    research_status_str = str(research_status)
    frequency_str = str(frequency)
    data_source_str = str(data_source)

    # 编码转可读名称
    category_label = _map_code(factor_category_str, FACTOR_CATEGORY_MAP)
    factor_type_label = _map_code(factor_type_str, FACTOR_TYPE_MAP)
    status_label = _map_code(research_status_str, RESEARCH_STATUS_MAP)
    frequency_label = _map_code(frequency_str, FREQUENCY_MAP)
    data_source_label = _map_code(data_source_str, DATA_SOURCE_MAP)

    description_parts = [
        f"因子类型={factor_type_label}",
        f"分类={category_label}",
        f"状态={status_label}",
        f"频率={frequency_label}",
        f"数据源={data_source_label}",
        f"品种={item.get('variety_code') or ''}",
    ]

    return {
        "id": str(item.get("factor_id") or item.get("exam_id") or ""),
        "name": item.get("factor_name") or "",
        # 统一字段名（与原有策略对齐）
        "category": category_label,
        "category_code": factor_category_str,
        "sub_category": factor_type_label,
        "sub_category_code": factor_type_str,
        "source_type": "quant_strategy",
        "source_type_label": "量化策略",
        "status": status_label,
        "status_code": research_status_str,
        "risk_level": "medium",
        "description": "; ".join(
            part for part in description_parts if part.split("=", 1)[1]
        ),
        # 详情字段
        "details": {
            "factor_type": factor_type_str,
            "factor_type_label": factor_type_label,
            "factor_category": factor_category_str,
            "factor_category_label": category_label,
            "research_status": research_status_str,
            "research_status_label": status_label,
            "frequency": frequency_str,
            "frequency_label": frequency_label,
            "data_source": data_source_str,
            "data_source_label": data_source_label,
            "variety_code": item.get("variety_code") or "",
            "exam_id": item.get("exam_id") or "",
            "exam_interval": item.get("exam_interval") or "",
            "ic_window": item.get("ic_window"),
            "subject_category": item.get("subject_category") or "",
            "breed_code": item.get("breed_code") or "",
            "original_factor_category": item.get("original_factor_category") or "",
        },
        "create_time": item.get("create_time") or "",
        "modify_time": item.get("modify_time") or "",
        "raw": item,
    }


def get_available_quant_strategies(
    page_size: int = 100, page_num: int = 1
) -> List[Dict[str, Any]]:
    """获取可用的量化策略列表

    Args:
        page_size: 每页数量，默认100
        page_num: 页码，默认1
        【临时兼容】离线模式下忽略分页参数，直接返回全量快照数据

    Returns:
        标准化后的量化策略列表
    """
    # 【临时兼容】SaaS 无法访问内网 API，从本地快照文件读取量化策略列表
    if _config.USE_LOCAL_SNAPSHOT:
        snapshot_path = _config.SNAPSHOT_DIR / "quant_strategies.json"
        if not snapshot_path.exists():
            raise RuntimeError(
                f"本地快照文件不存在: {snapshot_path}，请先在内网环境运行"
                f" scripts/generate_snapshot.py 生成快照"
            )
        with open(snapshot_path, "r", encoding="utf-8") as f:
            return json.load(f)

    url = _join_url(QUANT_STRATEGY_BASE_URL, QUANT_STRATEGY_LIST_PATH)

    # 构建查询参数
    params = {
        "factor_type_list": "1564142752714371072,1567429037549928448,4,1559114009792917505,1,1559114009792917506,3,2",
        "research_status_list": "38001,38003",
        "factor_category_list": "39002,39003,39001",
        "page_size": str(page_size),
        "page_num": str(page_num),
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": QUANT_STRATEGY_TOKEN,
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=DEFAULT_HTTP_TIMEOUT,
            proxies=get_requests_proxies(),
        )
        response.raise_for_status()
        result = response.json()
    except HTTPError as exc:
        raise RuntimeError(
            f"量化策略接口请求失败: HTTP {response.status_code}, url={url}, body={response.text[:500]}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"量化策略接口请求异常: url={url}, error={exc}") from exc

    # 解析返回数据
    # 接口返回格式: {"err_msg": "success", "err_data": {"total": 35, "list": [...]}}
    err_data = result.get("err_data") or {}
    records = err_data.get("list") or []

    if not isinstance(records, list):
        raise RuntimeError(
            f"量化策略接口返回 err_data.list 不是数组 (url={url}, list_type={type(records).__name__})"
        )

    strategies = [
        _normalize_quant_strategy(row) for row in records if isinstance(row, dict)
    ]

    return strategies


def get_all_strategies() -> Dict[str, Any]:
    """统一获取所有策略（量化策略 + 原有交易策略）

    返回统一格式的策略列表，方便前端展示。
    """
    quant_strategies = []
    trading_strategies = []
    errors: List[Dict[str, Any]] = []

    # 获取量化策略
    try:
        quant_strategies = get_available_quant_strategies(page_size=100, page_num=1)
    except Exception as exc:
        errors.append({"source": "quant_strategy", "error": str(exc)})

    # 获取原有交易策略
    try:
        trading_strategies = get_available_strategies()
    except Exception as exc:
        errors.append({"source": "trading_strategy", "error": str(exc)})

    return {
        "strategies": quant_strategies + trading_strategies,
        "quant_strategies": quant_strategies,
        "trading_strategies": trading_strategies,
        "total": len(quant_strategies) + len(trading_strategies),
        "quant_total": len(quant_strategies),
        "trading_total": len(trading_strategies),
        "errors": errors,
    }


def _normalize_bond(item: Dict[str, Any]) -> Dict[str, Any]:
    code = item.get("bondCode") or item.get("securityID") or item.get("code") or ""
    name = (
        item.get("bondShortName")
        or item.get("symbol")
        or item.get("securityName")
        or code
    )
    sign = item.get("sign") or "BOND"
    security_desc = item.get("securityDesc") or ""
    description_parts = [
        f"category={security_desc}",
        f"rating={item.get('rating') or ''}",
        f"term={item.get('termToMaturity') or ''}",
        f"coupon={item.get('couponRate') or ''}",
        f"issuer={item.get('issuer') or ''}",
    ]
    return {
        "code": str(code),
        "name": str(name),
        "type": str(sign or security_desc or "bond"),
        "description": "; ".join(
            part for part in description_parts if part.split("=", 1)[1]
        ),
        "raw": item,
    }


def get_available_targets() -> List[Dict[str, Any]]:
    # 【临时兼容】SaaS 无法访问内网 API，从本地快照文件读取债券标的列表
    if _config.USE_LOCAL_SNAPSHOT:
        snapshot_path = _config.SNAPSHOT_DIR / "targets.json"
        if not snapshot_path.exists():
            raise RuntimeError(
                f"本地快照文件不存在: {snapshot_path}，请先在内网环境运行"
                f" scripts/generate_snapshot.py 生成快照"
            )
        with open(snapshot_path, "r", encoding="utf-8") as f:
            return json.load(f)

    base_url = _get_required_base_url("BOND_API_BASE_URL")
    page_size = int(os.getenv("BOND_API_PAGE_SIZE", "10000"))
    max_targets = int(os.getenv("AI_RECOMMENDATION_MAX_TARGETS", "300"))
    page_no = 1
    targets: List[Dict[str, Any]] = []
    url = _join_url(base_url, BOND_LIST_PATH)

    while True:
        payload = {"data": {"pageNo": str(page_no), "pageSize": str(page_size)}}
        headers = {
            "Content-Type": "application/json",
        }
        result = _post_json(url, payload, headers)

        data = result.get("data") or {}
        records = data.get("records") or []
        if not isinstance(records, list):
            raise RuntimeError(
                f"债券列表接口返回 data.records 不是数组 (url={url}, pageNo={page_no}, records_type={type(records).__name__})"
            )

        targets.extend(_normalize_bond(row) for row in records if isinstance(row, dict))
        pages = int(data.get("pages") or 1)
        if page_no >= pages:
            break
        page_no += 1

    return targets[:max_targets]


def _format_list(items: List[Dict[str, Any]], fields: List[str]) -> str:
    lines = []
    for item in items:
        values = [str(item.get(field, "")) for field in fields]
        lines.append("- " + " | ".join(values))
    return "\n".join(lines) if lines else "No available data"


async def analyze(
    news_summary: List[str],
    strategy_list: List[Dict[str, Any]],
    target_list: List[Dict[str, Any]],
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    selected_model_name = model_name or MODEL_NAME
    provider_model = get_analysis_model_info(selected_model_name)["provider_model"]

    news_text = "\n".join(
        f"{idx}. {reason}" for idx, reason in enumerate(news_summary, 1)
    )
    if not news_text:
        news_text = "No analysis.reason records were found for the selected date."

    prompt = f"""
你是一名中国债券市场及策略分析师。仅依据提供的新闻情绪分析、策略清单和债券标的清单，推荐债券标的与配套投资策略。

新闻情绪分析：
{news_text}

策略清单：
{_format_list(strategy_list, ["id", "name", "category", "risk_level", "description"])}

债券标的清单：
{_format_list(target_list, ["code", "name", "type", "description"])}

规则：
1. 仅输出标准合法的JSON格式内容。
2. 每一条推荐组合必须分别选用清单内的一只标的和一项策略。
3. 推荐数量控制在1至5条。若现有信息不足，需给出偏保守的配置建议，并说明信息欠缺之处。
4. 禁止给出具体买卖点位、价格预判，以及承诺保本、保收益类表述。
5. 推荐理由需完整体现逻辑链路：新闻信号 → 市场判断 → 标的选择 → 策略匹配。

JSON格式要求：
{{
  "market_overview": "整体市场观点，控制在200字以内",
  "sentiment_summary": "核心关键词及情绪走向",
  "risk_alert": "主要风险提示",
  "recommendations": [
    {{
      "priority": 1,
      "target": {{"code": "", "name": "", "type": ""}},
      "strategy": {{"id": "", "name": ""}},
      "allocation_ratio": "例如 20%",
      "reason": "完整阐述推荐逻辑",
      "expected_holding_period": "例如 1-2周",
      "risk_level": "低|中|高"
    }}
  ],
  "not_recommended": [
    {{"target_code": "", "target_name": "", "reason": ""}}
  ]
}}
"""
    try:
        t0 = time.time()
        response = await async_chat_completion(
            model=provider_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            timeout=600,
        )
        latency_ms = int((time.time() - t0) * 1000)

        # 记录 Token 消耗
        if response.usage:
            log_llm_usage(
                call_source="strategy",
                model_name=selected_model_name,
                provider_model=provider_model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                success=True,
                latency_ms=latency_ms,
            )
    except openai.APIError as exc:
        latency_ms = int((time.time() - t0) * 1000) if "t0" in dir() else None
        log_llm_usage(
            call_source="strategy",
            model_name=selected_model_name,
            provider_model=provider_model,
            success=False,
            error_message=f"APIError: {exc.status_code or 'N/A'}, {exc.message}",
            latency_ms=latency_ms,
        )
        raise RuntimeError(
            f"AI API 调用失败 (model={selected_model_name}, provider_model={provider_model}): "
            f"status_code={exc.status_code or 'N/A'}, message={exc.message}"
        ) from exc
    except Exception as exc:
        latency_ms = int((time.time() - t0) * 1000) if "t0" in dir() else None
        log_llm_usage(
            call_source="strategy",
            model_name=selected_model_name,
            provider_model=provider_model,
            success=False,
            error_message=str(exc),
            latency_ms=latency_ms,
        )
        raise RuntimeError(
            f"AI API 调用发生未知异常 (model={selected_model_name}, provider_model={provider_model}): {exc}"
        ) from exc

    raw_content = response.choices[0].message.content
    if not raw_content:
        raise RuntimeError(
            f"AI 返回内容为空 (model={selected_model_name}, provider_model={provider_model})"
        )

    try:
        return extract_json(raw_content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"AI 返回内容 JSON 解析失败 (model={selected_model_name}, provider_model={provider_model}): {exc}"
        ) from exc


def get_cached_recommendation(
    target_date: date, model_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            if model_name:
                cur.execute(
                    """
                    SELECT id, analysis_date, news_summary, outcome, model_name, news_count, created_at, updated_at
                    FROM ai_strategy_recommendation
                    WHERE analysis_date = %s AND model_name = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (target_date, model_name),
                )
            else:
                cur.execute(
                    """
                    SELECT id, analysis_date, news_summary, outcome, model_name, news_count, created_at, updated_at
                    FROM ai_strategy_recommendation
                    WHERE analysis_date = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (target_date,),
                )
            row = cur.fetchone()
    except Exception as exc:
        raise RuntimeError(
            f"查询推荐缓存表失败 (analysis_date={target_date}): {exc}"
        ) from exc

    if not row:
        return None

    outcome = row[3]
    if isinstance(outcome, str):
        try:
            outcome = json.loads(outcome)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"缓存中 outcome 字段 JSON 解析失败 (analysis_date={target_date}, id={row[0]}): {exc}"
            ) from exc
    return {
        "id": row[0],
        "analysis_date": str(row[1]),
        "news_summary": row[2],
        "outcome": outcome,
        "model_name": row[4],
        "news_count": row[5],
        "created_at": str(row[6]) if row[6] else None,
        "updated_at": str(row[7]) if row[7] else None,
    }


def save_recommendation(
    target_date: date,
    news_summary: List[str],
    outcome: Dict[str, Any],
    model_name: str,
) -> None:
    try:
        outcome_json = json.dumps(outcome, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"推荐结果序列化 JSON 失败 (analysis_date={target_date}): {exc}"
        ) from exc

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO ai_strategy_recommendation
                    (analysis_date, news_summary, outcome, model_name, news_count)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    news_summary = VALUES(news_summary),
                    outcome = VALUES(outcome),
                    model_name = VALUES(model_name),
                    news_count = VALUES(news_count),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    target_date,
                    "\n".join(news_summary),
                    outcome_json,
                    model_name,
                    len(news_summary),
                ),
            )
            conn.commit()
    except Exception as exc:
        raise RuntimeError(
            f"写入推荐结果到数据库失败 (analysis_date={target_date}, model_name={model_name}): {exc}"
        ) from exc


async def get_or_create_recommendation(
    target_date: Optional[date] = None,
    force_refresh: bool = False,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    selected_date = target_date or (
        datetime.now(PORTFOLIO_TZ).date() - timedelta(days=1)
    )
    selected_model_name = model_name or MODEL_NAME

    try:
        cached = None if force_refresh else get_cached_recommendation(
            selected_date, selected_model_name
        )
        if cached:
            return {"success": True, "from_cache": True, "data": cached}
    except Exception as exc:
        raise RuntimeError(
            f"读取缓存失败 (analysis_date={selected_date}, force_refresh={force_refresh}): {exc}"
        ) from exc

    try:
        news_summary = get_news_reasons_for_date(selected_date, selected_model_name)
    except Exception as exc:
        raise RuntimeError(
            f"获取新闻分析原因失败 (analysis_date={selected_date}, model_name={selected_model_name}): {exc}"
        ) from exc

    try:
        target_list = get_available_targets()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"获取可用债券目标列表失败: {exc}") from exc

    try:
        strategy_list = get_available_strategies()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"获取可用策略列表失败: {exc}") from exc

    try:
        outcome = await analyze(
            news_summary=news_summary,
            strategy_list=strategy_list,
            target_list=target_list,
            model_name=selected_model_name,
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"AI 分析过程异常 (model={selected_model_name}): {exc}"
        ) from exc

    try:
        save_recommendation(selected_date, news_summary, outcome, selected_model_name)
    except Exception as exc:
        raise RuntimeError(
            f"保存推荐结果到数据库失败 (analysis_date={selected_date}): {exc}"
        ) from exc

    try:
        data = get_cached_recommendation(selected_date, selected_model_name)
    except Exception as exc:
        raise RuntimeError(
            f"保存后回读推荐结果失败 (analysis_date={selected_date}): {exc}"
        ) from exc

    return {"success": True, "from_cache": False, "data": data}


def get_latest_recommendation() -> Optional[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT analysis_date
                FROM ai_strategy_recommendation
                ORDER BY analysis_date DESC
                LIMIT 1
                """)
            row = cur.fetchone()
    except Exception as exc:
        raise RuntimeError(f"查询最新推荐日期失败: {exc}") from exc

    if not row:
        return None
    return get_cached_recommendation(row[0])


def get_recommendation_history(limit: int = 50) -> List[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, analysis_date, outcome, model_name, news_count, created_at, updated_at
                FROM ai_strategy_recommendation
                ORDER BY analysis_date DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    except Exception as exc:
        raise RuntimeError(f"查询推荐历史列表失败: {exc}") from exc

    history = []
    for row in rows:
        outcome = row[2]
        if isinstance(outcome, str):
            try:
                outcome = json.loads(outcome)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"历史记录中 outcome JSON 解析失败 (id={row[0]}, analysis_date={row[1]}): {exc}"
                ) from exc
        history.append(
            {
                "id": row[0],
                "analysis_date": str(row[1]),
                "outcome": outcome,
                "model_name": row[3],
                "news_count": row[4],
                "created_at": str(row[5]) if row[5] else None,
                "updated_at": str(row[6]) if row[6] else None,
            }
        )
    return history
