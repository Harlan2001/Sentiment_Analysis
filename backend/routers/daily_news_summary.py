"""每日新闻总结任务 HTTP 编排。"""

from __future__ import annotations

import asyncio
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator

from backend.config.config import API_PREFIX, NEWS_SOURCES
from backend.news_summary.service import generate_daily_news_summary
from backend.repositories.news_summary_repository import (
    DailyNewsSummaryNotFoundError,
    DailyNewsSummaryRepository,
)

router = APIRouter(
    prefix=f"{API_PREFIX}/daily-news-summaries", tags=["daily-news-summaries"]
)
_background_tasks: set[asyncio.Task] = set()
POLICY_DEMO_SUMMARY_ID = 0


def _policy_demo_summary(owner_username: str) -> dict:
    """返回政策驱动演示对话所指向的固定新闻总结，不写入用户任务数据。"""
    return {
        "id": POLICY_DEMO_SUMMARY_ID,
        "owner_username": owner_username,
        "start_date": "2026-09-03",
        "end_date": "2026-09-09",
        "sources_json": ["数据源2"],
        "focus": "政策驱动：央行缩长增短、财政增量政策、海外利率波动",
        "status": "succeeded",
        "news_count": 9,
        "source_stats_json": {"数据源2": 9},
        "summary": """# 政策驱动｜新闻总结

## 样本概览

本次汇总覆盖 **2026 年 9 月 3 日至 9 日**，共纳入 9 条政策与市场新闻，其中国内政策 5 条、海外联动 4 条。所有方向均表示新闻对 **中国国债价格** 的影响，而不是对股票、实体经济或政策本身的价值判断。

| 方向 | 条数 | 主要来源 |
|---|---:|---|
| 利多债市 | 5 | 资金面呵护、海外宽松预期、美债回购与资产再配置 |
| 利空债市 | 3 | 财政供给、宽信用与基建投资预期 |
| 中性 | 1 | 海外利率上行与避险需求相互抵消 |

## 核心结论

本周政策信号并非简单的“全面宽松”或“全面收紧”，而是呈现明显的期限分化：**短端由央行流动性操作提供支撑，长端则在财政扩张、政府债供给和海外利率变化之间反复定价。**

央行通过隔夜与 7 天逆回购对冲缴款和跨月资金缺口，降低了短端资金价格突然上行的风险；但 MLF 缩量说明中长期流动性并未同步大幅扩张。与此同时，财政支出、贴息和新基建政策改善增长与宽信用预期，也可能带来更多政府债净融资，因此对中长端构成供给和风险偏好两方面的压力。

海外方向较此前有所改善：美联储边际宽松预期、美债回购以及全球资产再配置，均有助于缓解中外利差和资本流动压力。但美债长端仍处于高波动环境，海外渠道对国内长端的影响仍是双向的。

## 分渠道新闻解读

### 1. 货币与资金面

央行“缩长增短”组合的重点在期限结构，而非总量放水。MLF 缩量 1000 亿元，但短期逆回购加量并提高操作上限，意在平滑政府债缴款和临时资金缺口。其直接影响是稳定 DR001、DR007 和机构融资预期，首先利多短端国债；对 10 年以上期限的支撑相对有限。

### 2. 财政与产业政策

前 7 月广义财政支出超过 20 万亿元，叠加贴息扩围和新一代通信网建设，说明稳增长工具正在从资金供给进一步传导至消费、信贷与产业投资。其利空债市的核心不是“财政支出增加”本身，而是 **政府债供给增加、宽信用预期升温和经济增长预期改善**。零基预算改革通过压减低效支出、降低新增融资需求，对上述压力形成部分对冲。

### 3. 海外政策与市场

海外通胀回落和美联储边际宽松预期，有助于推动美债收益率回落并改善中外利差；美国财政部扩大长债回购和调整发债结构，也可能降低美债长端净供给。另一方面，全球科技股重估与长端利率高波动会同时带来避险买盘和估值约束，因此海外新闻总体偏利多，但不能据此直接形成单向久期判断。

## 因子与数据验证

9 条新闻累计命中 **41 次、31 个唯一因子**。出现频率最高或传导最关键的因子包括：美债收益率、中外利差、政府债净融资额、债券供给压力、财政支出节奏和全球流动性传导。

后续验证应按以下顺序进行：

1. 观察 DR001、DR007 是否继续围绕政策利率稳定运行；
2. 跟踪政府债周度发行、净融资和一级招标需求；
3. 判断财政支出是否进一步带动社融、信贷与实体需求；
4. 观察 10 年与 30 年美债收益率、美元指数和人民币汇率；
5. 最后再根据资金、供给和海外变量的组合变化调整久期。

## 收益率曲线判断

基准情景下，短端收益率小幅下行或维持低位，中端以区间震荡为主，长端受财政供给和海外波动制约，短端表现优于长端，曲线存在阶段性陡峭化倾向。

如果政府债发行低于预期且美债收益率明显回落，长端可能出现资本利得机会；如果财政供给提速并叠加美债上行，则应降低组合久期和杠杆，优先保留流动性更好的短债与票息收益。

## 跟踪清单

- **资金面：** DR001、DR007、质押式回购成交量；
- **供给面：** 政府债净融资、一级招标倍数与边际利率；
- **基本面：** 财政支出、社融、信贷和投资增速；
- **海外面：** 美债长端收益率、美元指数、人民币汇率与中外利差。

当前建议仍是：以短久期票息和杠杆套息作为基础收益来源，长久期保持战术仓位，等待财政供给或海外利率出现更明确拐点。""",
        "references_json": [
            {
                "news_id": 18224,
                "title": "MLF、隔夜逆回购双箭齐发，如何理解央行“缩长增短”操作意图？",
                "publish_time": "2026-09-06T19:54:00",
                "source": "数据源2",
                "direction": "positive",
                "horizon": "短期",
            },
            {
                "news_id": 18349,
                "title": "前7月广义财政支出超20万亿，财政部谋划更多增量政策",
                "publish_time": "2026-09-09T19:42:00",
                "source": "数据源2",
                "direction": "negative",
                "horizon": "中期",
            },
            {
                "news_id": 18157,
                "title": "千亿财金协同促内需再迎调整，贴息范围与额度双扩围",
                "publish_time": "2026-09-03T21:04:00",
                "source": "数据源2",
                "direction": "negative",
                "horizon": "中期",
            },
            {
                "news_id": 18313,
                "title": "546亿压减成效难掩堵点，零基预算改革如何深化︱财税益侃",
                "publish_time": "2026-09-08T20:55:00",
                "source": "数据源2",
                "direction": "positive",
                "horizon": "中期",
            },
            {
                "news_id": 18176,
                "title": "建设新一代通信网，国常会再做这些部署",
                "publish_time": "2026-09-04T11:31:00",
                "source": "数据源2",
                "direction": "negative",
                "horizon": "中期",
            },
            {
                "news_id": 18340,
                "title": "杰克逊霍尔首秀在即！沃什如何“走钢丝”，市场又将如何评判",
                "publish_time": "2026-09-09T15:28:00",
                "source": "数据源2",
                "direction": "positive",
                "horizon": "中期",
            },
            {
                "news_id": 18225,
                "title": "美债“定价之锚”剧烈晃动，全球科技股遭遇重估风暴",
                "publish_time": "2026-09-06T19:53:00",
                "source": "数据源2",
                "direction": "neutral",
                "horizon": "短期",
            },
            {
                "news_id": 18197,
                "title": "美财政部“救债”难解困局，全球长端利率重新定价",
                "publish_time": "2026-09-05T21:17:00",
                "source": "数据源2",
                "direction": "positive",
                "horizon": "长期",
            },
            {
                "news_id": 18174,
                "title": "一文读懂｜贝森特救市真还有“庞大工具箱”？未来哪些动向重要？",
                "publish_time": "2026-09-04T09:55:00",
                "source": "数据源2",
                "direction": "positive",
                "horizon": "中期",
            },
        ],
        "error_message": None,
        "retry_of_id": None,
        "started_at": "2026-09-09T20:00:00",
        "completed_at": "2026-09-09T20:01:00",
        "created_at": "2026-09-09T20:00:00",
        "updated_at": "2026-09-09T20:01:00",
    }


