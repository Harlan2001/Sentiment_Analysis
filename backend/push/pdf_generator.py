"""
PDF 生成器 — 从数据库 forecast_report 表读取数据，通过 Jinja2 + Playwright 本地渲染生成 PDF。

数据流：
  数据库 forecast_report.prediction (JSON) → Jinja2 模板渲染 HTML → Playwright headless Chromium → PDF

依赖：playwright + Chromium（`playwright install chromium`）
"""

import json
import logging
import os
import tempfile
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.common.database import get_db_connection

logger = logging.getLogger("pdf_generator")

# 项目根目录 (backend/push/pdf_generator.py → backend → 项目根)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PDF_DIR = Path(os.getenv("PDF_OUTPUT_DIR", str(_PROJECT_ROOT / "data" / "pdf")))
FONTS_DIR = _PROJECT_ROOT / "data" / "fonts"

# Jinja2 模板环境
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


# ====================== 数据库查询 ======================


def _fetch_report_from_db(trade_date: date) -> dict:
    """
    从 forecast_report 表查询指定日期的 full_report 记录。

    Returns:
        {
            "trade_date": date,
            "model_name": str,
            "prompt_version": str,
            "created_at": datetime,
            "prediction": dict,  # 已解析的 JSON
        }

    Raises:
        ValueError: 未找到对应记录
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT trade_date, model_name, prompt_version, prediction, created_at "
            "FROM forecast_report "
            "WHERE trade_date = %s AND forecast_type = 'full_report'",
            (trade_date,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(
                f"未找到 {trade_date.isoformat()} 的预测报告（forecast_report 表中无 full_report 记录）"
            )

        prediction = row[3]
        if isinstance(prediction, str):
            prediction = json.loads(prediction)

        return {
            "trade_date": row[0] if isinstance(row[0], date) else row[0],
            "model_name": row[1],
            "prompt_version": row[2],
            "prediction": prediction,
            "created_at": row[4] if isinstance(row[4], datetime) else row[4],
        }


# ====================== HTML 渲染 ======================


def _format_dt(value) -> str:
    """将 datetime/date 格式化为 'YYYY-MM-DD HH:MM' 字符串。"""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _normalize_section(value):
    """将可能是 string 或 dict 的报告段统一为标准 dict。

    若为 string，返回 {"_raw": value}，模板直接渲染全文。
    若为 dict，原样返回，模板按子键渲染。
    """
    if value is None:
        return None
    if isinstance(value, str):
        return {"_raw": value}
    if isinstance(value, dict):
        return value
    return None


def _build_report_html(report: dict) -> str:
    """将数据库报告数据转换为完整的 HTML 字符串。"""
    pred = report["prediction"]
    trade_date = _format_dt(report["trade_date"])
    created_at = _format_dt(report["created_at"])

    # ── 报告摘要 ──
    summary = pred.get("报告摘要", "") or ""

    # ── 市场概览 / 技术分析 / 因子分析 / 策略建议 / 风险提示 ──
    # 统一处理：可能是 string(Markdown) 或 dict(结构化)，调用 _normalize_section 归一化
    market_overview = _normalize_section(pred.get("市场概览"))
    technical_analysis = _normalize_section(pred.get("技术分析"))
    factor_analysis = _normalize_section(pred.get("因子分析"))
    strategy = _normalize_section(pred.get("策略建议"))
    risk_warnings = _normalize_section(pred.get("风险提示"))

    # ── 预测结果（日/周/月 → 渲染列表） ──
    pred_results = pred.get("预测结果", {}) or {}
    predictions = []
    period_config = [
        ("日", "日度预测", "1天"),
        ("周", "周度预测", "1周"),
        ("月", "月度预测", "1月"),
    ]
    for key, title, period in period_config:
        item = pred_results.get(key)
        if item and isinstance(item, dict):
            predictions.append(
                {
                    "title": title,
                    "period": period,
                    "上涨概率": item.get("上涨概率", 0) or 0,
                    "下跌概率": item.get("下跌概率", 0) or 0,
                    "上涨基点": item.get("上涨基点", 0) or 0,
                    "下跌基点": item.get("下跌基点", 0) or 0,
                    "置信度": item.get("置信度", None),
                    "分析理由": item.get("分析理由", ""),
                    "假设条件": item.get("假设条件", []),
                }
            )

    # ── 情景分析 ──
    scenario_data = pred.get("情景分析", {}) or {}
    scenario_config = [
        ("基准", "📊", "基准情景"),
        ("牛市", "📈", "牛市情景"),
        ("熊市", "📉", "熊市情景"),
        ("黑天鹅", "🦢", "黑天鹅事件"),
    ]
    scenarios = []
    for key, icon, title in scenario_config:
        item = scenario_data.get(key)
        if item and isinstance(item, dict):
            scenarios.append(
                {
                    "key": key,
                    "icon": icon,
                    "title": title,
                    "概率": item.get("概率", 0) or 0,
                    "触发条件": item.get("触发条件", ""),
                    "描述": item.get("描述", ""),
                }
            )

    # ── 渲染模板 ──
    template = _jinja_env.get_template("report.html")

    # 构造字体目录的 file:// URL（正斜杠，适配所有平台）
    fonts_url = f"file:///{str(FONTS_DIR.resolve()).replace(os.sep, '/')}"

    html = template.render(
        fonts_dir=fonts_url,
        trade_date=trade_date,
        created_at=created_at,
        model_name=report["model_name"],
        prompt_version=report["prompt_version"],
        summary=summary,
        market_overview=market_overview,
        technical_analysis=technical_analysis,
        factor_analysis=factor_analysis,
        predictions=predictions,
        scenarios=scenarios,
        strategy=strategy,
        risk_warnings=risk_warnings,
    )
    return html


# ====================== PDF 生成入口 ======================


def generate_prediction_pdf(
    report_date: date = None,
    output_path: str = None,
) -> tuple:
    """
    从数据库读取预测报告数据，生成 PDF 保存到 data/pdf/。

    :param report_date: 报告日期，为 None 则从数据库查询最新报告日期。
    :param output_path: 可选，指定 PDF 输出路径，默认 data/pdf/{trade_date}.pdf。
    :return: (PDF文件路径, trade_date 字符串) 的元组。
    """
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 从数据库获取报告数据
    if report_date is None:
        raise ValueError("report_date 不能为 None，请指定报告日期")

    logger.info("开始生成预测报告 PDF（DB 模式）")
    logger.info("  报告日期 : %s", report_date)
    logger.info("  输出目录 : %s", PDF_DIR)

    report = _fetch_report_from_db(report_date)
    trade_date_str = (
        report["trade_date"].isoformat()
        if isinstance(report["trade_date"], date)
        else str(report["trade_date"])
    )

    if output_path is None:
        output_path = str(PDF_DIR / f"{trade_date_str}.pdf")

    logger.info(
        "  模型 : %s  |  版本 : %s", report["model_name"], report["prompt_version"]
    )

    # 2. 构建 HTML
    html = _build_report_html(report)
    logger.info("HTML 已生成 (%.1f KB)", len(html.encode("utf-8")) / 1024)

    # 3. Playwright headless Chromium 渲染 HTML → PDF
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "PDF 生成不可用：playwright 未安装。"
            "请执行 `pip install playwright && playwright install chromium`"
        ) from e

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 写 HTML 到临时文件，再用 file:// URL 加载。
            # page.set_content() 使用 about:blank 源，无法访问系统字体；
            # file:// 协议下 Chromium 可以正常读取 @font-face 引用的字体文件。
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", encoding="utf-8", delete=False
            ) as tmp:
                tmp.write(html)
                tmp_path = tmp.name

            try:
                page.goto(
                    f"file:///{tmp_path.replace(os.sep, '/')}", wait_until="networkidle"
                )
                page.pdf(
                    path=output_path,
                    format="A4",
                    margin={
                        "top": "15mm",
                        "bottom": "15mm",
                        "left": "12mm",
                        "right": "12mm",
                    },
                    print_background=True,
                )
            finally:
                os.unlink(tmp_path)

            browser.close()

        file_size_kb = Path(output_path).stat().st_size / 1024
        logger.info("PDF 生成成功: %s (%.1f KB)", output_path, file_size_kb)

        return str(output_path), trade_date_str

    except Exception as e:
        logger.exception("PDF 生成失败: %s", e)
        raise RuntimeError(f"PDF 生成失败: {e}") from e
