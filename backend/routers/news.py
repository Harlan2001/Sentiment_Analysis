from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pymysql
from fastapi import APIRouter, HTTPException, Query

from backend.common.api_response import ok
from backend.common.database import build_in_placeholders, execute_query, get_db_connection
from backend.common.db_analysis import AnalysisQueries
from backend.common.db_operations import DBOperations
from backend.common.vector_store import get_faiss_store
from backend.common.yield_db import get_yield_window_by_news_id
from backend.config.config import (
    ANALYSIS_MODEL_PRIORITY,
    API_PREFIX,
    NEWS_SOURCES,
    get_default_analysis_model_name,
    mask_news_source,
)

router = APIRouter(prefix=API_PREFIX, tags=["news"])

logger = logging.getLogger(__name__)


def _priority_cases() -> str:
    """模型优先级 SQL CASE 片段（来源唯一：db_analysis.AnalysisQueries）。"""
    return AnalysisQueries.priority_case_sql()


def _serialize_news_item(
    r: Dict[str, Any],
    *,
    include_content: bool = False,
    selected: Optional[Dict[str, Any]] = None,
    analyses: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """把 news 行（DictCursor）序列化为前端新闻项。

    single/best 视图在 SQL 中已联结 analysis（row 自带 direction/horizon/reason/model），
    传入 ``selected=None`` 直接取行内列；all 视图在 Python 侧选最佳分析，传入
    ``selected``（含 direction/horizon/reason/model）与 ``analyses``（全量模型列表）。
    """
    sel = selected if selected is not None else r
    return {
        "id": r["id"],
        "title": r["title"],
        "publish_time": r["pub_time"],
        "source": mask_news_source(r["source"]),
        "source_key": r["source"],
        "source_url": r["url"],
        "global_uid": r["global_uid"],
        "author": r["author"],
        "source_news_id": r["source_news_id"],
        "direction": sel.get("direction"),
        "horizon": sel.get("horizon"),
        "reason": sel.get("reason"),
        "model": sel.get("model"),
        "selected_model": sel.get("model"),
        "analyses": analyses if analyses is not None else [],
        **({"content": r["content"]} if include_content else {}),
    }


def _keyword_like_filter(keywords: List[str]) -> tuple[str, List[str]]:
    """构造标题/正文关键词过滤片段（逗号分词，命中任意一个即返回）。

    返回 (SQL片段, 参数)。SQL 片段以 AND 开头，依赖表别名 n。
    """
    if not keywords:
        return "", []

    conds = " OR ".join(
        "(n.title LIKE %s OR n.content LIKE %s)" for _ in keywords
    )
    params = [f"%{kw}%" for kw in keywords for _ in (0, 1)]
    return f"AND ({conds})", params


def _attach_best_analysis(
    news_rows: List[tuple], model: Optional[str] = None
) -> Dict[int, Dict[str, Any]]:
    """为 (id, title, pub_time, source_key) 行附加优先级最高的 analysis。

    返回 {news_id: {id, title, publish_time, source, direction, horizon, reason,
                    model, selected_model}}，不保证输入顺序。
    """
    if not news_rows:
        return {}

    news_ids = [r[0] for r in news_rows]
    placeholders = build_in_placeholders(news_ids)
    analysis_sql = (
        "SELECT news_id, direction, horizon, reason, model FROM analysis "
        f"WHERE news_id IN ({placeholders})"
    )
    analysis_params: List[Any] = list(news_ids)
    if model:
        analysis_sql += " AND model = %s"
        analysis_params.append(model)

    analysis_rows = execute_query(
        analysis_sql, tuple(analysis_params), one=False
    )

    analyses_by_news: Dict[int, List[Dict[str, Any]]] = {}
    for news_id, direction, horizon, reason, model_name in analysis_rows:
        analyses_by_news.setdefault(news_id, []).append(
            {
                "direction": direction or "中性",
                "horizon": horizon or "短期",
                "reason": reason or "待分析",
                "model": model_name,
            }
        )

    priority_rank = {m: i for i, m in enumerate(ANALYSIS_MODEL_PRIORITY)}
    out: Dict[int, Dict[str, Any]] = {}
    for row in news_rows:
        nid, title, pub_time, source_key = row
        current_analyses = analyses_by_news.get(nid, [])
        if current_analyses:
            selected = sorted(
                current_analyses, key=lambda x: priority_rank.get(x["model"], 999)
            )[0]
        else:
            selected = {
                "direction": "中性",
                "horizon": "短期",
                "reason": "待分析",
                "model": model or "default",
            }
        out[nid] = {
            "id": nid,
            "title": title,
            "publish_time": pub_time,
            "source": mask_news_source(source_key),
            "direction": selected["direction"],
            "horizon": selected["horizon"],
            "reason": selected["reason"],
            "model": selected["model"],
            "selected_model": selected["model"],
        }
    return out


@router.get("/yields")
def get_yields(start: str, end: str, type: str = Query("10年")):
    try:
        return ok(DBOperations.get_yield_series_by_period(start, end, type))
    except Exception as exc:
        logger.exception("yield 序列查询失败")
        raise HTTPException(
            status_code=500,
            detail=(
                "数据库表不存在或数据未初始化: "
                f"{exc}. 请运行 python init_yield_db.py 初始化数据库"
            ),
        ) from exc


@router.get("/news")
def get_news(
    date: Optional[str] = Query(None, description="单个日期查询，格式 YYYY-MM-DD"),
    start_date: Optional[str] = Query(
        None, description="时间段开始日期，格式 YYYY-MM-DD"
    ),
    end_date: Optional[str] = Query(
        None, description="时间段结束日期，格式 YYYY-MM-DD"
    ),
    source: Optional[str] = Query(
        None, description="新闻源过滤，多个用逗号分隔，如 wallstreetcn,yicai"
    ),
    keyword: Optional[str] = Query(
        None, description="关键词检索，多个用逗号分隔，命中标题或正文任意一个即可"
    ),
    model: Optional[str] = Query(
        None, description="模型短名，用于 single/all 视图过滤"
    ),
    view: str = Query("best", description="best | single | all"),
    include_content: bool = Query(
        False, description="是否在列表返回新闻正文（content），供外部批量消费"
    ),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=5000,
        description="可选：返回条数上限，缺省返回全部匹配项；配合 offset 分页",
    ),
    offset: int = Query(0, ge=0, description="可选：配合 limit 使用的跳过条数"),
):
    params: List[Any] = []
    date_filter = ""

    if date:
        date_filter = "DATE(n.pub_time) = %s"
        params = [date]
    elif start_date and end_date:
        date_filter = "DATE(n.pub_time) BETWEEN %s AND %s"
        params = [start_date, end_date]
    else:
        default_end = datetime.now().strftime("%Y-%m-%d")
        default_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        date_filter = "DATE(n.pub_time) BETWEEN %s AND %s"
        params = [default_start, default_end]

    source_filter = ""
    if source:
        sources = [s.strip() for s in source.split(",") if s.strip()]
        if sources:
            placeholders = build_in_placeholders(sources)
            source_filter = f"AND n.source IN ({placeholders})"
            params.extend(sources)

    keyword_filter = ""
    if keyword:
        kw_list = [k.strip() for k in keyword.split(",") if k.strip()]
        if kw_list:
            keyword_filter, kw_params = _keyword_like_filter(kw_list)
            params.extend(kw_params)

    # 对外开放：可选返回正文 + 可选分页（只在显式给 limit 时生效，保持原默认行为）
    content_col = ", n.content" if include_content else ""
    pagination_clause = ""
    if limit is not None:
        pagination_clause = " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

    effective_view = view if view in ("best", "single", "all") else "best"
    if effective_view == "single" and not model:
        model = get_default_analysis_model_name()

    with get_db_connection() as conn:
        cur = conn.cursor(pymysql.cursors.DictCursor)

        if effective_view == "single":
            cur.execute(
                f"""
                SELECT n.id, n.title, n.pub_time, n.source, n.url, n.global_uid,
                       n.author, n.source_news_id{content_col},
                       COALESCE(a.direction, '中性') as direction,
                       COALESCE(a.horizon, '短期') as horizon,
                       COALESCE(a.reason, '待分析') as reason,
                       COALESCE(a.model, %s) as model
                FROM news n
                LEFT JOIN analysis a ON a.news_id = n.id AND a.model = %s
                WHERE {date_filter} {source_filter} {keyword_filter}
                ORDER BY n.pub_time DESC
                {pagination_clause}
                """,
                [model, model] + params,
            )
            rows = cur.fetchall()
            return ok(
                [_serialize_news_item(r, include_content=include_content) for r in rows]
            )

        if effective_view == "best":
            cur.execute(
                f"""
                SELECT n.id, n.title, n.pub_time, n.source, n.url, n.global_uid,
                       n.author, n.source_news_id{content_col},
                       COALESCE(a.direction, '中性') as direction,
                       COALESCE(a.horizon, '短期') as horizon,
                       COALESCE(a.reason, '待分析') as reason,
                       COALESCE(a.model, 'default') as model
                FROM news n
                {AnalysisQueries.best_analysis_join()}
                WHERE {date_filter} {source_filter} {keyword_filter}
                ORDER BY n.pub_time DESC
                {pagination_clause}
                """,
                params,
            )
            rows = cur.fetchall()
            return ok(
                [_serialize_news_item(r, include_content=include_content) for r in rows]
            )

        cur.execute(
            f"""
            SELECT n.id, n.title, n.pub_time, n.source, n.url, n.global_uid,
                   n.author, n.source_news_id{content_col}
            FROM news n
            WHERE {date_filter} {source_filter} {keyword_filter}
            ORDER BY n.pub_time DESC
            {pagination_clause}
            """,
            params,
        )
        news_rows = cur.fetchall()
        if not news_rows:
            return ok([])

        news_ids = [r["id"] for r in news_rows]
        placeholders = build_in_placeholders(news_ids)
        analysis_sql = f"""
            SELECT news_id, direction, horizon, reason, model
            FROM analysis
            WHERE news_id IN ({placeholders})
        """
        analysis_params: List[Any] = list(news_ids)
        if model:
            analysis_sql += " AND model = %s"
            analysis_params.append(model)

        cur.execute(analysis_sql, analysis_params)
        analysis_rows = cur.fetchall()

    analyses_by_news: Dict[int, List[Dict[str, Any]]] = {}
    for a in analysis_rows:
        analyses_by_news.setdefault(a["news_id"], []).append(
            {
                "direction": a["direction"] or "中性",
                "horizon": a["horizon"] or "短期",
                "reason": a["reason"] or "待分析",
                "model": a["model"],
            }
        )

    priority_rank = {m: i for i, m in enumerate(ANALYSIS_MODEL_PRIORITY)}
    result: List[Dict[str, Any]] = []

    for row in news_rows:
        current_analyses = analyses_by_news.get(row["id"], [])
        if current_analyses:
            selected = sorted(
                current_analyses, key=lambda x: priority_rank.get(x["model"], 999)
            )[0]
        else:
            selected = {
                "direction": "中性",
                "horizon": "短期",
                "reason": "待分析",
                "model": model or "default",
            }

        result.append(
            _serialize_news_item(
                row,
                include_content=include_content,
                selected=selected,
                analyses=current_analyses,
            )
        )

    return ok(result)


