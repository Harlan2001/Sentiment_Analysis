"""
策略与标的变动对比 — 服务层。
提供快照生成、列表查询、版本对比三个核心功能。

依赖：
- analysis.reason（新闻摘要）作为 LLM 输入
- 快照写入 strategy_change_snapshot 表
- LLM 调用复用 kingstar API（与 ai_strategy_recommendation 一致）
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from backend.common.database import get_db_connection
from backend.common.llm_logger import log_llm_usage
from backend.config.config import (
    create_openai_http_client,
    get_analysis_model_info,
    get_default_analysis_model_name,
)

logger = logging.getLogger("change_router")

CHANGE_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_MODEL = get_default_analysis_model_name()

# LLM client（复用 kingstar 环境变量）
_kingstar_API_KEY = os.getenv("kingstar_API_KEY")
_kingstar_BASE_URL = os.getenv("kingstar_BASE_URL")


def _get_llm_client():
    from openai import OpenAI

    return OpenAI(
        api_key=_kingstar_API_KEY,
        base_url=_kingstar_BASE_URL,
        http_client=create_openai_http_client(),
    )


# ============================================================
# 数据库操作
# ============================================================
def latest_snapshot() -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, version_time, window_start, window_end, news_total, "
                "news_added_count, news_removed_count, stock_recommend, strategy_recommend, "
                "summary_stats, generate_status, create_time "
                "FROM strategy_change_snapshot ORDER BY version_time DESC LIMIT 1"
            )
            row = cur.fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def snapshot_by_id(snapshot_id: int) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, version_time, window_start, window_end, news_total, "
                "news_added_count, news_removed_count, stock_recommend, strategy_recommend, "
                "summary_stats, generate_status, create_time "
                "FROM strategy_change_snapshot WHERE id = %s",
                (snapshot_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def snapshot_by_version_time(version_time: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, version_time, window_start, window_end, news_total, "
                "news_added_count, news_removed_count, stock_recommend, strategy_recommend, "
                "summary_stats, generate_status, create_time "
                "FROM strategy_change_snapshot WHERE version_time = %s",
                (version_time,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def list_snapshots(hours: int = 168) -> List[Dict[str, Any]]:
    since = datetime.now(CHANGE_TZ) - timedelta(hours=hours)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, version_time, window_start, window_end, news_total, "
                "news_added_count, news_removed_count, "
                "JSON_LENGTH(stock_recommend) AS stock_count, "
                "JSON_LENGTH(strategy_recommend) AS strategy_count, "
                "generate_status, create_time "
                "FROM strategy_change_snapshot "
                "WHERE version_time >= %s "
                "ORDER BY version_time DESC",
                (since.strftime("%Y-%m-%d %H:%M:%S"),),
            )
            rows = cur.fetchall()
    return [
        {
            "id": row[0],
            "version_time": _fmt(row[1]),
            "window_start": _fmt(row[2]),
            "window_end": _fmt(row[3]),
            "news_total": row[4],
            "news_added_count": row[5],
            "news_removed_count": row[6],
            "stock_count": row[7] or 0,
            "strategy_count": row[8] or 0,
            "generate_status": row[9],
            "create_time": _fmt(row[10]),
        }
        for row in rows
    ]


def save_snapshot(snapshot: Dict[str, Any]) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategy_change_snapshot
                    (version_time, window_start, window_end, news_total,
                     news_added_count, news_removed_count,
                     stock_recommend, strategy_recommend, summary_stats, generate_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    snapshot["version_time"],
                    snapshot["window_start"],
                    snapshot["window_end"],
                    snapshot["news_total"],
                    snapshot.get("news_added_count", 0),
                    snapshot.get("news_removed_count", 0),
                    json.dumps(snapshot["stock_recommend"], ensure_ascii=False),
                    json.dumps(snapshot["strategy_recommend"], ensure_ascii=False),
                    json.dumps(snapshot.get("summary_stats", {}), ensure_ascii=False),
                    snapshot.get("generate_status", 1),
                ),
            )
            conn.commit()
            cur.execute("SELECT LAST_INSERT_ID()")
            return cur.fetchone()[0]


# ============================================================
# 工具函数
# ============================================================


def _fmt(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _row_to_dict(row) -> Dict[str, Any]:
    def _parse_json(val):
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val
        return val

    return {
        "id": row[0],
        "version_time": _fmt(row[1]),
        "window_start": _fmt(row[2]),
        "window_end": _fmt(row[3]),
        "news_total": row[4],
        "news_added_count": row[5],
        "news_removed_count": row[6],
        "stock_recommend": _parse_json(row[7]),
        "strategy_recommend": _parse_json(row[8]),
        "summary_stats": _parse_json(row[9]),
        "generate_status": row[10],
        "create_time": _fmt(row[11]),
    }


def _build_model_priority_case() -> str:
    """构建分析模型优先级 CASE WHEN 子句（doubao > deepseek > ...）"""
    from backend.config.config import ANALYSIS_MODEL_PRIORITY

    return " ".join(
        [f"WHEN '{m}' THEN {i}" for i, m in enumerate(ANALYSIS_MODEL_PRIORITY)]
    )


def get_latest_news_pub_time() -> Optional[datetime]:
    """查询 news 表中最新一条新闻的 pub_time（数据源时间，非服务器时间）"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(pub_time) FROM news")
            row = cur.fetchone()
    if row and row[0]:
        dt = row[0]
        if isinstance(dt, datetime):
            return dt.replace(tzinfo=CHANGE_TZ) if dt.tzinfo is None else dt
    return None


