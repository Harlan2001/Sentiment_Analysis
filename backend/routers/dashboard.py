"""
开发者可视化看板 API — 精简版
"""
from __future__ import annotations

import json, time, threading
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from backend.common.database import execute_query, execute_update, get_db_connection
from backend.config.config import NEWS_SOURCES, PERIOD_MAP, API_PREFIX

router = APIRouter(prefix=f"{API_PREFIX}/dashboard", tags=["dashboard"])

DIR_MAP = {"positive":"看涨","negative":"看跌","neutral":"中性"}
PERIOD_LIST = ["3M","6M","1Y","2Y","3Y","5Y","7Y","10Y","30Y"]
PAGE_TITLES = {"/news":"新闻","/factors":"因子","/data":"数据","/prediction":"预测",
               "/agents":"Agent","/select-strategy":"AI推荐","/strategies":"策略",
               "/change":"变动对比","/macro-signal-logs":"信号日志","/dashboard":"看板","/login":"登录"}
# 会话冷却时间
SESSION_COOLING_SEC = 10
# 指标缓存有效期
CACHE_TTL_SEC = 60
_cache_lock = threading.Lock()

# ============================================================
# 工具
# ============================================================
def _admin(r: Request):
    if not getattr(r.state,'is_admin',False): raise HTTPException(403,detail="需要管理员权限")
    return True

def _fmt_dt(v, f="%Y-%m-%d"):
    return v.strftime(f) if hasattr(v,'strftime') else str(v) if v else None

def _fmt_dt2(v):
    return v.strftime("%Y-%m-%d %H:%M:%S") if hasattr(v,'strftime') and v else None

def _pct(n,d): return round(n/d*100,1) if d>0 else 0

def _safe_one(sql,*params):
    r = execute_query(sql,params,one=True); return r[0] if r else 0

def _page_title(route):
    # '/' 和 '/news' 都映射到新闻首页
    if route == '/' or (route or '').startswith('/news'):
        return '新闻'
    for p,t in PAGE_TITLES.items():
        if route==p or route.startswith(p): return t
    return route

def _assemble_trend(rows, key_map=None):
    bucket:Dict[str,Dict[str,int]]={}
    for d,k,cnt in rows:
        ds=_fmt_dt(d); name=key_map.get(k,k) if key_map else k
        bucket.setdefault(ds,{})[name]=cnt
    return [{"date":ds,**bucket[ds]} for ds in sorted(bucket)]

# ============================================================
# 服务健康（每次计算，通过参数传入模块避免重复调用）
# ============================================================
def _svc():
    try:
        t0=time.time(); execute_query("SELECT 1",one=True)
        mysql={"ok":True,"latency_ms":round((time.time()-t0)*1000,1)}
    except Exception as e: mysql={"ok":False,"error":str(e)}
    return {"mysql":mysql}

# ============================================================
# 基础统计（一次查询收集所有 COUNT）
# ============================================================
def _base():
    r=execute_query("""
        SELECT (SELECT COUNT(*) FROM news),(SELECT COUNT(DISTINCT news_id) FROM analysis),
               (SELECT COUNT(*) FROM news n WHERE NOT EXISTS(SELECT 1 FROM analysis a WHERE a.news_id=n.id)),
               (SELECT COUNT(*) FROM factor),(SELECT COUNT(*) FROM news WHERE indexed=1),
               (SELECT COUNT(*) FROM news WHERE indexed=0 AND content IS NOT NULL AND content!=''),
               (SELECT COUNT(DISTINCT date) FROM yield_data),(SELECT COUNT(*) FROM forecast_report),
               (SELECT COUNT(*) FROM analysis WHERE direction IS NOT NULL AND direction!=''
                 AND horizon IS NOT NULL AND horizon!='' AND reason IS NOT NULL AND reason!=''),
               (SELECT COUNT(*) FROM analysis)
    """,one=True)
    if not r: return {}
    return dict(zip(["news_total","analyzed","pending","factor_total","indexed","vec_pending",
                     "yield_days","report_total","valid_analysis","analysis_total"],r))

# ============================================================
# 模块 A-F（接收 base+svc 复用）
# ============================================================
def _mod_news(total, _b):
    """
    新闻模块数据组装
    total：新闻总条数，_b：_base函数返回的全量基础指标
    返回：新闻大盘数据：总量、7天趋势、来源分布、各来源最新采集时间
    """
    t=execute_query("SELECT DATE(pub_time)d,source,COUNT(*)c FROM news WHERE pub_time>=DATE_SUB(NOW(),INTERVAL 7 DAY) GROUP BY d,source ORDER BY d")
    s=execute_query("SELECT source,COUNT(*)c FROM news GROUP BY source ORDER BY c DESC")
    lt=[];
    for k,n in NEWS_SOURCES.items():
        r=execute_query("SELECT MAX(pub_time) FROM news WHERE source=%s",(k,),one=True)
        v=r[0] if r and r[0] else None
        st="ok"
        if v is None: st="red" # 从未采集过该来源，红色告警
        elif (datetime.now()-v).total_seconds()/3600>24: st="yellow" # 超过24小时无新新闻，黄色警告
        lt.append({"source":k,"name":n,"latest_time":_fmt_dt2(v),"status":st})
    return {"total":total,"trend_7d":_assemble_trend(t,NEWS_SOURCES),
            "source_distribution":[{"source":x,"name":NEWS_SOURCES.get(x,x),"count":c,"percentage":_pct(c,total)} for x,c in s],
            "latest_per_source":lt}