@router.get("/news/sources")
def get_news_sources():
    return ok({
        "sources": [
            {"key": key, "name": mask_news_source(key), "enabled": True}
            for key in NEWS_SOURCES
        ]
    })


@router.get("/news/latest-trading-day")
def get_latest_publish_day():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT MAX(DATE(pub_time))
                FROM news
                WHERE pub_time IS NOT NULL
                """)
            result = cursor.fetchone()
            latest_date = (
                result[0]
                if result and result[0]
                else datetime.now().strftime("%Y-%m-%d")
            )
    return ok({"latest_date": latest_date})


@router.get("/news/similar")
def similar_news(news_id: int, top_k: int = 5):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT content FROM news WHERE id=%s", (news_id,))
        row = cur.fetchone()
        if not row:
            return ok([])
        content = row[0]
        store = get_faiss_store()
        query_emb = store.model.encode(
            [content], normalize_embeddings=True, convert_to_numpy=True
        ).astype("float32")
        results = store.search_by_vector(query_emb, top_k + 1)

        out = []
        for item in results:
            nid = item["news_id"]
            score = item["score"]
            if nid == news_id:
                continue
            cur.execute("SELECT title FROM news WHERE id=%s", (nid,))
            row = cur.fetchone()
            if row:
                out.append({"news_id": nid, "score": round(score, 3), "title": row[0]})
            if len(out) >= top_k:
                break
    return ok(out)


@router.get("/news/search")
def search_news(
    q: str = Query(..., description="检索关键词，逗号分隔多个（命中任意一个即满足）"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    top_k: int = Query(30, ge=1, le=200),
    model: Optional[str] = Query(None, description="模型短名，用于 best 分析回填"),
):
    """新闻检索：先精确关键词匹配（标题/正文 LIKE），再 FAISS 语义联想兜底。

    返回按相关度排序的新闻列表，每条附带命中关键词与语义相似度。
    """
    keywords = [k.strip() for k in q.split(",") if k.strip()]
    if not keywords:
        return ok({"query": {"q": q, "keywords": keywords}, "total": 0, "items": []})

    # 日期过滤（可选）
    date_filter = ""
    date_params: List[Any] = []
    if start_date and end_date:
        date_filter = "AND DATE(n.pub_time) BETWEEN %s AND %s"
        date_params = [start_date, end_date]
    elif start_date:
        date_filter = "AND DATE(n.pub_time) >= %s"
        date_params = [start_date]
    elif end_date:
        date_filter = "AND DATE(n.pub_time) <= %s"
        date_params = [end_date]

    # 1. 精确关键词匹配（命中关键词数越多越靠前；SELECT 段占位符在 WHERE 段之前）
    like_conds = " OR ".join(
        "(n.title LIKE %s OR n.content LIKE %s)" for _ in keywords
    )
    match_cases = " + ".join(
        "(CASE WHEN n.title LIKE %s OR n.content LIKE %s THEN 1 ELSE 0 END)"
        for _ in keywords
    )
    case_params = [f"%{k}%" for k in keywords for _ in (0, 1)]
    like_params = [f"%{k}%" for k in keywords for _ in (0, 1)]
    exact_rows: List[tuple] = []
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT n.id, n.title, n.pub_time, n.source, n.url, n.global_uid,
                   n.author, n.source_news_id, {match_cases} AS matched_count
            FROM news n
            WHERE ({like_conds}) {date_filter}
            ORDER BY matched_count DESC, n.pub_time DESC
            LIMIT %s
            """,
            case_params + like_params + date_params + [top_k],
        )
        exact_rows = cur.fetchall()

    # 2. 语义召回（FAISS 向量：无字面命中也能召回相关新闻）
    semantic_map: Dict[int, float] = {}
    semantic_rows: List[tuple] = []
    try:
        store = get_faiss_store()
        results = store.search(" ".join(keywords), top_k=max(top_k * 3, 50))
        semantic_map = {item["news_id"]: item["score"] for item in results}
        exact_ids = {r[0] for r in exact_rows}
        sem_ids = [nid for nid in semantic_map if nid not in exact_ids]
        if sem_ids:
            placeholders = build_in_placeholders(sem_ids)
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"""
                    SELECT n.id, n.title, n.pub_time, n.source, n.url, n.global_uid,
                           n.author, n.source_news_id, 0 AS matched_count
                    FROM news n
                    WHERE n.id IN ({placeholders}) {date_filter}
                    """,
                    sem_ids + date_params,
                )
                semantic_rows = cur.fetchall()
    except Exception:
        logger.exception("news/search 语义检索失败，降级为关键词精确匹配")

    all_rows = exact_rows + semantic_rows
    if not all_rows:
        return ok({
            "query": {"q": q, "keywords": keywords},
            "total": 0,
            "items": [],
        })

    # 3. 读取正文用于计算每个关键词的命中情况（前端可据此高亮）
    content_map: Dict[int, str] = {}
    all_ids = list({r[0] for r in all_rows})
    content_rows = execute_query(
        f"SELECT id, content FROM news WHERE id IN ({','.join(['%s'] * len(all_ids))})",
        tuple(all_ids),
        one=False,
    )
    for cid, content in content_rows:
        content_map[cid] = content or ""

    merged: List[Dict[str, Any]] = []
    for r in all_rows:
        nid, title, pub_time, source_key, url, gid, author, src_nid, _sql_count = r
        text = f"{title or ''} {content_map.get(nid, '')}"
        matched_keywords = [k for k in keywords if k in text]
        merged.append(
            {
                "id": nid,
                "title": title,
                "publish_time": pub_time,
                "_source_key": source_key,
                "source_key": source_key,
                "source_url": url,
                "global_uid": gid,
                "author": author,
                "source_news_id": src_nid,
                "matched_count": len(matched_keywords),
                "matched_keywords": matched_keywords,
                "semantic_score": semantic_map.get(nid),
            }
        )

    merged.sort(
        key=lambda x: (
            x["matched_count"],
            x["semantic_score"] if x["semantic_score"] is not None else 0,
            x["publish_time"].timestamp() if x["publish_time"] else 0,
        ),
        reverse=True,
    )
    merged = merged[:top_k]

    # 4. 回填 best 分析方向/原因
    best_map = _attach_best_analysis(
        [
            (x["id"], x["title"], x["publish_time"], x["_source_key"])
            for x in merged
        ],
        model=model,
    )
    items = []
    for x in merged:
        item = best_map.get(x["id"]) or {}
        item = dict(item)
        item.update(
            {
                "matched_keywords": x["matched_keywords"],
                "matched_count": x["matched_count"],
                "semantic_score": x["semantic_score"],
            }
        )
        for extra in ("source_key", "source_url", "global_uid", "author", "source_news_id"):
            item[extra] = x.get(extra)
        items.append(item)

    return ok({
        "query": {"q": q, "keywords": keywords},
        "total": len(items),
        "items": items,
    })


