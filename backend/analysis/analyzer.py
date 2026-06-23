"""
债券收益率分析模块 - 使用 kingstar API
集成收益率相似度数据和文本相似新闻数据
"""

import json
import os
from typing import Any, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import openai
from openai import AsyncOpenAI
from backend.config.config import (
    create_openai_async_http_client,
    get_default_analysis_model_name,
    get_analysis_model_info,
)
from backend.common.database import get_db_connection
from backend.common.db_operations import DBOperations
from backend.analysis.result_processor import AnalysisResultProcessor
from backend.factor.factor_management import get_factor_prompt_text

# ========== 模型配置 ==========
# 定义此分析器使用的模型短名
MODEL_NAME = get_default_analysis_model_name()

# kingstar API配置
kingstar_API_KEY = os.getenv("kingstar_API_KEY")
if not kingstar_API_KEY:
    raise ValueError("kingstar_API_KEY environment variable is not set. Please set it in your .env file.")
kingstar_BASE_URL = os.getenv("kingstar_BASE_URL")

# 创建异步客户端
async_client_kwargs = {
    "api_key": kingstar_API_KEY,
    "base_url": kingstar_BASE_URL,
}
async_http_client = create_openai_async_http_client()
if async_http_client is not None:
    async_client_kwargs["http_client"] = async_http_client
async_client = AsyncOpenAI(**async_client_kwargs)

# API调用重试装饰器：最多重试3次，指数退避（1s, 2s, 4s）
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((openai.APIError, openai.APIConnectionError, openai.RateLimitError)),
    reraise=True
)
async def async_chat_completion(**kwargs):
    """带重试的异步API调用"""
    return await async_client.chat.completions.create(**kwargs)


async def analyze_bond_yield_async(news_id: int, model_name: Optional[str] = None) -> dict:
    """
    分析新闻事件对应的关键因子

    参数:
        news_id: 新闻ID（整数）

    返回:
        分析结果字典
    """
    if not news_id:
        return {
            "direction": "neutral",
            "horizon": "短期",
            "reason": "无法获取新闻ID",
            "factors": [],
        }

    # 从数据库获取完整的新闻信息
    news_info = DBOperations.get_news_by_id(news_id)
    if not news_info:
        return {
            "direction": "neutral",
            "horizon": "短期",
            "reason": "无法获取新闻信息",
            "factors": [],
        }

    publish_date = news_info.get("publish_date")
    if not publish_date:
        return {
            "direction": "neutral",
            "horizon": "短期",
            "reason": "无法获取新闻发布日期",
            "factors": [],
        }

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
        
        response = await async_chat_completion(
            model=provider_model,
            messages=messages,
            temperature=1.0,
            timeout=600
        )

        response_text = response.choices[0].message.content

        # 检查响应是否为空
        if not response_text:
            raise ValueError("AI响应为空")

        # 确保response_text是字符串类型
        response_text = str(response_text)

        # 提取JSON部分
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()

        result = json.loads(json_str)
        return result

    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        print(f"原始响应: {response_text}")
        return {
            "direction": "neutral",
            "horizon": "短期",
            "reason": "分析失败: JSON解析错误",
            "factors": [],
        }
    except Exception as e:
        print(f"kingstar API调用失败: {e}")
        return {
            "direction": "neutral",
            "horizon": "短期",
            "reason": f"分析失败: {str(e)}",
            "factors": [],
        }


async def process_single_news_analysis(news_id: int, model_name: Optional[str] = None) -> Dict[str, Any]:
    """标准化的单条新闻分析工具函数：分析、落库并写入因子关联。"""
    with get_db_connection() as conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM news WHERE id = %s", (news_id,))
            if not cur.fetchone():
                return {"success": False, "message": "新闻不存在", "news_id": news_id}

            selected_model_name = model_name or MODEL_NAME
            provider_model = get_analysis_model_info(selected_model_name)["provider_model"]

            analysis_result = await analyze_bond_yield_async(news_id, model_name=selected_model_name)

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
            return {"success": False, "message": f"分析失败: {str(exc)}", "news_id": news_id}