class DailyNewsSummaryCreateRequest(BaseModel):
    start_date: date
    end_date: date
    sources: list[str] = Field(default_factory=list, max_length=20)
    focus: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_range(self) -> "DailyNewsSummaryCreateRequest":
        if self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        if (self.end_date - self.start_date).days > 30:
            raise ValueError("单次最多总结 31 天新闻")
        invalid_sources = sorted(set(self.sources) - set(NEWS_SOURCES))
        if invalid_sources:
            raise ValueError(f"未知新闻来源: {', '.join(invalid_sources)}")
        self.sources = list(dict.fromkeys(self.sources))
        self.focus = " ".join(self.focus.split())
        return self


def _owner(request: Request) -> str:
    username = getattr(request.state, "username", None)
    if not username:
        raise HTTPException(status_code=401, detail="请先登录后再使用新闻总结")
    return str(username)


def _repository() -> DailyNewsSummaryRepository:
    return DailyNewsSummaryRepository.from_environment()


def _start_generation(owner_username: str, task_id: int) -> None:
    task = asyncio.create_task(
        generate_daily_news_summary(_repository(), owner_username, task_id)
    )
    task.add_done_callback(_background_tasks.discard)
    _background_tasks.add(task)


@router.get("")
def list_summaries(request: Request, limit: int = Query(default=50, ge=1, le=100)):
    items = _repository().list_tasks(_owner(request), limit)
    return {"success": True, "data": {"items": items}}


