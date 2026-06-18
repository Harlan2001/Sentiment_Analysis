"""
策略与标的变动对比服务。
提供快照生成、列表查询、版本对比三个核心功能。

依赖：
- analysis.reason（新闻摘要）作为 LLM 输入
- 快照写入 strategy_change_snapshot 表
- LLM 调用复用 kingstar API（与 ai_strategy_recommendation 一致）
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from backend.config.config import get_analysis_model_info, get_default_analysis_model_name
from backend.common.database import get_db_connection

logger = logging.getLogger("change_router")

router = APIRouter(prefix="/api/change", tags=["change"])

CHANGE_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_MODEL = get_default_analysis_model_name()

# LLM client（复用 kingstar 环境变量）
_kingstar_API_KEY = os.getenv("kingstar_API_KEY")
_kingstar_BASE_URL = os.getenv("kingstar_BASE_URL")

_openai_client = None


def _get_llm_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=_kingstar_API_KEY, base_url=_kingstar_BASE_URL)
    return _openai_client


# ============================================================
# Pydantic 请求模型
# ============================================================

class TriggerRequest(BaseModel):
    force: bool = False


class CompareRequest(BaseModel):
    old_snapshot_id: Optional[int] = None
    new_snapshot_id: Optional[int] = None
    old_version_time: Optional[str] = None
    new_version_time: Optional[str] = None


# ============================================================
# 数据库操作
# ============================================================

def _create_table_if_not_exists() -> None:
    """自动建表（幂等）"""
    ddl = """
    CREATE TABLE IF NOT EXISTS strategy_change_snapshot (
        id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        version_time     DATETIME        NOT NULL COMMENT '版本整点时间',
        window_start     DATETIME        NOT NULL COMMENT '新闻窗口起始时间',
        window_end       DATETIME        NOT NULL COMMENT '新闻窗口结束时间',
        news_total       INT             NOT NULL DEFAULT 0 COMMENT '窗口内有效新闻总数',
        news_added_count INT             NOT NULL DEFAULT 0 COMMENT '相比上一版本新增新闻数',
        news_removed_count INT           NOT NULL DEFAULT 0 COMMENT '相比上一版本移出新闻数',
        stock_recommend  JSON            NOT NULL COMMENT '标的推荐全量列表',
        strategy_recommend JSON          NOT NULL COMMENT '策略推荐全量列表',
        summary_stats    JSON            DEFAULT NULL COMMENT '窗口舆情总览统计',
        generate_status  TINYINT         NOT NULL DEFAULT 1 COMMENT '0=失败 1=成功 2=待确认',
        create_time      DATETIME        DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uk_version_time (version_time),
        KEY idx_version_time (version_time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略变动快照表-每小时版本';
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()


def _latest_snapshot() -> Optional[Dict[str, Any]]:
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


def _snapshot_by_id(snapshot_id: int) -> Optional[Dict[str, Any]]:
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


def _snapshot_by_version_time(version_time: str) -> Optional[Dict[str, Any]]:
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


def _list_snapshots(hours: int = 24) -> List[Dict[str, Any]]:
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


def _save_snapshot(snapshot: Dict[str, Any]) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategy_change_snapshot
                    (version_time, window_start, window_end, news_total,
                     news_added_count, news_removed_count,
                     stock_recommend, strategy_recommend, summary_stats, generate_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    window_start = VALUES(window_start),
                    window_end = VALUES(window_end),
                    news_total = VALUES(news_total),
                    news_added_count = VALUES(news_added_count),
                    news_removed_count = VALUES(news_removed_count),
                    stock_recommend = VALUES(stock_recommend),
                    strategy_recommend = VALUES(strategy_recommend),
                    summary_stats = VALUES(summary_stats),
                    generate_status = VALUES(generate_status),
                    create_time = CURRENT_TIMESTAMP
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
    return " ".join([f"WHEN '{m}' THEN {i}" for i, m in enumerate(ANALYSIS_MODEL_PRIORITY)])


def _get_latest_news_pub_time() -> Optional[datetime]:
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


def _compute_window_from_news() -> tuple[Optional[datetime], Optional[datetime], Optional[datetime]]:
    """
    基于 news.pub_time 计算 24h 滚动窗口，返回 (version_time, window_start, window_end)。

    时间取整规则（ceil 到整点）：
      - version_time: 最新 pub_time 所在的整点小时末（如 22:41 → 23:00, 22:00 → 22:00）
      - window_end: 同 version_time
      - window_start: window_end - 24h

    这样 latest=22:41 时 window=(昨日23:00, 今日23:00)，22:41 的文章包含在内。
    如果 news 表为空，返回 (None, None, None)。
    """
    latest = _get_latest_news_pub_time()
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


def _count_news_raw(window_start: datetime, window_end: datetime) -> int:
    """统计窗口内 news 表中全部新闻数（含未分析的）"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM news WHERE pub_time >= %s AND pub_time <= %s",
                (window_start.replace(tzinfo=None), window_end.replace(tzinfo=None)),
            )
            row = cur.fetchone()
    return row[0] if row else 0


def _query_news_ids_analyzed(window_start: datetime, window_end: datetime) -> set:
    """查询窗口内已完成分析（有 reason）的新闻ID集合，按模型优先级去重"""
    priority_cases = _build_model_priority_case()

    sql = f"""
        SELECT DISTINCT news_id
        FROM (
            SELECT n.id AS news_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY n.id
                       ORDER BY CASE a.model {priority_cases} ELSE 999 END
                   ) AS rn
            FROM news n
            JOIN analysis a ON a.news_id = n.id
            WHERE n.pub_time >= %s
              AND n.pub_time <= %s
              AND a.reason IS NOT NULL
              AND TRIM(a.reason) <> ''
        ) t
        WHERE t.rn = 1
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (window_start.replace(tzinfo=None), window_end.replace(tzinfo=None)))
            return {row[0] for row in cur.fetchall()}


def _extract_json(text: str) -> Dict[str, Any]:
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
            return json.loads(text[start:end + 1])
        raise


# ============================================================
# 新闻查询（复用 ai_strategy_recommendation 的查询模式）
# ============================================================

def _query_news_for_window(window_start: datetime, window_end: datetime) -> List[Dict[str, Any]]:
    """查询窗口内的新闻摘要（仅取 analysis.reason），按模型优先级去重"""
    priority_cases = _build_model_priority_case()

    sql = f"""
        SELECT t.news_id, t.title, t.pub_time, t.direction, t.reason, t.model
        FROM (
            SELECT n.id AS news_id, n.title, n.pub_time,
                   COALESCE(a.direction, '') AS direction,
                   COALESCE(a.reason, '') AS reason,
                   a.model,
                   ROW_NUMBER() OVER (
                       PARTITION BY n.id
                       ORDER BY CASE a.model {priority_cases} ELSE 999 END
                   ) AS rn
            FROM news n
            JOIN analysis a ON a.news_id = n.id
            WHERE n.pub_time >= %s
              AND n.pub_time <= %s
              AND a.reason IS NOT NULL
              AND TRIM(a.reason) <> ''
        ) t
        WHERE t.rn = 1
        ORDER BY t.pub_time ASC
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (window_start.replace(tzinfo=None), window_end.replace(tzinfo=None)))
            rows = cur.fetchall()

    return [
        {
            "news_id": row[0],
            "title": row[1],
            "pub_time": row[2],
            "direction": (row[3] or "").strip(),
            "reason": row[4],
            "model": row[5],
        }
        for row in rows
    ]


# ============================================================
# LLM 策略生成
# ============================================================

def _build_reason_text(news_rows: List[Dict[str, Any]]) -> str:
    lines = []
    for idx, item in enumerate(news_rows, 1):
        pub_time = item["pub_time"]
        ts = pub_time.strftime("%Y-%m-%d %H:%M") if isinstance(pub_time, datetime) else str(pub_time)
        lines.append(
            f"{idx}. 时间: {ts} | 方向: {item['direction']} | 标题: {item['title']} | 摘要: {item['reason']}"
        )
    return "\n".join(lines) if lines else "当前窗口内暂无有效新闻。"


def _generate_recommendations(
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
    response = client.chat.completions.create(
        model=provider_model,
        messages=[
            {"role": "system", "content": "你是严格输出 JSON 的中国债券市场策略分析师。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        timeout=600,
    )

    raw = response.choices[0].message.content or ""
    return _extract_json(raw)


# ============================================================
# 对比计算
# ============================================================

def _compute_diff(
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
        {"code": c, "name": old_stock_map[c].get("name", ""), "prev_rating": old_stock_map[c].get("rating", "")}
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
            stock_modified.append({
                "code": code,
                "name": new_item.get("name", ""),
                **changes,
            })

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
        {"id": i, "name": old_strat_map[i].get("name", ""), "prev_priority": old_strat_map[i].get("priority", 0)}
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
            strategy_modified.append({
                "id": sid,
                "name": new_item.get("name", ""),
                **changes,
            })

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
            "strategy_changes": len(strategy_added) + len(strategy_removed) + len(strategy_modified),
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


# ============================================================
# API 端点
# ============================================================

@router.post("/trigger")
async def trigger_snapshot(request: TriggerRequest = Body(default=TriggerRequest())):
    """
    触发一次快照生成。
    基于 news.pub_time（数据源时间，非服务器时间）确定24h滚动窗口，
    取 analysis.reason 作为LLM输入，生成标的+策略推荐，写入快照表。

    保护措施：
    - 若 news 表最新 pub_time 与当前服务器时间偏差 > 2h，标记待确认
    - 若窗口内未分析新闻占比 > 50%，标记待确认
    """
    _create_table_if_not_exists()

    # 基于 news.pub_time 计算窗口（而非服务器时间）
    version_time, window_start, window_end = _compute_window_from_news()

    if version_time is None or window_start is None or window_end is None:
        raise HTTPException(status_code=503, detail="news 表为空，无法确定窗口范围。请先执行新闻爬取与分析。")

    # 查询窗口内已分析的新闻（有 reason 的）
    news_rows = _query_news_for_window(window_start, window_end)

    # 统计窗口内新闻覆盖情况
    total_news_raw = _count_news_raw(window_start, window_end)
    analyzed_count = len(news_rows)
    unanalyzed_count = max(0, total_news_raw - analyzed_count)
    analysis_coverage = (analyzed_count / total_news_raw * 100) if total_news_raw > 0 else 0

    logger.info(
        "窗口 [%s ~ %s]：总新闻=%d, 已分析=%d, 未分析=%d, 覆盖率=%.1f%%",
        window_start.strftime("%Y-%m-%d %H:%M"),
        window_end.strftime("%Y-%m-%d %H:%M"),
        total_news_raw, analyzed_count, unanalyzed_count, analysis_coverage,
    )

    if not news_rows and not request.force:
        return {
            "success": True,
            "message": (
                f"窗口内无已分析新闻（总{total_news_raw}条，已分析0条）。"
                f"请检查 analysis 表是否已写入。使用 force=true 可强制生成。"
            ),
            "skipped": True,
            "window": {
                "start": window_start.strftime("%Y-%m-%d %H:%M:%S"),
                "end": window_end.strftime("%Y-%m-%d %H:%M:%S"),
                "total_news_raw": total_news_raw,
                "analyzed_count": 0,
            },
        }

    # 计算相比上一版本的新闻变动
    current_news_ids = {r["news_id"] for r in news_rows}
    prev = _latest_snapshot()
    news_added_count = 0
    news_removed_count = 0

    if prev:
        prev_window_start = datetime.strptime(prev["window_start"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CHANGE_TZ)
        prev_window_end = datetime.strptime(prev["window_end"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CHANGE_TZ)
        prev_news_ids = _query_news_ids_analyzed(prev_window_start, prev_window_end)
        news_added_count = len(current_news_ids - prev_news_ids)
        news_removed_count = len(prev_news_ids - current_news_ids)

    # 调用 LLM 生成推荐
    try:
        result = _generate_recommendations(news_rows, window_start, window_end)
    except Exception as exc:
        logger.exception("LLM 推荐生成失败")
        raise HTTPException(status_code=500, detail=f"LLM 推荐生成失败: {exc}")

    stock_recommend = result.get("stock_recommend", [])
    strategy_recommend = result.get("strategy_recommend", [])
    summary_stats = result.get("summary_stats", {})
    summary_stats["market_overview"] = result.get("market_overview", "")

    # 注入分析覆盖信息到 summary_stats（前端可展示）
    summary_stats["news_total_raw"] = total_news_raw
    summary_stats["analyzed_count"] = analyzed_count
    summary_stats["unanalyzed_count"] = unanalyzed_count
    summary_stats["analysis_coverage_pct"] = round(analysis_coverage, 1)

    # --- 校验与保护 ---
    generate_status = 1
    warnings: List[str] = []

    # 1) 时间偏差检测：news 最新时间 vs 服务器当前时间
    server_now = datetime.now(CHANGE_TZ)
    time_gap_hours = abs((server_now - version_time).total_seconds()) / 3600
    if time_gap_hours > 2:
        generate_status = 2
        warnings.append(f"数据源最新时间与服务器时间偏差 {time_gap_hours:.1f}h，可能爬虫或分析管道延迟")

    # 2) 分析覆盖率不足
    if total_news_raw > 0 and analysis_coverage < 50:
        generate_status = 2
        warnings.append(f"窗口内仅 {analysis_coverage:.0f}% 新闻已完成分析（{analyzed_count}/{total_news_raw}），推荐可能不完整")

    # 3) 新闻量波动超过 50%
    if prev and prev.get("news_total", 0) > 0 and analyzed_count > 0:
        news_change_ratio = abs(analyzed_count - prev["news_total"]) / prev["news_total"]
        if news_change_ratio > 0.5:
            generate_status = 2
            warnings.append(f"新闻量波动 {news_change_ratio:.0%}，超过 50% 阈值")

    # 4) LLM 未生成任何推荐
    if len(stock_recommend) == 0 and len(strategy_recommend) == 0:
        generate_status = 2
        warnings.append("LLM 未生成任何标的或策略推荐")

    if warnings:
        summary_stats["warnings"] = warnings

    snapshot = {
        "version_time": version_time.strftime("%Y-%m-%d %H:%M:%S"),
        "window_start": window_start.strftime("%Y-%m-%d %H:%M:%S"),
        "window_end": window_end.strftime("%Y-%m-%d %H:%M:%S"),
        "news_total": analyzed_count,
        "news_added_count": news_added_count,
        "news_removed_count": news_removed_count,
        "stock_recommend": stock_recommend,
        "strategy_recommend": strategy_recommend,
        "summary_stats": summary_stats,
        "generate_status": generate_status,
    }

    try:
        new_id = _save_snapshot(snapshot)
    except Exception as exc:
        logger.exception("快照写入失败")
        raise HTTPException(status_code=500, detail=f"快照写入失败: {exc}")

    snapshot["id"] = new_id
    return {
        "success": True,
        "snapshot": snapshot,
        "message": (
            "快照生成成功"
            if generate_status == 1
            else f"快照已生成（待确认），警告: {'; '.join(warnings)}"
        ),
    }


@router.get("/snapshots")
def list_snapshots(hours: int = Query(24, ge=1, le=168)):
    """返回指定小时数内的快照列表，用于时间轴渲染"""
    _create_table_if_not_exists()
    try:
        items = _list_snapshots(hours)
        return {"success": True, "items": items, "count": len(items)}
    except Exception as exc:
        logger.exception("快照列表查询失败")
        raise HTTPException(status_code=500, detail=f"快照列表查询失败: {exc}")


@router.post("/compare")
def compare_snapshots(request: CompareRequest = Body(default=CompareRequest())):
    """对比两个版本的快照，返回标的&策略变动详情"""
    _create_table_if_not_exists()

    # 确定新旧快照
    old_snapshot = None
    new_snapshot = None

    if request.new_snapshot_id:
        new_snapshot = _snapshot_by_id(request.new_snapshot_id)
    elif request.new_version_time:
        new_snapshot = _snapshot_by_version_time(request.new_version_time)

    if request.old_snapshot_id:
        old_snapshot = _snapshot_by_id(request.old_snapshot_id)
    elif request.old_version_time:
        old_snapshot = _snapshot_by_version_time(request.old_version_time)

    # 默认：取最新两个版本
    if not new_snapshot:
        all_items = _list_snapshots(48)
        if len(all_items) >= 1:
            new_snapshot = _snapshot_by_id(all_items[0]["id"])
        if not old_snapshot and len(all_items) >= 2:
            old_snapshot = _snapshot_by_id(all_items[1]["id"])

    if not new_snapshot:
        raise HTTPException(status_code=404, detail="未找到快照数据，请先调用 /api/change/trigger 生成")

    if not old_snapshot:
        raise HTTPException(
            status_code=400,
            detail="仅有一个版本的快照，无法对比。请至少生成两个版本后重试。",
        )

    try:
        diff = _compute_diff(old_snapshot, new_snapshot)
        diff["old_snapshot_id"] = old_snapshot["id"]
        diff["new_snapshot_id"] = new_snapshot["id"]
        diff["old_summary"] = old_snapshot.get("summary_stats", {})
        diff["new_summary"] = new_snapshot.get("summary_stats", {})
        return {"success": True, **diff}
    except Exception as exc:
        logger.exception("快照对比失败")
        raise HTTPException(status_code=500, detail=f"快照对比失败: {exc}")
