"""
生成的预测报告应填满整个板块，包含详尽的分析内容。
"""

import re
import json
import logging
import os
import argparse
from typing import Any, Dict, List, Optional
from datetime import datetime
from openai import OpenAI
from backend.config.config import (
    MYSQL_CONFIG,
    create_openai_http_client,
    get_analysis_model_info,
    get_default_analysis_model_name,
)
from backend.task_logging import start_task_run, finish_task_run, add_task_event
from backend.common.database import init_database, DatabaseConfig, get_db_connection
from backend.common.db_operations import DBOperations

from dotenv import load_dotenv
load_dotenv()

# 日志配置
logger = logging.getLogger(__name__)

# 常量配置
MODEL_NAME = get_default_analysis_model_name()
MODEL_INFO = get_analysis_model_info(MODEL_NAME)
MODEL_PROVIDER_MODEL = MODEL_INFO.get("provider_model", MODEL_NAME) if isinstance(MODEL_INFO, dict) else str(MODEL_INFO)
PROMPT_VERSION = "v2.0"  # 升级版本号
KINGSTAR_API_KEY = os.getenv("kingstar_API_KEY")
KINGSTAR_BASE_URL = os.getenv("kingstar_BASE_URL")


def _truncate_text(text: str, limit: int) -> str:
    """统一文本截断逻辑，避免重复处理。"""
    if not text:
        return ""
    return f"{text[:limit]}..." if len(text) > limit else text


def _extract_json_content(content: str) -> str:
    """提取 fenced code block 中的 JSON 文本。"""
    if not content:
        return ""
    
    #  Step 1: 移除代码块标记
    cleaned = re.sub(r'```json|```', '', content).strip()
    
    #  Step 2: 提取第一个 { ... } 结构（无视前后废话）
    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if json_match:
        return json_match.group().strip()
    
    # 没找到 JSON 结构
    return ""