def compute_window_from_news() -> (
    Tuple[Optional[datetime], Optional[datetime], Optional[datetime]]
):
    """
    基于 news.pub_time 计算 24h 滚动窗口，返回 (version_time, window_start, window_end)。

    时间取整规则（ceil 到整点）：
      - version_time: 最新 pub_time 所在的整点小时末（如 22:41 → 23:00, 22:00 → 22:00）
      - window_end: 同 version_time
      - window_start: window_end - 24h

    这样 latest=22:41 时 window=(昨日23:00, 今日23:00)，22:41 的文章包含在内。
    如果 news 表为空，返回 (None, None, None)。
    """
    latest = get_latest_news_pub_time()
    if latest is None:
        return None, None, None

    # ceil 到整点：非整点则进到下一小时
    hour_floor = latest.replace(minute=0, second=0, microsecond=0)
    if latest > hour_floor:
        version_time = hour_floor + timedelta(hours=1)
    else:
        version_time = hour_floor

    window_end = version_time
    window_start = window_end - timedelta(hours=24)
    return version_time, window_start, window_end


def count_news_raw(window_start: datetime, window_end: datetime) -> int:
    """统计窗口内 news 表中全部新闻数（含未分析的）"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM news WHERE pub_time >= %s AND pub_time <= %s",
                (window_start.replace(tzinfo=None), window_end.replace(tzinfo=None)),
            )
            row = cur.fetchone()
    return row[0] if row else 0


def query_news_ids_analyzed(window_start: datetime, window_end: datetime) -> set:
    """查询窗口内已完成分析（有 reason）的新闻ID集合，按模型优先级去重（兼容 MySQL 5.x）"""
    priority_cases = _build_model_priority_case()

    sql = f"""
        SELECT DISTINCT n.id AS news_id
        FROM news n
        JOIN analysis a ON a.news_id = n.id
        LEFT JOIN analysis a2 ON a2.news_id = a.news_id
            AND a2.reason IS NOT NULL
            AND TRIM(a2.reason) <> ''
            AND CASE a2.model {priority_cases} ELSE 999 END
              < CASE a.model {priority_cases} ELSE 999 END
        WHERE n.pub_time >= %s
          AND n.pub_time <= %s
          AND a.reason IS NOT NULL
          AND TRIM(a.reason) <> ''
          AND a2.news_id IS NULL
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (window_start.replace(tzinfo=None), window_end.replace(tzinfo=None)),
            )
            return {row[0] for row in cur.fetchall()}


def extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # try to find JSON block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


# ============================================================
# 新闻查询（复用 ai_strategy_recommendation 的查询模式）
# ============================================================


def query_news_for_window(
    window_start: datetime, window_end: datetime
) -> List[Dict[str, Any]]:
    """查询窗口内的所有新闻，已分析的按模型优先级去重，未分析的也一并返回（content 作为 fallback）。"""
    from backend.config.config import ANALYSIS_MODEL_PRIORITY

    priority_map: Dict[str, int] = {m: i for i, m in enumerate(ANALYSIS_MODEL_PRIORITY)}

    sql = """
        SELECT n.id AS news_id, n.title, n.pub_time, n.content,
               a.direction, a.reason, a.model
        FROM news n
        LEFT JOIN analysis a ON a.news_id = n.id
            AND a.reason IS NOT NULL
            AND TRIM(a.reason) <> ''
        WHERE n.pub_time >= %s
          AND n.pub_time <= %s
        ORDER BY n.pub_time ASC, n.id ASC
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (window_start.replace(tzinfo=None), window_end.replace(tzinfo=None)),
            )
            rows = cur.fetchall()

    # 按模型优先级去重：同一条新闻有多条分析时，取最高优先级；无分析的行（model=NULL）直接保留
    seen: Dict[int, tuple] = {}
    for row in rows:
        news_id = row[0]
        model = row[6]
        if news_id not in seen:
            seen[news_id] = row
        elif model and model in priority_map:
            existing_model = seen[news_id][6]
            existing_rank = (
                priority_map.get(existing_model, 999) if existing_model else 999
            )
            new_rank = priority_map.get(model, 999)
            if new_rank < existing_rank:
                seen[news_id] = row

    result = [
        {
            "news_id": row[0],
            "title": row[1],
            "pub_time": row[2],
            "content": row[3] or "",
            "direction": (row[4] or "").strip(),
            "reason": row[5] or "",
            "model": row[6] or "",
        }
        for row in seen.values()
    ]
    # 按 pub_time 排序（注意：pub_time 可能为 None 或 str，datetime 优先）
    result.sort(
        key=lambda x: (
            x["pub_time"]
            if isinstance(x["pub_time"], datetime)
            else (x["pub_time"] or "")
        )
    )
    return result


# ============================================================
# LLM 策略生成
# ============================================================


def _build_reason_text(news_rows: List[Dict[str, Any]]) -> str:
    lines = []
    for idx, item in enumerate(news_rows, 1):
        pub_time = item["pub_time"]
        ts = (
            pub_time.strftime("%Y-%m-%d %H:%M")
            if isinstance(pub_time, datetime)
            else str(pub_time)
        )
        reason = (item.get("reason") or "").strip()
        if not reason:
            # 未分析新闻：优先用 content 前 200 字作为摘要
            content = (item.get("content") or "").strip()
            if content:
                reason = "【未分析】" + (
                    content[:200] + "…" if len(content) > 200 else content
                )
            else:
                reason = "（暂无分析摘要）"
        lines.append(
            f"{idx}. 时间: {ts} | 方向: {item['direction']} | 标题: {item['title']} | 摘要: {reason}"
        )
    return "\n".join(lines) if lines else "当前窗口内暂无有效新闻。"


def generate_recommendations(
    news_rows: List[Dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """调用 LLM 生成标的推荐 + 策略推荐"""
    selected_model = model_name or DEFAULT_MODEL
    provider_model = get_analysis_model_info(selected_model)["provider_model"]

    reason_text = _build_reason_text(news_rows)

    prompt = f"""
你是一名中国债券市场及策略分析师。请根据以下时间窗口内的新闻摘要，推荐债券标的与配套投资策略。