def _mod_analysis(analyzed,pending,news_total,_b):
    """
    AI分析模块数据组装：分析覆盖率、模型分布、涨跌趋势、时效性
    analyzed：已分析新闻数 pending：待分析 news_total：新闻总量 _b：基础指标
    """
    m=execute_query("SELECT model,COUNT(*)c FROM analysis GROUP BY model ORDER BY c DESC")
    d=execute_query("""SELECT DATE(n.pub_time)d,COALESCE(a.direction,'中性')dir,COUNT(*)c
        FROM analysis a JOIN news n ON n.id=a.news_id WHERE n.pub_time>=DATE_SUB(NOW(),INTERVAL 7 DAY) GROUP BY d,dir ORDER BY d""")
    r=execute_query("""SELECT (SELECT MAX(n.pub_time) FROM news n JOIN analysis a ON a.news_id=n.id)la,
        (SELECT MAX(pub_time) FROM news)lp""",one=True)
    lag=round((r[1]-r[0]).total_seconds()/3600,1) if r and r[0] and r[1] else None
    # 处理分析覆盖率，存在待分析则不允许显示100%
    if news_total > 0:
        raw_rate = analyzed / news_total * 100
        if pending > 0 and raw_rate >= 99.9:
            coverage_pct = 99.99
        else:
            coverage_pct = round(raw_rate, 2)
    else:
        coverage_pct = 0
    return {"analyzed":analyzed,"pending":pending,"coverage_pct":coverage_pct,
            "model_distribution":[{"model":x or "unknown","count":c,"percentage":_pct(c,max(analyzed,1))} for x,c in m],
            "direction_7d":_assemble_trend([(dt,DIR_MAP.get(dr,dr),cnt) for dt,dr,cnt in d]),
            "valid_analysis_pct":_pct(_b["valid_analysis"],_b["analysis_total"]),
            "timeliness_diff_hours":lag}

def _mod_factor(total,_b):
    """
    因子模块数据组装：因子分类、类型分布、7天新增、新闻关联覆盖率
    total：因子总数量 _b：基础指标
    """
    r=execute_query("SELECT category,factor_type,COUNT(*)c FROM factor GROUP BY category,factor_type")
    cat,typ={},{}
    for cat_n,typ_n,cnt in r:
        cat[cat_n]=cat.get(cat_n,0)+cnt
        typ[typ_n or "unknown"]=typ.get(typ_n or "unknown",0)+cnt
    n7=_safe_one("SELECT COUNT(*) FROM factor_discovery_history WHERE created_at>=DATE_SUB(NOW(),INTERVAL 7 DAY)")
    tr=execute_query("SELECT DATE(created_at)d,COUNT(*)c FROM factor_discovery_history WHERE created_at>=DATE_SUB(NOW(),INTERVAL 7 DAY) GROUP BY d ORDER BY d")
    # 补全近7天缺失的日期（值为0），确保前端折线图连续
    tr_map={_fmt_dt(d):c for d,c in tr}
    today=date.today()
    tr=[(today-timedelta(days=i), tr_map.get((today-timedelta(days=i)).isoformat(),0)) for i in range(6,-1,-1)]
    # 统计：绑定因子的分析新闻 / 总分析新闻，得到因子关联覆盖率
    row=execute_query("""SELECT (SELECT COUNT(DISTINCT nf.news_id) FROM news_factor nf JOIN analysis a ON nf.news_id=a.news_id),
        (SELECT COUNT(DISTINCT news_id) FROM analysis)""",one=True)
    assoc=_pct(row[0],row[1]) if row and row[1]>0 else 0
    r2=execute_query("SELECT MAX(created_at) FROM news_factor",one=True)
    lm=round((datetime.now()-r2[0]).total_seconds()/60,1) if r2 and r2[0] else None
    return {"total":total,
            "category_distribution":[{"category":k,"count":v} for k,v in sorted(cat.items(),key=lambda x:-x[1])],
            "type_distribution":[{"factor_type":k,"count":v} for k,v in typ.items()],
            "new_factors_7d":n7,"new_factors_trend_7d":[{"date":_fmt_dt(d),"count":c} for d,c in tr],
            "association_coverage_pct":assoc,"update_timeliness_diff_minutes":lm}

def _mod_vector(indexed, pending, svc, _b):
    """
    向量库模块：已向量化、待向量化数量、FAISS库状态、Embedding模型状态
    indexed：已入库新闻 pending：待入库新闻 svc：服务健康状态
    """
    t = indexed + pending
    if t > 0:
        raw_rate = indexed / t * 100
        # 存在待处理数据且接近100%时强制封顶99.99，避免展示100%误导
        if pending > 0 and raw_rate >= 99.9:
            coverage_pct = 99.99
        else:
            coverage_pct = round(raw_rate, 2)
    else:
        coverage_pct = 0
    return {"indexed_count": indexed,
        "pending_count": pending,
        "coverage_pct": coverage_pct}