def construct_enhanced_prompt(
    news_texts: List[Dict[str, Any]], 
    yield_data: Dict[str, List[Dict[str, float]]],
    market_summary: Dict[str, Any],
    report_date: str
) -> str:
    """
    构建增强版大模型提示词，要求生成详尽的市场预测报告。

    参数:
        news_texts: 新闻分析数据列表。
        yield_data: 收益率数据字典。
        market_summary: 市场摘要统计。
        report_date: 报告日期。

    返回:
        格式化后的提示词文本。
    """
    # 新闻部分 - 包含详细的分析信息
    news_section = "\n\n".join([
        f"【新闻{i+1}】{news['title']}\n"
        f"方向: {news['direction']}\n"
        f"时间范围: {news['horizon']}\n"
        f"逻辑: {_truncate_text(news['reason'], 200)}\n"
        f"内容摘要: {_truncate_text(news['content'], 150)}"
        for i, news in enumerate(news_texts[:10])  # 最多取10条新闻
    ])

    # 收益率部分
    yield_section = ""
    for period, points in yield_data.items():
        if points:
            latest = points[-1]
            if len(points) >= 2:
                prev = points[-2]
                change = latest['value'] - prev['value']
                change_str = f"+{change:.2f}" if change > 0 else f"{change:.2f}"
                yield_section += f"{period}: {latest['value']}% (日变动: {change_str}bp, 日期: {latest['date']})\n"
            else:
                yield_section += f"{period}: {latest['value']}% (日期: {latest['date']})\n"

    # 市场摘要部分
    summary_section = ""
    for period, data in market_summary.items():
        summary_section += (
            f"{period}国债: 最新{data['latest']}% | 5日变动{data['change']:+.2f}bp | "
            f"趋势: {data['trend']} | 波动率: {data['volatility']:.2f}\n"
        )

    prompt = f"""# 中国债券市场预测分析报告生成任务

作为专业的债券市场分析师，请基于以下详尽的市场数据，生成一份全面的市场预测报告。

## 分析日期
{report_date}

## 近期市场概况（近5个交易日）
{summary_section if summary_section else "暂无市场摘要数据"}

## 新闻事件详细分析
{news_section if news_section else "暂无新闻数据"}

## 收益率详细数据
{yield_section if yield_section else "暂无收益率数据"}

---

## 请生成以下详尽的预测报告内容：

### 1. 市场综述（market_overview）
- 当前市场总体走势和情绪
- 主要驱动因素概述
- 关键风险点识别
- 与前期的对比分析

### 2. 技术面分析（technical_analysis）
- 收益率曲线形态分析（陡峭化/平坦化趋势）
- 关键支撑/阻力位
- 动量指标判断
- 历史分位数位置

### 3. 基本面因子分析（factor_analysis）
- 宏观因子影响（CPI、PPI、PMI、社融等）
- 政策因子影响（货币政策、财政政策、监管政策）
- 资金面和流动性分析
- 外部环境影响（美联储、汇率、大宗商品）

### 4. 详细预测（预测结果）
对每个时间周期（日/周/月）提供：
- 上涨概率和下跌概率（精确到小数点后2位）
- 预期变动幅度（上涨/下跌基点数）
- 预测置信度（0-1之间）
- 核心假设条件

### 5. 情景分析（情景分析）
- 基准情景（概率最大）
- 乐观情景及触发条件
- 悲观情景及触发条件
- 黑天鹅风险提示

### 6. 交易策略建议（strategy_recommendations）
- 利率债策略
- 信用债策略
- 久期管理建议
- 杠杆和套息策略

### 7. 风险提示（risk_warnings）
- 主要风险因素清单
- 需关注的关键数据和事件
- 预警指标阈值

---

**输出要求（必须严格遵守）：**
1. **只输出纯 JSON 格式**，**绝对不要**输出任何解释、前言、总结、 markdown、代码块、说明文字
2. 不要写 ```json，不要写```，不要写任何多余内容
3. 所有分析内容必须详尽、充实、有逻辑
4. 严格按照下面的 JSON 结构输出，字段一个都不能少
5. 所有键名必须使用中文

请以JSON格式返回完整报告，所有键名必须使用中文，格式如下：
{{
  "市场概览": {{
    "概述": "详细的市场综述...",
    "市场情绪": "看涨/看跌/中性",
    "主要驱动因素": ["因素1", "因素2", ...],
    "风险点": ["风险1", "风险2", ...]
  }},
  "技术分析": {{
    "曲线形态": "收益率曲线形态描述",
    "支撑压力": "关键支撑阻力位分析",
    "动能分析": "动量指标判断",
    "分位数": "历史分位数位置"
  }},
  "因子分析": {{
    "宏观因子": "宏观经济因子影响分析...",
    "政策因子": "政策因子影响分析...",
    "流动性分析": "流动性和资金面分析...",
    "外部因素": "外部环境和国际因素..."
  }},
  "预测结果": {{
    "日": {{
      "上涨概率": 0.55,
      "下跌概率": 0.45,
      "上涨基点": 3.5,
      "下跌基点": -2.5,
      "置信度": 0.72,
      "假设条件": ["假设1", "假设2"]
    }},
    "周": {{
      "上涨概率": 0.60,
      "下跌概率": 0.40,
      "上涨基点": 8.2,
      "下跌基点": -5.8,
      "置信度": 0.68,
      "假设条件": ["假设1", "假设2"]
    }},
    "月": {{
      "上涨概率": 0.65,
      "下跌概率": 0.35,
      "上涨基点": 15.5,
      "下跌基点": -10.2,
      "置信度": 0.62,
      "假设条件": ["假设1", "假设2"]
    }}
  }},
  "情景分析": {{
    "基准": {{"概率": 0.50, "描述": "基准情景描述", "触发条件": "触发条件"}},
    "牛市": {{"概率": 0.25, "描述": "乐观情景描述", "触发条件": "触发条件"}},
    "熊市": {{"概率": 0.20, "描述": "悲观情景描述", "触发条件": "触发条件"}},
    "黑天鹅": {{"概率": 0.05, "描述": "黑天鹅风险描述"}}
  }},
  "策略建议": {{
    "利率债": "利率债策略建议...",
    "信用债": "信用债策略建议...",
    "久期管理": "久期管理建议...",
    "杠杆策略": "杠杆和套息策略..."
  }},
  "风险提示": {{
    "主要风险": ["主要风险1", "主要风险2", "主要风险3"],
    "重点事件": ["关注事件1", "关注事件2"],
    "关键指标": ["预警指标1", "预警指标2"]
  }},
    "生成时间": "{report_date}",
  "报告摘要": "本报告核心结论摘要..."
}}
"""
    return prompt.strip()