@router.get("/{task_id}")
def get_summary(request: Request, task_id: int):
    owner_username = _owner(request)
    if task_id == POLICY_DEMO_SUMMARY_ID:
        return {"success": True, "data": _policy_demo_summary(owner_username)}
    task = _repository().get_task(owner_username, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="新闻总结任务不存在")
    return {"success": True, "data": task}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_summary(request: Request, body: DailyNewsSummaryCreateRequest):
    owner_username = _owner(request)
    task = await asyncio.to_thread(
        _repository().create_task,
        owner_username,
        body.start_date,
        body.end_date,
        body.sources,
        body.focus,
    )
    _start_generation(owner_username, int(task["id"]))
    return {"success": True, "data": task}


@router.post("/{task_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_summary(request: Request, task_id: int):
    owner_username = _owner(request)
    repository = _repository()
    previous = await asyncio.to_thread(repository.get_task, owner_username, task_id)
    if not previous:
        raise HTTPException(status_code=404, detail="新闻总结任务不存在")
    if previous["status"] not in {"failed", "empty"}:
        raise HTTPException(status_code=409, detail="仅失败或无新闻的任务可以重试")
    task = await asyncio.to_thread(
        repository.create_task,
        owner_username,
        date.fromisoformat(previous["start_date"]),
        date.fromisoformat(previous["end_date"]),
        previous.get("sources_json") or [],
        str(previous.get("focus") or ""),
        task_id,
    )
    _start_generation(owner_username, int(task["id"]))
    return {"success": True, "data": task}


@router.delete("/{task_id}")
def delete_summary(request: Request, task_id: int):
    try:
        return {"success": True, "data": _repository().soft_delete_task(_owner(request), task_id)}
    except DailyNewsSummaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{task_id}/restore")
def restore_summary(request: Request, task_id: int):
    try:
        return {"success": True, "data": _repository().restore_task(_owner(request), task_id)}
    except DailyNewsSummaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{task_id}/permanently")
def permanently_delete_summary(request: Request, task_id: int):
    try:
        return {"success": True, "data": _repository().permanently_delete_task(_owner(request), task_id)}
    except DailyNewsSummaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