时间窗口：{window_start.strftime('%Y-%m-%d %H:%M')} 到 {window_end.strftime('%Y-%m-%d %H:%M')}
新闻条数：{len(news_rows)}

新闻摘要：
{reason_text}

规则：
1. 仅输出标准合法的 JSON，不要 Markdown，不要解释文字。
2. 标的推荐（stock_recommend）：基于新闻情绪推荐 3—8 只债券标的。每只标的需包含 code（标的代码）、name（名称）、rating（评级：强烈推荐/推荐/中性推荐/不建议）、weight（权重 1—100）、reason（推荐理由）、tags（关联标签数组）、risk_level（低/中/高）。
3. 策略推荐（strategy_recommend）：基于新闻信号推荐 1—5 条策略。每条策略需包含 id（策略编号）、name（策略名称）、priority（优先级 1—5，1 最高）、weight（权重 1—100）、target_pool（适用标的代码数组）、trigger_logic（触发逻辑说明）。
4. 市场概览（market_overview）：整体市场观点，控制在 200 字以内。
5. 舆情总览（summary_stats）：包含 sentiment（整体情绪：positive/neutral/negative）、pos_ratio（正面新闻占比 0-1）、neg_ratio（负面新闻占比 0-1）、hot_tags（高频标签 Top5 数组）。
6. 若信息不足，给出偏保守的建议并说明原因。
7. 禁止给出具体买卖点位、价格预判及保本保收益类表述。

