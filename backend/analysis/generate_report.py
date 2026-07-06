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
PROMPT_VERSION = "v2.2"  # v2.2: 多日新闻范围 + 单条新闻日期标注 + 去重
KINGSTAR_API_KEY = os.getenv("kingstar_API_KEY")
KINGSTAR_BASE_URL = os.getenv("kingstar_BASE_URL")

# 报告生成时向前回溯的新闻天数（含 report_date 当天）
NEWS_LOOKBACK_DAYS = 3
# 送入 LLM 的最大新闻条数
MAX_NEWS_IN_PROMPT = 20


def _truncate_text(text: str, limit: int) -> str:
    """统一文本截断逻辑，避免重复处理。"""
    if not text:
        return ""
    return f"{text[:limit]}..." if len(text) > limit else text


def _sanitize_json(text: str) -> str:
    """清理 LLM 返回文本中常见的 JSON 不合规问题。"""
    if not text:
        return ""
    # 移除尾随逗号：逗号后紧跟 ] 或 }（中间允许空白）
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _extract_json_content(content: str) -> str:
    """提取 fenced code block 中的 JSON 文本。"""
    if not content:
        return ""

    #  Step 1: 移除代码块标记
    cleaned = re.sub(r'```json|```', '', content).strip()

    #  Step 2: 提取第一个 { ... } 结构（无视前后废话）
    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if json_match:
        return _sanitize_json(json_match.group().strip())

    # 没找到 JSON 结构
    return ""


