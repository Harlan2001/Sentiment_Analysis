"""
债券收益率分析模块 - 使用 kingstar API
集成收益率相似度数据和文本相似新闻数据
"""

import json
import logging
import time
from typing import Any, Dict, Optional

from backend.analysis.result_processor import AnalysisResultProcessor
from backend.common.database import get_db_connection
from backend.common.db_operations import DBOperations
from backend.common.llm_call import async_chat_completion
from backend.common.llm_json import extract_json_string
from backend.common.llm_logger import log_llm_usage
from backend.config.config import (
    get_analysis_model_info,
    get_default_analysis_model_name,
    get_llm_api_key,
)
from backend.factor.factor_management import get_factor_prompt_text

logger = logging.getLogger(__name__)


class AnalysisError(RuntimeError):
    """分析失败（LLM 输出无效 / API 调用重试耗尽），区别于信息不足时返回的中性结果。"""


def fallback_analysis_result(reason: str) -> dict:
    """构造“无法分析”的中性兜底结果（信息缺失场景，不视为失败）。"""
    return {"direction": "neutral", "horizon": "短期", "reason": reason, "factors": []}


# ========== 模型配置 ==========
# 定义此分析器使用的模型短名
MODEL_NAME = get_default_analysis_model_name()

# LLM API 配置（LLM_API_KEY / LLM_BASE_URL）
llm_api_key = get_llm_api_key()
if not llm_api_key:
    raise ValueError(
        "LLM_API_KEY environment variable is not set. Please set it in your .env file."
    )