@router.get("/news/{news_id}")
def get_news_detail(
    news_id: int,
    model: Optional[str] = Query(None, description="模型短名，不传则按优先级取 best"),
    include_all_models: bool = Query(False, description="是否返回多模型结果"),
):
    news_row = execute_query(
        """
        SELECT id, title, pub_time, content, source, url, global_uid, author, source_news_id
        FROM news
        WHERE id = %s
        """,
        (news_id,),
        one=True,
    )
    if not news_row:
        raise HTTPException(status_code=404, detail="新闻不存在")

    all_analysis_rows = execute_query(
        """
        SELECT direction, horizon, reason, model
        FROM analysis
        WHERE news_id = %s
        """,
        (news_id,),
        one=False,
    )

    analyses_by_model: Dict[str, Dict[str, Any]] = {}
    for a_row in all_analysis_rows:
        analyses_by_model[a_row[3]] = {
            "direction": a_row[0] or "中性",
            "horizon": a_row[1] or "短期",
            "reason": a_row[2] or "待分析",
            "model": a_row[3],
        }

    selected_model = model
    if not selected_model:
        for model_name in ANALYSIS_MODEL_PRIORITY:
            if model_name in analyses_by_model:
                selected_model = model_name
                break
    if not selected_model:
        # 历史数据可能只有 doubao 分析（已不在优先级列表），回退到任一可用模型
        if analyses_by_model:
            selected_model = next(iter(analyses_by_model))
        else:
            selected_model = "default"

    selected_analysis = analyses_by_model.get(
        selected_model,
        {
            "direction": "中性",
            "horizon": "短期",
            "reason": "待分析",
            "model": selected_model,
        },
    )

    def _query_factors_for_model(model_name: str) -> List[Dict[str, Any]]:
        factor_rows = execute_query(
            """
            SELECT f.code, f.name, f.category, nf.direction, nf.driver
            FROM news_factor nf
            JOIN factor f ON nf.factor_id = f.id
            WHERE nf.news_id = %s AND nf.model = %s
            ORDER BY f.code ASC
            """,
            (news_id, model_name),
            one=False,
        )
        return [
            {
                "code": r[0],
                "name": r[1] or r[0],
                "category": r[2],
                "direction": r[3],
                "driver": r[4],
            }
            for r in factor_rows
        ]

    selected_factors = _query_factors_for_model(selected_model)
    analyses_payload: List[Dict[str, Any]] = []
    if include_all_models:
        for model_name, analysis_data in analyses_by_model.items():
            analyses_payload.append(
                {**analysis_data, "factors": _query_factors_for_model(model_name)}
            )

    content_block_rows = execute_query(
        """
        SELECT id, news_id, block_type, block_order, content,
               heading_level, image_url, image_alt, image_width,
               table_caption, table_unit, table_headers, table_rows, created_at
        FROM news_content_blocks
        WHERE news_id = %s
        ORDER BY block_order ASC
        """,
        (news_id,),
        one=False,
    )

    content_blocks = []
    for block_row in content_block_rows:
        block = {
            "id": block_row[0],
            "news_id": block_row[1],
            "block_type": block_row[2],
            "block_order": block_row[3],
            "content": block_row[4],
            "heading_level": block_row[5],
            "image_url": block_row[6],
            "image_alt": block_row[7],
            "image_width": block_row[8],
            "table_caption": block_row[9],
            "table_unit": block_row[10],
            "table_headers": None,
            "table_rows": None,
            "created_at": block_row[13],
        }
        if block_row[11]:
            try:
                block["table_headers"] = json.loads(block_row[11])
            except (json.JSONDecodeError, ValueError):
                pass
        if block_row[12]:
            try:
                block["table_rows"] = json.loads(block_row[12])
            except (json.JSONDecodeError, ValueError):
                pass
        content_blocks.append(block)

    source_key = news_row[4] if news_row[4] else ""
    source_display = mask_news_source(source_key)
    return ok({
        "id": news_row[0],
        "title": news_row[1],
        "publish_time": news_row[2],
        "content": news_row[3],
        "content_blocks": content_blocks,
        "source": source_display,
        "source_key": source_key,
        "source_url": news_row[5],
        "global_uid": news_row[6],
        "author": news_row[7],
        "source_news_id": news_row[8],
        "direction": selected_analysis["direction"],
        "horizon": selected_analysis["horizon"],
        "reason": selected_analysis["reason"],
        "model": selected_analysis["model"],
        "selected_model": selected_model,
        "factors": selected_factors,
        "analyses": analyses_payload,
    })