def construct_enhanced_prompt(
    news_texts: List[Dict[str, Any]],
    yield_data: Dict[str, List[Dict[str, float]]],
    market_summary: Dict[str, Any],
    report_date: str,
    news_start_date: str = "",
    news_end_date: str = "",
) -> str:
    """
    构建增强版大模型提示词，根据数据可用性动态调整报告要求。

    参数:
        news_texts: 新闻分析数据列表。
        yield_data: 收益率数据字典。
        market_summary: 市场摘要统计。
        report_date: 报告日期。

    返回:
        格式化后的提示词文本。
    """
    # 新闻部分 - 包含详细的分析信息，标注每条新闻的日期
    news_date_label = (
        f"{news_start_date} 至 {news_end_date}"
        if news_start_date and news_end_date
        else report_date
    )
    news_section = "\n\n".join([
        f"【新闻{i+1}】[{news.get('pub_date', report_date)}] {news['title']}\n"
        f"方向: {news['direction']}\n"
        f"时间范围: {news['horizon']}\n"
        f"逻辑: {_truncate_text(news['reason'], 200)}\n"
        for i, news in enumerate(news_texts[:MAX_NEWS_IN_PROMPT])
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

    # --- 数据可用性判断 ---
    has_yield_data = bool(yield_section)
    has_market_summary = bool(summary_section)
    has_news = bool(news_section)

    # --- 根据数据可用性生成差异化的报告指令 ---
    if has_market_summary and has_yield_data:
        data_context = "以下提供了完整的近期市场概况、收益率详细数据和新闻事件分析。请基于这些实际数据生成全面的分析报告。"
        technical_requirement = """### 2. 技术分析
基于上方提供的实际收益率数据，分析收益率曲线形态（陡峭化/平坦化趋势）、关键支撑阻力位、动量指标判断、历史分位数位置。必须引用具体数据。"""
        factor_requirement = """### 3. 因子分析
结合新闻事件和实际市场数据，综合分析宏观因子（CPI、PPI、PMI、社融等）、政策因子（货币/财政/监管）、资金面流动性状况，以及外部环境的影响。"""
        output_instruction = "分析内容需详尽充实，但每个章节用一段完整的文字表述即可，不要拆分为多个子字段"
    elif has_news:
        data_context = (
            "⚠️ 注意：本次分析缺少收益率数据和市场摘要（可能为非交易日），"
            "以下仅提供了新闻事件分析数据。请基于新闻事件进行定性分析。"
        )
        technical_requirement = """### 2. 技术分析
由于缺少实际收益率数据，本节应简要说明「因本日为节假日/非交易日，无行情数据，技术分析无法进行」，不得超过3句话。"""
        factor_requirement = """### 3. 因子分析
基于上方提供的新闻事件，分析其中涉及的宏观、政策、资金面、外部环境因子的潜在影响。仅分析新闻中实际提及的因子，不得自行引入新闻未涉及的因子或数据。"""
        output_instruction = "数据缺失的章节简短诚实说明即可，不要编造填充；有数据的章节可正常展开分析"
    else:
        data_context = (
            "⚠️ 注意：本次分析无市场数据、无收益率数据、无新闻数据，无法进行有效分析。"
        )
        technical_requirement = """### 2. 技术分析
因无数据，本节填写「无可用数据，分析跳过」。"""
        factor_requirement = """### 3. 因子分析
因无数据，本节填写「无可用数据，分析跳过」。"""
        output_instruction = "数据缺失的章节简短诚实说明即可，不要编造填充；有数据的章节可正常展开分析"

    prompt = f"""# 中国债券市场预测分析报告生成任务

作为专业的债券市场分析师，请基于以下市场数据，生成一份市场预测报告。

{data_context}

## 分析日期
{report_date}

## 近期市场概况（近5个交易日）
{summary_section if summary_section else "（无数据 — 可能为非交易日或数据未更新）"}

## 新闻事件详细分析（{news_date_label}，共 {len(news_texts[:MAX_NEWS_IN_PROMPT])} 条）
{news_section if news_section else "（无新闻数据）"}

## 收益率详细数据
{yield_section if yield_section else "（无数据 — 可能为非交易日或数据未更新）"}

---

## 报告内容要求

### 1. 市场概览
基于上述数据综合分析当前市场总体走势、市场情绪、主要驱动因素、关键风险点。{"" if has_market_summary else "如无行情数据，可简要说明市场处于休市状态，聚焦新闻事件中的情绪信号。"}

{technical_requirement}

{factor_requirement}

### 4. 预测结果
对日/周/月三个周期，分别给出上涨概率和下跌概率（精确到小数点后2位）、预期变动基点数、置信度（0-1）、核心假设条件。{"若无行情数据，所有预测的置信度不得超过0.55，并在假设条件中明确标注「基于非交易日新闻情绪推断，无实际行情数据支撑」。严禁编造任何具体数值。" if not has_yield_data else ""}

### 5. 情景分析
分析基准情景、牛市情景、熊市情景及黑天鹅风险，各含发生概率、情景描述和触发条件。

### 6. 策略建议
给出利率债策略、信用债策略、久期管理、杠杆和套息策略的综合建议。

### 7. 风险提示
列出主要风险因素、需关注的关键数据和事件、预警指标阈值。

---

## ⚠️ 严禁事项（必须遵守）
1. **严禁编造数据**：不得使用「合理假设」「假设前期」「预计在XX区间」「假设XX在XX附近」「基于XX合理推测」等措辞编造具体的收益率数值、指数点位、宏观数据。没有数据就如实说明「无法获取」，绝不自创数字。
2. **严禁空洞堆砌**：当某个章节确实缺少分析素材时，用1-3句话简要说明原因即可，不要用大量「可能」「或许」「大概率」的猜测来填充篇幅。
3. **区分事实与推测**：基于新闻事实的推断可以写，但必须标注「据XX新闻推断」；没有信息来源的判断不得出现。
4. **违规示例**（绝对禁止）：❌「合理假设10年期国债收益率在2.30%-2.40%区间」❌「假设前期震荡平台为XX」❌「预计CPI同比温和回升至1.0%-1.5%」——这些数字没有数据来源，纯属编造。

---

**输出要求：**
1. 只输出纯 JSON，不要任何解释、markdown 标记、代码块或说明文字
2. 所有键名必须使用中文
3. {output_instruction}

请严格按照以下 JSON 结构输出：
{{
  "市场概览": "详细的市场综述文本...",
  "技术分析": "详细的技术分析文本...",
  "因子分析": "详细的因子分析文本...",
  "预测结果": {{
    "日": {{"上涨概率": 0.55, "下跌概率": 0.45, "上涨基点": 3.5, "下跌基点": -2.5, "置信度": 0.72, "假设条件": ["假设1", "假设2"]}},
    "周": {{"上涨概率": 0.60, "下跌概率": 0.40, "上涨基点": 8.2, "下跌基点": -5.8, "置信度": 0.68, "假设条件": ["假设1", "假设2"]}},
    "月": {{"上涨概率": 0.65, "下跌概率": 0.35, "上涨基点": 15.5, "下跌基点": -10.2, "置信度": 0.62, "假设条件": ["假设1", "假设2"]}}
  }},
  "情景分析": {{
    "基准": {{"概率": 0.50, "描述": "基准情景描述", "触发条件": "触发条件"}},
    "牛市": {{"概率": 0.25, "描述": "乐观情景描述", "触发条件": "触发条件"}},
    "熊市": {{"概率": 0.20, "描述": "悲观情景描述", "触发条件": "触发条件"}},
    "黑天鹅": {{"概率": 0.05, "描述": "黑天鹅风险描述"}}
  }},
  "策略建议": "详细的策略建议文本...",
  "风险提示": "详细的风险提示文本...",
  "报告摘要": "本报告核心结论摘要...",
  "生成时间": "{report_date}"
}}"""
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
                {"role": "system", "content": "你是专业的中国债券市场分析师，擅长宏观经济分析、货币政策解读和技术面分析。你必须严格遵守数据事实：有数据就深入分析，无数据就诚实说明，绝不编造任何数值或假设。"},
                {"role": "user", "content": prompt}
            ],
            temperature=1.0,
            max_tokens=8000,
        )

        choice = response.choices[0]
        if choice.finish_reason == "length":
            logger.warning("大模型返回被截断（finish_reason=length），max_tokens 可能不足")

        content = choice.message.content or ""
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

            conn.commit()
            logger.info("%s 的增强预测报告保存成功", report_date)
            return True

        except Exception as e:
            logger.error("保存预测报告失败: %s", e)
            return False