def _mod_yield(_b):
    """
    债券收益率模块：数据时间区间、各期限完整度、各期限近7天走势图
    _b：基础指标
    """
    r=execute_query("SELECT MIN(date),MAX(date),COUNT(DISTINCT date) FROM yield_data",one=True)
    p=execute_query("SELECT period,COUNT(*)c FROM yield_data GROUP BY period ORDER BY period")
    sp=[];
    for dbp in PERIOD_LIST:
        v=execute_query("SELECT date,value FROM yield_data WHERE period=%s ORDER BY date DESC LIMIT 7",(dbp,))
        ld=v[-1][0] if v else None; lv=float(v[-1][1]) if v else None
        sp.append({"period":dbp,"display_name":PERIOD_MAP.get(dbp,dbp),
                   "latest_date":_fmt_dt(ld),"latest_value":lv,
                   "sparkline":[float(x) for _,x in reversed(v)]})
    return {"date_min":_fmt_dt(r[0]) if r and r[0] else None,
            "date_max":_fmt_dt(r[1]) if r and r[1] else None,
            "coverage_days":r[2] if r else 0,
            "period_completeness":[{"period":x,"display_name":PERIOD_MAP.get(x,x),"count":c} for x,c in p],
            "latest_yields":sp}

def _mod_forecast(_b):
    """
    预测模块数据组装：报告总数、最新报告日期、30天覆盖情况
    _b：基础指标
    """
    r=execute_query("SELECT MAX(trade_date) FROM forecast_report",one=True)
    cal=execute_query("SELECT DISTINCT trade_date FROM forecast_report WHERE trade_date>=DATE_SUB(CURDATE(),INTERVAL 30 DAY) ORDER BY trade_date")
    covered={_fmt_dt(x[0]) for x in cal}
    today=date.today()
     # 生成近30天日期数组，标记当天是否存在预测报告
    return {"total_reports":_b["report_total"],"latest_date":_fmt_dt(r[0]) if r and r[0] else None,
            "coverage_30d":[{"date":(today-timedelta(days=29-i)).isoformat(),
                             "has_report":(today-timedelta(days=29-i)).isoformat() in covered} for i in range(30)]}

# ============================================================
# 缓存（加锁防穿透）
# ============================================================
def _cache_read():
    """读取缓存：查询60秒内生成的指标快照，存在直接返回解析后的字典"""
    r=execute_query("SELECT core_metrics FROM dashboard_metric_cache WHERE calc_time>=DATE_SUB(NOW(),INTERVAL %s SECOND) ORDER BY calc_time DESC LIMIT 1",(CACHE_TTL_SEC,),one=True)
    if r and r[0]:
        return json.loads(r[0]) if isinstance(r[0],str) else r[0]
    return None

def _cache_write(data):
    """写入缓存：将全量指标JSON存入缓存表"""
    execute_update("INSERT INTO dashboard_metric_cache (calc_time,core_metrics,service_status) VALUES (NOW(),%s,'{}')",
                   (json.dumps(data,default=str),))

def _cache_cleanup():
    """缓存清理：删除1天前的旧缓存，避免表无限膨胀"""
    execute_update("DELETE FROM dashboard_metric_cache WHERE calc_time<DATE_SUB(NOW(),INTERVAL 1 DAY)")

# ============================================================
# 核心看板指标接口
# ============================================================
@router.get("/core")
def get_dashboard_core():
    """
    前端大盘首页核心数据接口（GET请求）
    逻辑：先读缓存→无缓存加锁再读一次缓存→无缓存全量计算→写入缓存→返回数据
    """
    cached=_cache_read()
    if cached: return {"generated_at":datetime.now().isoformat(),"from_cache":True,**cached}

    with _cache_lock:
        cached=_cache_read()
        if cached: return {"generated_at":datetime.now().isoformat(),"from_cache":True,**cached}

        svc=_svc()
        base=_base()
        if not base: return {"error":"数据库无数据"}

        data={
            "generated_at":datetime.now().isoformat(),"from_cache":False,
            "service_status":svc,
            "top_cards":{"news_total":base["news_total"],"analyzed":base["analyzed"],"pending":base["pending"],
                         "factor_total":base["factor_total"],
                         "yield_days":base["yield_days"]},
            "news":_mod_news(base["news_total"],base),
            "analysis":_mod_analysis(base["analyzed"],base["pending"],base["news_total"],base),
            "factor":_mod_factor(base["factor_total"],base),
            "vector":_mod_vector(base["indexed"],base["vec_pending"],svc,base),
            "yield":_mod_yield(base),
            "forecast":_mod_forecast(base),
        }
        _cache_write(data)
        _cache_cleanup()  # 延迟清理，不在核心路径阻塞
        return data