@router.get("/factor/{factor_code}/news")
def get_news_by_factor(
    factor_code: str,
    model: Optional[str] = Query(None, description="模型短名，不传则按优先级返回 best"),
):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, category, factor_type FROM factor WHERE code = %s",
            (factor_code,),
        )
        factor_row = cur.fetchone()
        if not factor_row:
            raise HTTPException(status_code=404, detail="因子不存在")

        factor_id = factor_row[0]
        factor_name = factor_row[1] or factor_code
        factor_category = factor_row[2]
        priority_cases = _priority_cases()

        if model:
            cur.execute(
                """
                SELECT DISTINCT n.id, n.title, n.pub_time, DATE(n.pub_time) as publish_date,
                       n.url, n.global_uid, n.source,
                       COALESCE(a.direction, '中性') as direction,
                       COALESCE(a.horizon, '短期') as horizon,
                       nf.direction as factor_direction,
                       nf.model as model
                FROM news_factor nf
                JOIN news n ON nf.news_id = n.id
                LEFT JOIN analysis a ON a.news_id = n.id AND a.model = nf.model
                WHERE nf.factor_id = %s AND nf.model = %s
                ORDER BY DATE(n.pub_time) DESC, n.pub_time DESC
                """,
                (factor_id, model),
            )
        else:
            cur.execute(
                f"""
                SELECT DISTINCT n.id, n.title, n.pub_time, DATE(n.pub_time) as publish_date,
                       n.url, n.global_uid, n.source,
                       COALESCE(a.direction, '中性') as direction,
                       COALESCE(a.horizon, '短期') as horizon,
                       nf.direction as factor_direction,
                       nf.model as model
                FROM news_factor nf
                JOIN news n ON nf.news_id = n.id
                LEFT JOIN analysis a ON a.news_id = n.id AND a.model = nf.model
                WHERE nf.factor_id = %s
                  AND nf.model = (
                      SELECT nf2.model
                      FROM news_factor nf2
                      WHERE nf2.news_id = n.id AND nf2.factor_id = nf.factor_id
                      ORDER BY CASE nf2.model
                          {priority_cases}
                          ELSE 999
                      END
                      LIMIT 1
                  )
                ORDER BY DATE(n.pub_time) DESC, n.pub_time DESC
                """,
                (factor_id,),
            )
        rows = cur.fetchall()

    news_list = [
        {
            "id": r[0],
            "title": r[1],
            "publish_time": r[2],
            "publish_date": r[3],
            "source": r[6] or "",
            "source_url": r[4] or "",
            "global_uid": r[5],
            "direction": r[7],
            "horizon": r[8],
            "factor_direction": r[9],
            "model": r[10],
        }
        for r in rows
    ]

    return ok({
        "factor": {
            "code": factor_code,
            "name": factor_name,
            "category": factor_category,
        },
        "news": news_list,
        "count": len(news_list),
    })


@router.get("/news/{news_id}/yield")
def get_news_yield_data(
    news_id: int,
    period: str = Query("10年"),
    window_before: int = Query(10),
    window_after: int = Query(10),
):
    data, window_start, window_end = get_yield_window_by_news_id(
        news_id=news_id,
        window_before=window_before,
        window_after=window_after,
        period=period,
    )

    if not data:
        raise HTTPException(status_code=404, detail="新闻不存在或无法获取收益率数据")

    news_info = DBOperations.get_news_by_id(news_id)
    publish_date_str = news_info.get("publish_date") if news_info else None

    base_value = None
    relative_changes = []
    if publish_date_str:
        for item in data:
            if item["date"] == publish_date_str:
                base_value = item["value"]
                break
    if base_value is None and data:
        base_value = data[0]["value"]

    if base_value is not None:
        relative_changes = [
            {
                "date": item["date"],
                "change": round((item["value"] - base_value) / base_value * 100, 4),
            }
            for item in data
        ]

    return ok({
        "news_id": news_id,
        "period": period,
        "publish_date": publish_date_str,
        "data": data,
        "relative_changes": relative_changes,
        "window_before": window_before,
        "window_after": window_after,
        "window_start": window_start,
        "window_end": window_end,
    })