def generate_for_news_date(report_date: str) -> bool:
    """按新闻发布日期生成并保存单日预测报告。

    新闻范围向前回溯 NEWS_LOOKBACK_DAYS 天，避免单天新闻量过少或质量过低。
    """
    from datetime import timedelta

    logger.info("开始生成 %s 的报告（新闻回溯 %d 天）", report_date, NEWS_LOOKBACK_DAYS)

    # 计算新闻查询范围
    end_dt = datetime.strptime(report_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=NEWS_LOOKBACK_DAYS)
    news_start_date = start_dt.strftime("%Y-%m-%d")
    news_end_date = report_date

    # 获取多日新闻与分析数据（自动去重，取最高优先级模型）
    news_data = DBOperations.get_news_analysis_by_date_range(
        start_date=news_start_date,
        end_date=news_end_date,
        limit=MAX_NEWS_IN_PROMPT,
    )
    if not news_data:
        logger.warning("%s（范围 %s~%s）无新闻数据，跳过", report_date, news_start_date, news_end_date)
        return False

    logger.info("%s 获取到 %d 条新闻（%s~%s）", report_date, len(news_data), news_start_date, news_end_date)

    yield_bundle = DBOperations.get_yield_data_and_market_summary(
        end_date=report_date,
        lookback_days=30,
        summary_days=5,
    )
    yield_data = yield_bundle.get("yield_data", {})
    market_summary = yield_bundle.get("market_summary", {})

    # 构造提示词
    prompt = construct_enhanced_prompt(
        news_data, yield_data, market_summary, report_date,
        news_start_date=news_start_date,
        news_end_date=news_end_date,
    )

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
