"""
宏观信号查询模块

支持两种信号类型：
- presence：某因子在指定时间范围内是否存在对应新闻（0/1）
- directional：某因子在指定时间范围内的方向性信号（-1/0/1），带时间衰减加权
"""
import math
from datetime import datetime
from typing import List
from backend.common.database import get_db_connection

# 常量定义
DIRECTIONAL_THRESHOLD = 0.3
SIGNAL_PRESENCE = "presence"
SIGNAL_DIRECTIONAL = "directional"

# 方向映射字典
DIRECTION_SCORE_MAP = {
    "positive": 1.0,
    "neutral": 0.0,
    "negative": -1.0,
}


def _format_time_range(start: datetime, end: datetime) -> dict:
    """公共时间格式化（消除冗余）"""
    return {"start": start.isoformat(), "end": end.isoformat()}


def _get_hit_news_ids(matched_rows: list) -> list:
    """公共获取新闻ID列表（消除冗余）"""
    return [row[1] for row in matched_rows]


def _direction_to_score(direction: str) -> float:
    return DIRECTION_SCORE_MAP.get((direction or "").lower(), 0.0)


def _score_to_signal(score: float) -> int:
    if score >= DIRECTIONAL_THRESHOLD:
        return 1
    return -1 if score <= -DIRECTIONAL_THRESHOLD else 0


def _query_news_factor_rows(
    cur, factor_codes: List[str], start_time: datetime, end_time: datetime
):
    placeholders = ",".join(["%s"] * len(factor_codes))
    cur.execute(
        f"""
        SELECT f.code, nf.news_id, nf.direction, nf.pub_time
        FROM news_factor nf
        JOIN factor f ON nf.factor_id = f.id
        WHERE f.code IN ({placeholders})
          AND nf.pub_time BETWEEN %s AND %s
        ORDER BY nf.pub_time ASC
        """,
        (*factor_codes, start_time, end_time),
    )
    return cur.fetchall()


def _check_factor_codes_exist(cur, factor_codes: List[str]) -> set:
    placeholders = ",".join(["%s"] * len(factor_codes))
    cur.execute(
        f"SELECT code FROM factor WHERE code IN ({placeholders})",
        tuple(factor_codes),
    )
    return {row[0] for row in cur.fetchall()}


def _compute_presence(rows, factor_code: str, start_time: datetime, end_time: datetime) -> dict:
    """计算单个因子的 presence 信号"""
    matched = [r for r in rows if r[0] == factor_code]
    news_count = len(matched)

    return {
        "factor_code": factor_code,
        "signal_type": SIGNAL_PRESENCE,
        "signal_value": 1 if news_count > 0 else 0,
        "confidence": None,
        "news_count": news_count,
        "hit_news_ids": _get_hit_news_ids(matched),
        "time_range": _format_time_range(start_time, end_time),
    }


def _compute_directional(
    rows, factor_code: str, start_time: datetime, end_time: datetime, decay_lambda: float
) -> dict:
    """计算单个因子的 directional 信号（时间衰减加权）"""
    matched = [r for r in rows if r[0] == factor_code]
    news_count = len(matched)

    if news_count == 0:
        return {
            "factor_code": factor_code,
            "signal_type": SIGNAL_DIRECTIONAL,
            "signal_value": 0,
            "confidence": 0.0,
            "news_count": 0,
            "hit_news_ids": [],
            "time_range": _format_time_range(start_time, end_time),
        }

    weighted_sum = weight_total = 0.0
    end_dt = end_time

    for _, _, direction, pub_time in matched:
        delta_days = max((end_dt - pub_time).total_seconds() / 86400.0, 0.0)
        w = math.exp(-decay_lambda * delta_days)
        weighted_sum += _direction_to_score(direction) * w
        weight_total += w

    raw_score = weighted_sum / weight_total if weight_total > 0 else 0.0
    confidence = min(weight_total / news_count, 1.0)

    return {
        "factor_code": factor_code,
        "signal_type": SIGNAL_DIRECTIONAL,
        "signal_value": _score_to_signal(raw_score),
        "confidence": round(confidence, 4),
        "news_count": news_count,
        "hit_news_ids": _get_hit_news_ids(matched),
        "time_range": _format_time_range(start_time, end_time),
    }


def get_macro_signal(
    factor_codes: List[str],
    start_time: datetime,
    end_time: datetime,
    signal_type: str,
    decay_lambda: float = 0.1,
) -> List[dict]:
    """
    查询宏观信号，返回每个 factor_code 的信号结果列表。

    :param factor_codes: 因子代码列表
    :param start_time: 时间范围起点
    :param end_time: 时间范围终点
    :param signal_type: "presence" 或 "directional"
    :param decay_lambda: 时间衰减系数（仅 directional 生效）
    :return: List[dict]，顺序与 factor_codes 一致
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        existing_codes = _check_factor_codes_exist(cur, factor_codes)
        valid_codes = [c for c in factor_codes if c in existing_codes]
        rows = _query_news_factor_rows(cur, valid_codes, start_time, end_time) if valid_codes else []

    results = []
    for code in factor_codes:
        if code not in existing_codes:
            results.append({"factor_code": code, "error": "not found"})
            continue

        if signal_type == SIGNAL_PRESENCE:
            results.append(_compute_presence(rows, code, start_time, end_time))
        else:
            results.append(_compute_directional(rows, code, start_time, end_time, decay_lambda))

    return results