JSON 格式：
{{
  "market_overview": "整体市场观点",
  "summary_stats": {{
    "sentiment": "positive|neutral|negative",
    "pos_ratio": 0.00,
    "neg_ratio": 0.00,
    "hot_tags": ["标签1", "标签2", ...]
  }},
  "stock_recommend": [
    {{
      "code": "标的代码",
      "name": "标的名称",
      "rating": "强烈推荐|推荐|中性推荐|不建议",
      "weight": 25,
      "reason": "推荐理由",
      "tags": ["标签"],
      "risk_level": "低|中|高"
    }}
  ],
  "strategy_recommend": [
    {{
      "id": "策略编号",
      "name": "策略名称",
      "priority": 1,
      "weight": 30,
      "target_pool": ["标的代码"],
      "trigger_logic": "触发逻辑说明"
    }}
  ]
}}
"""

    client = _get_llm_client()
    t0 = time.time()
    try:
        response = client.chat.completions.create(
            model=provider_model,
            messages=[
                {
                    "role": "system",
                    "content": "你是严格输出 JSON 的中国债券市场策略分析师。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            timeout=600,
        )
        latency_ms = int((time.time() - t0) * 1000)

        if response.usage:
            log_llm_usage(
                call_source="change",
                model_name=selected_model,
                provider_model=provider_model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                success=True,
                latency_ms=latency_ms,
            )
    except Exception as exc:
        latency_ms = int((time.time() - t0) * 1000)
        log_llm_usage(
            call_source="change",
            model_name=selected_model,
            provider_model=provider_model,
            success=False,
            error_message=str(exc),
            latency_ms=latency_ms,
        )
        raise

    raw = response.choices[0].message.content or ""
    return extract_json(raw)


# ============================================================
# 对比计算
# ============================================================


def compute_diff(
    old_s: Dict[str, Any],
    new_s: Dict[str, Any],
) -> Dict[str, Any]:
    """对比两个快照，计算标的和策略的变动"""

    old_stocks = old_s.get("stock_recommend") or []
    new_stocks = new_s.get("stock_recommend") or []
    old_strategies = old_s.get("strategy_recommend") or []
    new_strategies = new_s.get("strategy_recommend") or []

    # --- 标的对比 ---
    old_stock_codes = {s["code"] for s in old_stocks}
    new_stock_codes = {s["code"] for s in new_stocks}

    old_stock_map = {s["code"]: s for s in old_stocks}
    new_stock_map = {s["code"]: s for s in new_stocks}

    added_codes = new_stock_codes - old_stock_codes
    removed_codes = old_stock_codes - new_stock_codes
    common_codes = old_stock_codes & new_stock_codes

    stock_added = [new_stock_map[c] for c in added_codes]
    stock_removed = [
        {
            "code": c,
            "name": old_stock_map[c].get("name", ""),
            "prev_rating": old_stock_map[c].get("rating", ""),
        }
        for c in removed_codes
    ]

    stock_modified = []
    for code in common_codes:
        old_item = old_stock_map[code]
        new_item = new_stock_map[code]
        changes = {}
        if old_item.get("rating") != new_item.get("rating"):
            changes["old_rating"] = old_item.get("rating", "")
            changes["new_rating"] = new_item.get("rating", "")
        if old_item.get("weight") != new_item.get("weight"):
            changes["old_weight"] = old_item.get("weight", 0)
            changes["new_weight"] = new_item.get("weight", 0)
        if old_item.get("reason") != new_item.get("reason"):
            changes["old_reason"] = old_item.get("reason", "")
            changes["new_reason"] = new_item.get("reason", "")
        if changes:
            stock_modified.append(
                {
                    "code": code,
                    "name": new_item.get("name", ""),
                    **changes,
                }
            )

    # --- 策略对比 ---
    old_strat_ids = {s["id"] for s in old_strategies}
    new_strat_ids = {s["id"] for s in new_strategies}

    old_strat_map = {s["id"]: s for s in old_strategies}
    new_strat_map = {s["id"]: s for s in new_strategies}

    added_ids = new_strat_ids - old_strat_ids
    removed_ids = old_strat_ids - new_strat_ids
    common_ids = old_strat_ids & new_strat_ids

    strategy_added = [new_strat_map[i] for i in added_ids]
    strategy_removed = [
        {
            "id": i,
            "name": old_strat_map[i].get("name", ""),
            "prev_priority": old_strat_map[i].get("priority", 0),
        }
        for i in removed_ids
    ]

    strategy_modified = []
    for sid in common_ids:
        old_item = old_strat_map[sid]
        new_item = new_strat_map[sid]
        changes = {}
        if old_item.get("priority") != new_item.get("priority"):
            changes["old_priority"] = old_item.get("priority", 0)
            changes["new_priority"] = new_item.get("priority", 0)
        if old_item.get("weight") != new_item.get("weight"):
            changes["old_weight"] = old_item.get("weight", 0)
            changes["new_weight"] = new_item.get("weight", 0)
        if old_item.get("trigger_logic") != new_item.get("trigger_logic"):
            changes["old_trigger_logic"] = old_item.get("trigger_logic", "")
            changes["new_trigger_logic"] = new_item.get("trigger_logic", "")
        if changes:
            strategy_modified.append(
                {
                    "id": sid,
                    "name": new_item.get("name", ""),
                    **changes,
                }
            )

    return {
        "base_info": {
            "old_version": old_s.get("version_time"),
            "new_version": new_s.get("version_time"),
            "old_window": [old_s.get("window_start"), old_s.get("window_end")],
            "new_window": [new_s.get("window_start"), new_s.get("window_end")],
            "news_diff": {
                "added_count": new_s.get("news_added_count", 0),
                "removed_count": new_s.get("news_removed_count", 0),
            },
        },
        "diff_summary": {
            "new_stocks": len(stock_added),
            "removed_stocks": len(stock_removed),
            "rating_changes": len([m for m in stock_modified if "old_rating" in m]),
            "strategy_changes": len(strategy_added)
            + len(strategy_removed)
            + len(strategy_modified),
        },
        "stock_changes": {
            "added": stock_added,
            "removed": stock_removed,
            "modified": stock_modified,
        },
        "strategy_changes": {
            "added": strategy_added,
            "removed": strategy_removed,
            "modified": strategy_modified,
        },
    }
