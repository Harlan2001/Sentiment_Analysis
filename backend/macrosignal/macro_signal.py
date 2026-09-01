"""
宏观信号查询模块

支持两种信号类型：
- presence：某因子在指定时间范围内是否存在对应新闻（0/1）
- directional：某因子在指定时间范围内的方向性信号（-1/0/1），带时间衰减加权
"""

import math
from datetime import datetime
from typing import NamedTuple

from backend.common.database import build_in_placeholders, get_db_connection

# 常量定义
DIRECTIONAL_THRESHOLD = 0.3
DEFAULT_DECAY_LAMBDA = 0.1
SIGNAL_PRESENCE = "presence"
SIGNAL_DIRECTIONAL = "directional"

# 方向标签 → 分数映射
DIRECTION_SCORE_MAP = {
    "positive": 1.0,
    "neutral": 0.0,
    "negative": -1.0,
}


class NewsFactorRow(NamedTuple):
    """news_factor 关联查询结果的一行。"""

    factor_code: str
    news_id: int
    direction: str
    pub_time: datetime


def _direction_to_score(direction: str) -> float:
    """方向标签转分数：positive=1 / neutral=0 / negative=-1，未知或空按 0。"""
    return DIRECTION_SCORE_MAP.get((direction or "").lower(), 0.0)


def _score_to_signal(score: float) -> int:
    """按阈值把连续分数映射为 -1/0/1 信号。"""
    if score >= DIRECTIONAL_THRESHOLD:
        return 1
    if score <= -DIRECTIONAL_THRESHOLD:
        return -1
    return 0


def _check_factor_codes_exist(cur, factor_codes: list[str]) -> set[str]:
    """返回 factor 表中真实存在的因子代码集合。"""
    if not factor_codes:
        return set()
    placeholders = build_in_placeholders(factor_codes)
    cur.execute(
        f"SELECT code FROM factor WHERE code IN ({placeholders})",
        tuple(factor_codes),
    )
    return {row[0] for row in cur.fetchall()}


def _query_news_factor_rows(
    cur, factor_codes: list[str], start_time: datetime, end_time: datetime
) -> list[NewsFactorRow]:
    """查询因子在时间范围内的新闻关联记录；factor_codes 为空时返回空列表。"""
    if not factor_codes:
        return []
    placeholders = build_in_placeholders(factor_codes)
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
    return [NewsFactorRow(*row) for row in cur.fetchall()]


def _build_signal_result(
    factor_code: str,
    signal_type: str,
    signal_value: int,
    confidence,
    news_rows: list[NewsFactorRow],
    start_time: datetime,
    end_time: datetime,
) -> dict:
    """组装单个因子的信号结果字典（presence 与 directional 共用结构）。"""
    return {
        "factor_code": factor_code,
        "signal_type": signal_type,
        "signal_value": signal_value,
        "confidence": confidence,
        "news_count": len(news_rows),
        "hit_news_ids": [row.news_id for row in news_rows],
        "time_range": {"start": start_time.isoformat(), "end": end_time.isoformat()},
    }


def _compute_presence(
    news_rows: list[NewsFactorRow],
    factor_code: str,
    start_time: datetime,
    end_time: datetime,
) -> dict:
    """计算单个因子的 presence 信号（0/1）。"""
    return _build_signal_result(
        factor_code,
        SIGNAL_PRESENCE,
        1 if news_rows else 0,
        None,
        news_rows,
        start_time,
        end_time,
    )


def _compute_directional(
    news_rows: list[NewsFactorRow],
    factor_code: str,
    start_time: datetime,
    end_time: datetime,
    decay_lambda: float,
) -> dict:
    """计算单个因子的 directional 信号（时间衰减加权，-1/0/1）。"""
    if not news_rows:
        return _build_signal_result(
            factor_code, SIGNAL_DIRECTIONAL, 0, 0.0, [], start_time, end_time
        )

    weighted_sum = weight_total = 0.0
    for row in news_rows:
        delta_days = max((end_time - row.pub_time).total_seconds() / 86400.0, 0.0)
        weight = math.exp(-decay_lambda * delta_days)
        weighted_sum += _direction_to_score(row.direction) * weight
        weight_total += weight

    # weight_total 恒 > 0（每条新闻的权重 exp() 均为正），无需判 0
    raw_score = weighted_sum / weight_total
    confidence = min(weight_total / len(news_rows), 1.0)

    return _build_signal_result(
        factor_code,
        SIGNAL_DIRECTIONAL,
        _score_to_signal(raw_score),
        round(confidence, 4),
        news_rows,
        start_time,
        end_time,
    )


def get_macro_signal(
    factor_codes: list[str],
    start_time: datetime,
    end_time: datetime,
    signal_type: str,
    decay_lambda: float = DEFAULT_DECAY_LAMBDA,
) -> list[dict]:
    """
    查询宏观信号，返回每个 factor_code 的信号结果列表。

    :param factor_codes: 因子代码列表
    :param start_time: 时间范围起点
    :param end_time: 时间范围终点
    :param signal_type: "presence" 或 "directional"，其他值抛 ValueError
    :param decay_lambda: 时间衰减系数（仅 directional 生效）
    :return: List[dict]，顺序与 factor_codes 一致；不存在的因子返回
             {"factor_code": ..., "error": "not found"}
    """
    if signal_type not in (SIGNAL_PRESENCE, SIGNAL_DIRECTIONAL):
        raise ValueError(f"未知 signal_type: {signal_type!r}")
    if not factor_codes:
        return []

    with get_db_connection() as conn:
        cur = conn.cursor()
        existing_codes = _check_factor_codes_exist(cur, factor_codes)
        valid_codes = [c for c in factor_codes if c in existing_codes]
        # rows 按 pub_time 排序，需按 code 归组一次，避免每个因子重复全表扫描
        rows_by_code: dict[str, list[NewsFactorRow]] = {}
        for row in _query_news_factor_rows(cur, valid_codes, start_time, end_time):
            rows_by_code.setdefault(row.factor_code, []).append(row)

    results = []
    for code in factor_codes:
        if code not in existing_codes:
            results.append({"factor_code": code, "error": "not found"})
            continue

        news_rows = rows_by_code.get(code, [])
        if signal_type == SIGNAL_PRESENCE:
            results.append(_compute_presence(news_rows, code, start_time, end_time))
        else:
            results.append(
                _compute_directional(news_rows, code, start_time, end_time, decay_lambda)
            )

    return results