async def analyze_bond_yield_async(
    news_id: int, model_name: Optional[str] = None
) -> dict:
    """
    分析新闻事件对应的关键因子

    参数:
        news_id: 新闻ID（整数）

    返回:
        分析结果字典
    """
    if not news_id:
        raise AnalysisError("无法获取新闻ID")

    # 从数据库获取完整的新闻信息（DB 瞬时错误直接向上抛出，交由调用方重试）
    news_info = DBOperations.get_news_by_id(news_id)
    if not news_info:
        raise AnalysisError(f"新闻不存在: {news_id}")

    publish_date = news_info.get("publish_date")
    if not publish_date:
        return fallback_analysis_result("无法获取新闻发布日期")

    selected_model_name = model_name or MODEL_NAME
    provider_model = get_analysis_model_info(selected_model_name)["provider_model"]

    # 构建完整prompt
    prompt = f"""
你是中国宏观与债券市场分析专家，基于新闻事件判断对【中国国债】的影响。

【核心任务】
1. 提取新闻事件对应的相关因子
2. 构建逻辑推导链

---

【当前新闻】
标题：{news_info.get("title", "")}
内容：{news_info.get("content", "")}
发布日期：{publish_date}

---

【输出要求】
1. 仅输出有效JSON,无任何解释性文本
2. 信息不足时direction设为"neutral"
3. 禁止提供投资建议

---

## 因子规则
### 复用优先
- 必须优先从【预定义因子列表】选择，禁止创建同义因子
- 仅当以下情况允许创建新因子：
1. 现有因子无法表达该事件的“经济传导机制”
2. 该事件具有可复用性（未来可能再次出现）
3. 不是一次性描述（如具体公司/地点/日期）
- 禁止创建：
1. 具体政策名称(如“XX会议决定”)
2. 具体国家+事件拼接
3. 单次新闻标签

### 因子字段规范
- code: 语义化大写英文缩写,禁止NEW_FACTOR_*格式
- name: 中文名称
- category:
    POLICY(政策驱动)
    MACRO(基本面驱动)
    LIQUIDITY(流动性驱动)
    RISK(风险/避险驱动)
    SENTIMENT(市场情绪驱动)
    INDUSTRY(行业/结构性驱动)
- type: quantitative(可量化)|conceptual(结构、概念类)
- direction: positive (债券利多 / 收益率下行)| negative (债券利空 / 收益率上行)| neutral
- logic_impact: 因子作用机制说明,logic_impact 必须显式包含三个部分：
1. 触发事件（如：降息 / 战争 / 数据公布）
2. 中间变量（如：流动性 / 风险偏好 / 通胀预期）
3. 利率方向
4. 可以包含多个触发事件、多个中间变量
- is_new_discovery: 是否为新发现因子

---

## 总输出字段规范以及冲突处理
- direction: positive (债券利多 / 收益率下行)| negative (债券利空 / 收益率上行)| neutral
- horizon: 短期:事件驱动(1周-1月),中期：政策/周期(1-6月),长期:结构性(6月以上)
- reason: 逻辑推导链,必须包含：
1. 新闻中的“具体触发点”
2. 对应的经济变量变化
3. 如何传导到利率
- factors: 相关因子列表，因子字段规范见上
- 当多个因子方向冲突时：
1. 以“主导逻辑”为准确定 direction 和 horizon
2. reason中必须说明冲突及主导因素

---
## 输出格式
{{
  "direction": "positive|negative|neutral",
  "horizon": "短期|中期|长期",
  "reason": "",
  "factors": [{{
    "code": "", "name": "", "category": "", "is_new_discovery": false, "type": "", "direction": "", "logic_impact": ""
  }}]
}}

【预定义因子列表】
{get_factor_prompt_text()}
"""

    response_text = ""
    try:
        messages = [{"role": "user", "content": prompt}]

        t0 = time.monotonic()
        response = await async_chat_completion(
            model=provider_model, messages=messages, temperature=1.0, timeout=600
        )
        elapsed = time.monotonic() - t0
        logger.debug(
            "kingstar API 调用完成, elapsed=%.2fs, model=%s, news_id=%d",
            elapsed,
            provider_model,
            news_id,
        )

        response_text = response.choices[0].message.content

        # 检查响应是否为空
        if not response_text:
            raise ValueError("AI响应为空")

        # 提取并清理 JSON 文本（fenced code 提取 + 尾随逗号清洗，见 common.llm_json）
        json_str = extract_json_string(response_text)
        if not json_str:
            raise ValueError("AI响应未包含有效JSON结构")

        result = json.loads(json_str)

        # 记录 Token 消耗（不影响分析结果）
        try:
            usage = response.usage
            log_llm_usage(
                call_source="analysis",
                model_name=selected_model_name,
                provider_model=provider_model,
                prompt_tokens=(
                    usage.prompt_tokens if usage and usage.prompt_tokens else 0
                ),
                completion_tokens=(
                    usage.completion_tokens if usage and usage.completion_tokens else 0
                ),
                total_tokens=usage.total_tokens if usage and usage.total_tokens else 0,
                success=True,
                latency_ms=int(elapsed * 1000),
            )
        except Exception:
            logger.exception("Token 日志记录失败（不影响分析）")

        return result

    except json.JSONDecodeError as e:
        logger.warning("JSON解析失败: %s", e)
        logger.debug("原始响应: %s", response_text[:500])
        raise AnalysisError("LLM JSON解析错误") from e
    except AnalysisError:
        raise
    except Exception as e:
        logger.error("kingstar API调用失败: %s", e, exc_info=True)
        raise AnalysisError("LLM API调用失败") from e


async def process_single_news_analysis(
    news_id: int, model_name: Optional[str] = None
) -> Dict[str, Any]:
    """标准化的单条新闻分析工具函数：分析、落库并写入因子关联。"""
    with get_db_connection() as conn:
        try:
            selected_model_name = model_name or MODEL_NAME
            provider_model = get_analysis_model_info(selected_model_name)[
                "provider_model"
            ]

            # 新闻存在性/发布日期的校验在 analyze_bond_yield_async 内部完成
            analysis_result = await analyze_bond_yield_async(
                news_id, model_name=selected_model_name
            )

            DBOperations.save_analysis_result(
                news_id=news_id,
                analysis_result=analysis_result,
                model=selected_model_name,
                conn=conn,
            )

            result_processor = AnalysisResultProcessor(model_name=selected_model_name)
            result_processor.process_analysis_result(
                news_id=news_id,
                analysis_result=analysis_result,
                conn=conn,
            )

            conn.commit()
            return {
                "success": True,
                "message": "分析完成",
                "news_id": news_id,
                "model_name": selected_model_name,
                "provider_model": provider_model,
                "analysis": analysis_result,
            }
        except Exception as exc:
            conn.rollback()
            return {
                "success": False,
                "message": f"分析失败: {str(exc)}",
                "news_id": news_id,
            }