def call_llm(prompt: str) -> str:
    """
    调用大模型生成预测结果。

    Args:
        prompt: 输入提示词。

    Returns:
        LLM 返回的 JSON 字符串。
    """
    try:
        client_kwargs: Dict[str, Any] = {
            "api_key": KINGSTAR_API_KEY,
            "base_url": KINGSTAR_BASE_URL,
        }
        http_client = create_openai_http_client()
        if http_client is not None:
            client_kwargs["http_client"] = http_client
        client = OpenAI(**client_kwargs)
        
        response = client.chat.completions.create(
            model=MODEL_PROVIDER_MODEL,
            messages=[
                {"role": "system", "content": "你是专业的中国债券市场分析师，擅长宏观经济分析、货币政策解读和技术面分析。请生成详尽专业的市场预测报告。"},
                {"role": "user", "content": prompt}
            ],
            temperature=1.0,
            max_tokens=4000,  # 增加令牌数以获取更详细的回复
        )
        
        content = response.choices[0].message.content or ""
        return _extract_json_content(content)
        
    except Exception as e:
        logger.error("大模型调用失败: %s", e)
        return ""


def save_enhanced_forecast(
    report_date: str,
    model_name: str,
    prompt_version: str,
    forecast_data: Dict,
) -> bool:
    """
    将增强预测结果保存到数据库。

    参数:
        report_date: 基于 news.pub_time 的报告日期。
        model_name: 模型名称。
        prompt_version: 提示词版本。
        forecast_data: 完整预测结果字典。

    返回:
        保存成功返回 True。
    """
    with get_db_connection() as conn:
        try:
            cur = conn.cursor()
            
            # 检查是否已存在该日期的完整报告
            cur.execute(
                """
                SELECT id FROM forecast_report
                WHERE trade_date = %s AND forecast_type = 'full_report'
            """,
                (report_date,),
            )
            
            if cur.fetchone():
                logger.info("%s 的完整报告已存在，执行更新", report_date)
                # 更新已有记录
                cur.execute(
                    """
                    UPDATE forecast_report
                    SET prediction = %s, model_name = %s, prompt_version = %s, updated_at = NOW()
                    WHERE trade_date = %s AND forecast_type = 'full_report'
                """,
                    (
                        json.dumps(forecast_data, ensure_ascii=False),
                        model_name,
                        prompt_version,
                        report_date,
                    ),
                )
            else:
                # 插入新记录 - 保存完整报告
                cur.execute(
                    """
                    INSERT INTO forecast_report
                    (trade_date, model_name, prompt_version, forecast_type, prediction, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                    (
                        report_date,
                        model_name,
                        prompt_version,
                        "full_report",
                        json.dumps(forecast_data, ensure_ascii=False),
                    ),
                )
            
            logger.info("%s 的增强预测报告保存成功", report_date)
            return True
            
        except Exception as e:
            logger.error("保存预测报告失败: %s", e)
            return False


def generate_for_news_date(report_date: str) -> bool:
    """按新闻发布日期生成并保存单日预测报告。"""
    logger.info("开始生成 %s 的报告", report_date)

    # 获取新闻与分析数据
    news_data = DBOperations.get_news_analysis_by_date(report_date)
    if not news_data:
        logger.warning("%s 无新闻数据，跳过", report_date)
        return False

    yield_bundle = DBOperations.get_yield_data_and_market_summary(
        end_date=report_date,
        lookback_days=30,
        summary_days=5,
    )
    yield_data = yield_bundle.get("yield_data", {})
    market_summary = yield_bundle.get("market_summary", {})

    # 构造提示词
    prompt = construct_enhanced_prompt(news_data, yield_data, market_summary, report_date)

    # 调用大模型
    response = call_llm(prompt)
    if not response:
        logger.error("%s 的大模型返回为空", report_date)
        return False

    try:
        forecast_data = json.loads(response)
    except json.JSONDecodeError as e:
        logger.error(f"{report_date} JSON 解析失败: {str(e)}")
        logger.error(f"{report_date} 模型最终返回内容: {response}")  # 必加，方便调试
        return False

    forecast_data.setdefault("生成时间", datetime.now().strftime("%Y-%m-%d"))
    
    if not forecast_data:
        logger.error("%s 的大模型返回校验失败", report_date)
        return False

    # 保存报告
    success = save_enhanced_forecast(
        report_date,
        MODEL_NAME,
        PROMPT_VERSION,
        forecast_data,
    )

    if success:
        logger.info("%s 的增强预测报告已保存", report_date)
    else:
        logger.error("%s 的增强预测报告保存失败", report_date)

    return success


def _parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="按新闻发布日期生成预测报告")
    parser.add_argument(
        "--start-date",
        help="起始日期，格式 YYYY-MM-DD（闭区间）",
    )
    parser.add_argument(
        "--end-date",
        help="结束日期，格式 YYYY-MM-DD（闭区间）",
    )
    return parser.parse_args()


def _validate_date_str(date_str: Optional[str], field_name: str) -> None:
    """校验日期参数格式。"""
    if not date_str:
        return
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} 格式错误，应为 YYYY-MM-DD: {date_str}") from exc


def main() -> None:
    args = _parse_args()
    _validate_date_str(args.start_date, "start-date")
    _validate_date_str(args.end_date, "end-date")
    if args.start_date and args.end_date and args.start_date > args.end_date:
        raise ValueError("start-date 不能晚于 end-date")

    db_config = DatabaseConfig(**MYSQL_CONFIG)
    init_database(db_config)
    logger.info("数据库初始化成功")

    if args.start_date or args.end_date:
        news_dates = DBOperations.get_news_pub_dates_in_range(args.start_date, args.end_date)
    else:
        news_dates = DBOperations.get_news_pub_dates()

    task_payload = {
        "date_source": "news.pub_time",
        "news_dates": news_dates,
        "start_date": args.start_date,
        "end_date": args.end_date,
    }

    with get_db_connection() as task_conn:
        task_run_id = start_task_run(
            task_conn,
            task_name="generate_forecast_report",
            task_type="news_pub_time",
            payload=task_payload,
        )
        task_conn.commit()
    
        try:
            if not news_dates:
                logger.error("未找到新闻发布日期")
                finish_task_run(
                    task_conn,
                    task_run_id,
                    status="failed",
                    error_message="未找到新闻发布日期",
                )
                task_conn.commit()
                return

            logger.info("开始基于 %d 个新闻日期生成报告", len(news_dates))

            success_count = 0
            for report_date in news_dates:
                ok = generate_for_news_date(report_date)
                add_task_event(
                    task_conn,
                    task_run_id=task_run_id,
                    event_type="news_date_generated",
                    news_id=None,
                    status="success" if ok else "failed",
                    message=f"generate report for {report_date}",
                    payload={"report_date": report_date, "success": ok},
                )
                task_conn.commit()
                if ok:
                    success_count += 1

            logger.info(
                "新闻日期报告生成完成: 成功=%d, 失败=%d",
                success_count,
                len(news_dates) - success_count,
            )
            finish_task_run(
                task_conn,
                task_run_id,
                status="completed" if success_count == len(news_dates) else "completed_with_errors",
                total_count=len(news_dates),
                processed_count=success_count,
                result={"news_dates": news_dates},
            )
            task_conn.commit()
        except Exception as e:
            logger.exception("报告生成流程失败")
            finish_task_run(
                task_conn,
                task_run_id,
                status="failed",
                error_message=str(e),
            )
            task_conn.commit()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