# ============================================================
# 历史指标快照查询接口
# ============================================================
@router.get("/history")
def get_dashboard_history(days:int=Query(7,ge=1,le=90)):
    """
    查询历史手动保存的看板快照
    参数 days：查询最近N天快照，最小1最大90，默认7天
    """
    rs=execute_query("SELECT id,snapshot_time,metrics_json FROM dashboard_snapshot WHERE snapshot_time>=DATE_SUB(NOW(),INTERVAL %s DAY) ORDER BY snapshot_time DESC",(days,))
    return [{"id":r[0],"snapshot_time":_fmt_dt2(r[1]),
             "metrics":json.loads(r[2]) if isinstance(r[2],str) else r[2]} for r in rs]

# ============================================================
# 手动保存当前大盘快照接口
# ============================================================
@router.post("/snapshot")
def create_dashboard_snapshot():
    """POST接口，手动触发保存当前大盘指标到快照表，用于历史回溯"""
    core=get_dashboard_core()
    execute_update("INSERT INTO dashboard_snapshot (snapshot_time,metrics_json) VALUES (NOW(),%s)",
                   (json.dumps(core,default=str,ensure_ascii=False),))
    return {"success":True}

# ============================================================
# 用户行为事件
# ============================================================
class PageVisitEvent(BaseModel):
    page_route:str; page_title:Optional[str]=None; enter_time:str
    leave_time:Optional[str]=None; duration_sec:Optional[int]=None; exit_type:Optional[str]=None
    action_type:Optional[str]="page_enter"; action_target:Optional[str]=None; action_detail:Optional[Any]=None
    client_ts:Optional[str]=None

class BehaviorBatchRequest(BaseModel): events:List[PageVisitEvent]

@router.post("/behavior/batch")
def post_behavior_batch(body:BehaviorBatchRequest,request:Request):
    """
    前端批量上报页面访问行为日志接口
    body：前端传的批量事件数组（含 action_type/action_target/action_detail）
    request：当前请求对象，读取登录用户名
    """
    un=getattr(request.state,'username',None)
    if not un or un=='anonymous': return {"received":0,"note":"anonymous skipped"}
    r=execute_query("SELECT id FROM users WHERE username=%s",(un,),one=True)
    if not r: return {"received":0,"note":f"user '{un}' not found"}
    uid=r[0]
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 查询当前用户未关闭的活跃会话
            cur.execute("SELECT id,login_time FROM user_session WHERE user_id=%s AND logout_time IS NULL ORDER BY login_time DESC LIMIT 1",(uid,))
            act=cur.fetchone(); reuse=False
            if act:
                sid,_=act
                # 查询该会话最后一次页面离开时间
                cur.execute("SELECT MAX(leave_time) FROM user_page_view WHERE session_id=%s",(sid,))
                last=cur.fetchone()[0]
                # 冷却时间内，复用当前会话，不新建
                if last and (datetime.now()-last).total_seconds()<=SESSION_COOLING_SEC: reuse=True
            if reuse: sid=act[0]
            else:
                # 关闭旧会话，创建新会话
                cur.execute("UPDATE user_session SET logout_time=NOW(),duration_sec=TIMESTAMPDIFF(SECOND,login_time,NOW()) WHERE user_id=%s AND logout_time IS NULL",(uid,))
                cur.execute("INSERT INTO user_session (user_id,username,login_time) VALUES (%s,%s,NOW())",(uid,un))
                sid=cur.lastrowid
            for evt in body.events:
                cur.execute("""INSERT INTO user_page_view
                    (session_id,user_id,username,page_route,page_title,enter_time,leave_time,duration_sec,exit_type,
                     action_type,action_target,action_detail,client_ts)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (sid,uid,un,evt.page_route,evt.page_title or _page_title(evt.page_route),
                     evt.enter_time,evt.leave_time,evt.duration_sec,evt.exit_type,
                     evt.action_type or "page_enter",evt.action_target,
                     json.dumps(evt.action_detail,ensure_ascii=False) if evt.action_detail else None,
                     evt.client_ts or evt.enter_time))
        conn.commit()
    return {"received":len(body.events)}

# ============================================================
# 清理长时间无操作的闲置会话接口（管理员）
# ============================================================
@router.post("/cleanup-sessions")
def cleanup_stale_sessions(minutes:int=Query(30)):
    """
    批量标记超时会话为已登出
    minutes：超过多少分钟无操作判定为闲置，默认30分钟
    """
    # LEFT JOIN关联页面访问表，拿到每个会话最后离开时间，一次性更新
    n=execute_update("""UPDATE user_session s
        LEFT JOIN (SELECT session_id,MAX(leave_time)last FROM user_page_view GROUP BY session_id) p ON p.session_id=s.id
        SET s.logout_time=NOW(),s.duration_sec=TIMESTAMPDIFF(SECOND,s.login_time,NOW())
        WHERE s.logout_time IS NULL AND p.last IS NOT NULL
        AND p.last<DATE_SUB(NOW(),INTERVAL %s MINUTE)""",(minutes,))
    return {"cleaned":n,"threshold_minutes":minutes}

# ============================================================
# 用户行为统计大盘接口（仅管理员访问）
# ============================================================
@router.get("/behavior-stats")
def get_behavior_stats(days:int=Query(7,ge=1,le=90),_a=Depends(_admin)):
    """
    行为统计：活跃用户、会话数、页面访问排行、平均停留时长 + 7日趋势 + 时段热力图
    _a=Depends(_admin)：接口强制校验管理员权限，非管理员403
    """
    # 7日活跃趋势: DAU + 每日会话数
    trend_rows=execute_query("""
        SELECT DATE(login_time)d,COUNT(DISTINCT user_id)dau,COUNT(*)sessions
        FROM user_session WHERE login_time>=DATE_SUB(CURDATE(),INTERVAL %s DAY)
        GROUP BY d ORDER BY d""",(days,))
    activity_trend=[{"date":_fmt_dt(r[0]),"dau":r[1],"sessions":r[2]} for r in trend_rows]

    # 时段热力分布: 24h × 7天
    heatmap_rows=execute_query("""
        SELECT HOUR(enter_time)h,DAYOFWEEK(enter_time)dow,COUNT(*)c
        FROM user_page_view WHERE enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY)
        GROUP BY h,dow ORDER BY dow,h""",(days,))
    heatmap=[{"hour":r[0],"day_of_week":r[1],"count":r[2]} for r in heatmap_rows]

    # 重度用户 + 流失风险
    power_users=_safe_one("SELECT COUNT(*) FROM user_behavior_profile WHERE is_power_user=1")
    churn_users=_safe_one("SELECT COUNT(*) FROM user_behavior_profile WHERE churn_risk_score>0.5")

    return {
        "active_users_today":_safe_one("SELECT COUNT(DISTINCT user_id) FROM user_page_view WHERE DATE(enter_time)=CURDATE()"),
        "sessions_today":_safe_one("SELECT COUNT(*) FROM user_session WHERE DATE(login_time)=CURDATE()"),
        "avg_duration_7d":int(_safe_one("SELECT COALESCE(AVG(duration_sec),0) FROM user_session WHERE login_time>=DATE_SUB(NOW(),INTERVAL %s DAY) AND duration_sec>0",days)),
        "top_page":(lambda r:r[0] if r else None)(execute_query("SELECT page_route FROM user_page_view WHERE enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY) GROUP BY page_route ORDER BY COUNT(*) DESC LIMIT 1",(days,),one=True)),
        "power_users":power_users,
        "churn_risk_users":churn_users,
        "activity_trend":activity_trend,
        "hourly_heatmap":heatmap,
        "page_distribution":[{"page_route":r[0],"page_title":r[1] or _page_title(r[0]),"count":r[2]}
            for r in execute_query("""SELECT CASE WHEN page_route IN ('/','/news') THEN '/news' ELSE page_route END AS route,
                CASE WHEN page_route IN ('/','/news') THEN '新闻' ELSE page_title END AS title,
                COUNT(*)c FROM user_page_view WHERE enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY)
                GROUP BY route, title ORDER BY c DESC""",(days,))],
        "page_avg_duration":[{"page_route":r[0],"avg_sec":round(float(r[1]),0) if r[1] else 0}
            for r in execute_query("""SELECT CASE WHEN page_route IN ('/','/news') THEN '/news' ELSE page_route END AS route,
                AVG(duration_sec) FROM user_page_view WHERE enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY)
                AND duration_sec>0 GROUP BY route ORDER BY 2 DESC""",(days,))],
    }

# ============================================================
# 行为日志分页查询接口（管理员）
# ============================================================
@router.get("/behavior-logs")
def get_behavior_logs(user_id:Optional[str]=Query(None),page_route:Optional[str]=Query(None),
                      action_type:Optional[str]=Query(None),
                      start:Optional[str]=Query(None),end:Optional[str]=Query(None),
                      limit:int=Query(100,ge=1,le=1000),offset:int=Query(0,ge=0),_a=Depends(_admin)):
    """
    分页查询用户行为明细日志（含操作类型、目标），支持多维筛选
    limit：单页条数 1~1000，默认100
    offset：分页偏移量，从0开始
    """
    cond,params=["1=1"],[]
    for k,v in [("user_id",user_id),("page_route",page_route),("action_type",action_type)]:
        if v: cond.append(f"{k}=%s"); params.append(v)
    if start: cond.append("enter_time>=%s"); params.append(start)
    if end: cond.append("enter_time<=%s"); params.append(end)
    w=" AND ".join(cond)
    total=_safe_one(f"SELECT COUNT(*) FROM user_page_view WHERE {w}",*params)
    rows=execute_query(f"""SELECT id,session_id,user_id,username,page_route,page_title,
        enter_time,leave_time,duration_sec,exit_type,action_type,action_target,action_detail
        FROM user_page_view WHERE {w} ORDER BY enter_time DESC LIMIT %s OFFSET %s""",
        tuple(params)+(limit,offset))
    return {"items":[{"id":r[0],"session_id":r[1],"user_id":r[2],"username":r[3],"page_route":r[4],
            "page_title":r[5] or _page_title(r[4]) if r[4] else "",
            "enter_time":r[6].isoformat() if hasattr(r[6],'isoformat') else str(r[6]),
            "leave_time":r[7].isoformat() if r[7] and hasattr(r[7],'isoformat') else (str(r[7]) if r[7] else None),
            "duration_sec":r[8],"exit_type":r[9],
            "action_type":r[10] or "page_enter",
            "action_target":r[11] or "",
            "action_detail":json.loads(r[12]) if isinstance(r[12],str) else r[12] if r[12] else None}
            for r in rows],
            "total":total,"limit":limit,"offset":offset,"total_pages":(total+limit-1)//limit if total>0 else 0}

# ============================================================
# 用户画像接口（管理员）
# ============================================================

def _compute_user_profile(user_id:int,username:str):
    """计算单个用户画像并 UPSERT 到 user_behavior_profile"""
    now=datetime.now()
    d30=now-timedelta(days=30)

    # 活跃概览
    total_sessions=_safe_one("SELECT COUNT(*) FROM user_session WHERE user_id=%s",user_id)
    total_page_views=_safe_one("SELECT COUNT(*) FROM user_page_view WHERE user_id=%s",user_id)
    total_active_sec=int(_safe_one("SELECT COALESCE(SUM(duration_sec),0) FROM user_page_view WHERE user_id=%s AND duration_sec>0",user_id))
    fv_row=execute_query("SELECT MIN(DATE(enter_time)) FROM user_page_view WHERE user_id=%s",(user_id,),one=True)
    first_visit=_fmt_dt(fv_row[0]) if fv_row and fv_row[0] else None
    lv_row=execute_query("SELECT MAX(enter_time) FROM user_page_view WHERE user_id=%s",(user_id,),one=True)
    last_visit=lv_row[0] if lv_row else None
    active_days_30d=_safe_one("SELECT COUNT(DISTINCT DATE(enter_time)) FROM user_page_view WHERE user_id=%s AND enter_time>=%s",user_id,d30)
    avg_session_sec=int(_safe_one("SELECT COALESCE(AVG(duration_sec),0) FROM user_session WHERE user_id=%s AND duration_sec>0",user_id))
    avg_daily_pages=round(active_days_30d and total_page_views/active_days_30d or 0,2)

    # 页面偏好
    page_rows=execute_query("""SELECT page_route,COUNT(*)c FROM user_page_view
        WHERE user_id=%s AND enter_time>=%s GROUP BY page_route ORDER BY c DESC""",(user_id,d30))
    total_pv=sum(r[1] for r in page_rows) if page_rows else 0
    page_affinity={r[0]:round(r[1]/total_pv,3) if total_pv>0 else 0 for r in page_rows}
    # 报告/策略导向判定
    pred_pct=page_affinity.get("/prediction",0)
    strat_pct=page_affinity.get("/strategies",0)+page_affinity.get("/change",0)
    is_report_focused=pred_pct>0.5
    is_strategy_focused=strat_pct>0.5

    # 时段偏好
    hour_rows=execute_query("""SELECT HOUR(enter_time)h,COUNT(*)c FROM user_page_view
        WHERE user_id=%s AND enter_time>=%s GROUP BY h ORDER BY c DESC""",(user_id,d30))
    hour_dist={str(r[0]):r[1] for r in hour_rows}
    peak_hour=hour_rows[0][0] if hour_rows else None

    # 功能覆盖
    distinct_pages=_safe_one("SELECT COUNT(DISTINCT page_route) FROM user_page_view WHERE user_id=%s AND enter_time>=%s",user_id,d30)
    advanced_pages=["/agents","/select-strategy"]
    adv_count=_safe_one("SELECT COUNT(*) FROM user_page_view WHERE user_id=%s AND page_route IN (%s,%s)",
                        user_id,advanced_pages[0],advanced_pages[1])
    advanced_feature_used=adv_count>0

    # 行为特征
    is_power_user=active_days_30d>20 and (total_active_sec/(max(active_days_30d,1)*60)>30)
    # 流失风险: 最近不活跃天数/30
    last_active_row=execute_query("SELECT MAX(DATE(enter_time)) FROM user_page_view WHERE user_id=%s",(user_id,),one=True)
    last_active_date=last_active_row[0] if last_active_row else None
    if last_active_date:
        days_since=(now.date()-last_active_date).days if hasattr(last_active_date,'date') else (now.date()-last_active_date).days if isinstance(last_active_date,date) else 0
        churn_risk=round(min(days_since/30.0,1.0),2)
    else:
        churn_risk=1.0

    # UPSERT
    execute_update("""INSERT INTO user_behavior_profile
        (user_id,username,total_sessions,total_page_views,total_active_sec,
         first_visit,last_visit,active_days_30d,avg_session_sec,avg_daily_pages_30d,
         page_affinity_json,peak_hour,hour_distribution_json,
         distinct_pages_30d,advanced_feature_used,
         is_power_user,is_report_focused,is_strategy_focused,churn_risk_score,
         computed_at,profile_version)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),'v1.0')
        ON DUPLICATE KEY UPDATE
         username=VALUES(username),total_sessions=VALUES(total_sessions),
         total_page_views=VALUES(total_page_views),total_active_sec=VALUES(total_active_sec),
         first_visit=VALUES(first_visit),last_visit=VALUES(last_visit),
         active_days_30d=VALUES(active_days_30d),avg_session_sec=VALUES(avg_session_sec),
         avg_daily_pages_30d=VALUES(avg_daily_pages_30d),
         page_affinity_json=VALUES(page_affinity_json),peak_hour=VALUES(peak_hour),
         hour_distribution_json=VALUES(hour_distribution_json),
         distinct_pages_30d=VALUES(distinct_pages_30d),
         advanced_feature_used=VALUES(advanced_feature_used),
         is_power_user=VALUES(is_power_user),is_report_focused=VALUES(is_report_focused),
         is_strategy_focused=VALUES(is_strategy_focused),
         churn_risk_score=VALUES(churn_risk_score),computed_at=NOW()""",
        (user_id,username,total_sessions,total_page_views,total_active_sec,
         first_visit,last_visit,active_days_30d,avg_session_sec,avg_daily_pages,
         json.dumps(page_affinity,ensure_ascii=False),peak_hour,
         json.dumps(hour_dist,ensure_ascii=False),
         distinct_pages,advanced_feature_used,
         is_power_user,is_report_focused,is_strategy_focused,churn_risk))
    return {"user_id":user_id,"username":username,"computed":True}

def _profile_row_to_dict(r):
    """将 user_behavior_profile 查询行转为字典"""
    return {
        "id":r[0],"user_id":r[1],"username":r[2],
        "total_sessions":r[3],"total_page_views":r[4],"total_active_sec":r[5],
        "first_visit":_fmt_dt(r[6]) if r[6] else None,
        "last_visit":r[7].isoformat() if r[7] and hasattr(r[7],'isoformat') else str(r[7]) if r[7] else None,
        "active_days_30d":r[8],"avg_session_sec":r[9],"avg_daily_pages_30d":float(r[10]) if r[10] else 0,
        "page_affinity":json.loads(r[11]) if isinstance(r[11],str) else r[11] if r[11] else {},
        "peak_hour":r[12],
        "hour_distribution":json.loads(r[13]) if isinstance(r[13],str) else r[13] if r[13] else {},
        "distinct_pages_30d":r[14],"advanced_feature_used":bool(r[15]),
        "is_power_user":bool(r[16]),"is_report_focused":bool(r[17]),"is_strategy_focused":bool(r[18]),
        "churn_risk_score":float(r[19]) if r[19] else 0,
        "computed_at":r[20].isoformat() if r[20] and hasattr(r[20],'isoformat') else (str(r[20]) if r[20] else None),
        "profile_version":r[21],"updated_at":r[22].isoformat() if r[22] and hasattr(r[22],'isoformat') else None,
    }

@router.get("/behavior/profiles")
def get_behavior_profiles(sort_by:str=Query("last_visit"),order:str=Query("desc"),_a=Depends(_admin)):
    """获取所有用户行为画像列表"""
    allowed={"last_visit","active_days_30d","total_active_sec","total_page_views","churn_risk_score"}
    if sort_by not in allowed: sort_by="last_visit"
    order_dir="DESC" if order.lower()=="desc" else "ASC"
    rows=execute_query(f"""SELECT id,user_id,username,total_sessions,total_page_views,total_active_sec,
        first_visit,last_visit,active_days_30d,avg_session_sec,avg_daily_pages_30d,
        page_affinity_json,peak_hour,hour_distribution_json,
        distinct_pages_30d,advanced_feature_used,
        is_power_user,is_report_focused,is_strategy_focused,churn_risk_score,
        computed_at,profile_version,updated_at
        FROM user_behavior_profile ORDER BY {sort_by} {order_dir}""")
    return {"profiles":[_profile_row_to_dict(r) for r in rows],"count":len(rows)}

@router.get("/behavior/profile/{user_id}")
def get_behavior_profile(user_id:int,_a=Depends(_admin)):
    """获取单个用户画像（含雷达图数据），不存在时自动计算"""
    r=execute_query("""SELECT id,user_id,username,total_sessions,total_page_views,total_active_sec,
        first_visit,last_visit,active_days_30d,avg_session_sec,avg_daily_pages_30d,
        page_affinity_json,peak_hour,hour_distribution_json,
        distinct_pages_30d,advanced_feature_used,
        is_power_user,is_report_focused,is_strategy_focused,churn_risk_score,
        computed_at,profile_version,updated_at
        FROM user_behavior_profile WHERE user_id=%s""",(user_id,),one=True)
    if not r:
        # 用户存在但无画像 → 实时计算
        ur=execute_query("SELECT id,username FROM users WHERE id=%s",(user_id,),one=True)
        if not ur: raise HTTPException(404,f"用户 {user_id} 不存在")
        _compute_user_profile(ur[0],ur[1])
        r=execute_query("""SELECT id,user_id,username,total_sessions,total_page_views,total_active_sec,
            first_visit,last_visit,active_days_30d,avg_session_sec,avg_daily_pages_30d,
            page_affinity_json,peak_hour,hour_distribution_json,
            distinct_pages_30d,advanced_feature_used,
            is_power_user,is_report_focused,is_strategy_focused,churn_risk_score,
            computed_at,profile_version,updated_at
            FROM user_behavior_profile WHERE user_id=%s""",(user_id,),one=True)
        if not r: raise HTTPException(500,"画像计算失败")

    profile=_profile_row_to_dict(r)

    # 雷达图数据：标准化为 0-100 分
    max_active_days=30; max_daily_pages=50; max_avg_sec=3600; max_distinct=15
    radar=[
        {"dimension":"活跃天数","score":min(100,round(profile["active_days_30d"]/max_active_days*100)),"value":profile["active_days_30d"],"unit":"天"},
        {"dimension":"日均访问页数","score":min(100,round(float(profile["avg_daily_pages_30d"])/max_daily_pages*100)),"value":profile["avg_daily_pages_30d"],"unit":"页/天"},
        {"dimension":"平均停留时长","score":min(100,round((profile["avg_session_sec"] or 0)/max_avg_sec*100)),"value":profile["avg_session_sec"] or 0,"unit":"秒"},
        {"dimension":"功能覆盖面","score":min(100,round(profile["distinct_pages_30d"]/max_distinct*100)),"value":profile["distinct_pages_30d"],"unit":"种页面"},
        {"dimension":"深度使用度","score":100 if profile["advanced_feature_used"] else 20,"value":1 if profile["advanced_feature_used"] else 0,"unit":"是否使用高级功能"},
        {"dimension":"活跃频次","score":min(100,round(profile["active_days_30d"]/max_active_days*100)),"value":profile["active_days_30d"],"unit":"天/30天"},
    ]

    # 偏好详情
    page_affinity=profile.get("page_affinity",{}) or {}
    top_pages=sorted(page_affinity.items(),key=lambda x:-x[1])[:5]
    hour_dist=profile.get("hour_distribution",{}) or {}
    peak_slot=_peak_slot_label(profile.get("peak_hour"))

    profile["radar"]=radar
    profile["preferences"]={
        "top_pages":[{"route":r,"title":_page_title(r),"affinity":round(v,3)} for r,v in top_pages],
        "peak_slot":peak_slot,
        "peak_hour":profile.get("peak_hour"),
        "hour_distribution":hour_dist,
        "report_focused":profile.get("is_report_focused"),
        "strategy_focused":profile.get("is_strategy_focused"),
        "power_user":profile.get("is_power_user"),
        "churn_risk":profile.get("churn_risk_score"),
    }
    return profile

def _peak_slot_label(h):
    if h is None: return "未知"
    h=int(h)
    if 6<=h<12: return "上午"
    if 12<=h<14: return "午间"
    if 14<=h<18: return "下午"
    if 18<=h<22: return "晚间"
    return "深夜"

@router.get("/behavior/compare")
def get_behavior_compare(user_ids:str=Query(...),_a=Depends(_admin)):
    """对比2-3个用户画像"""
    ids=[int(x.strip()) for x in user_ids.split(",") if x.strip()]
    if len(ids)<2 or len(ids)>3: raise HTTPException(400,"需要2-3个用户ID")
    profiles=[]
    for uid in ids:
        try:
            p=get_behavior_profile(uid)
            profiles.append(p)
        except HTTPException: pass
    if len(profiles)<2: raise HTTPException(404,"至少需要2个有效用户")

    # 对比维度
    dims=["active_days_30d","avg_daily_pages_30d","avg_session_sec","distinct_pages_30d","total_page_views","total_active_sec"]
    dim_labels={"active_days_30d":"活跃天数(30日)","avg_daily_pages_30d":"日均访问页数","avg_session_sec":"平均停留(秒)",
                "distinct_pages_30d":"功能覆盖面","total_page_views":"累计页面访问","total_active_sec":"累计活跃时长(秒)"}
    comparison=[]
    for dim in dims:
        entry={"dimension":dim,"label":dim_labels.get(dim,dim),"values":[]}
        for p in profiles:
            entry["values"].append({"user_id":p["user_id"],"username":p["username"],"value":p.get(dim,0)})
        comparison.append(entry)
    return {"profiles":profiles,"comparison":comparison}

@router.post("/behavior/compute-profile/{user_id}")
def trigger_profile_compute(user_id:int,_a=Depends(_admin)):
    """手动触发单个用户画像计算"""
    ur=execute_query("SELECT id,username FROM users WHERE id=%s",(user_id,),one=True)
    if not ur: raise HTTPException(404,f"用户 {user_id} 不存在")
    return _compute_user_profile(ur[0],ur[1])

@router.post("/behavior/compute-all-profiles")
def trigger_all_profiles_compute(_a=Depends(_admin)):
    """批量计算全部用户画像"""
    users=execute_query("SELECT id,username FROM users")
    done=0
    for uid,un in users:
        try:
            _compute_user_profile(uid,un)
            done+=1
        except Exception: pass
    return {"total_users":len(users),"computed":done}
