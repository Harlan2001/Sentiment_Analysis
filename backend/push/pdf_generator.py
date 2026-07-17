"""
PDF 生成器 — 从数据库 forecast_report 表读取数据，通过 Jinja2 + Playwright 本地渲染生成 PDF。

数据流：
  数据库 forecast_report.prediction (JSON) → Jinja2 模板渲染 HTML → Playwright page.set_content() → page.pdf()
"""
import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from backend.common.database import get_db_connection

logger = logging.getLogger("pdf_generator")

# 项目根目录 (backend/push/pdf_generator.py → backend → 项目根)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PDF_DIR = Path(os.getenv("PDF_OUTPUT_DIR", str(_PROJECT_ROOT / "data" / "pdf")))

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
            raise ValueError(f"未找到 {trade_date.isoformat()} 的预测报告（forecast_report 表中无 full_report 记录）")

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
            predictions.append({
                "title": title,
                "period": period,
                "上涨概率": item.get("上涨概率", 0) or 0,
                "下跌概率": item.get("下跌概率", 0) or 0,
                "上涨基点": item.get("上涨基点", 0) or 0,
                "下跌基点": item.get("下跌基点", 0) or 0,
                "置信度": item.get("置信度", None),
                "分析理由": item.get("分析理由", ""),
                "假设条件": item.get("假设条件", []),
            })

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
            scenarios.append({
                "key": key,
                "icon": icon,
                "title": title,
                "概率": item.get("概率", 0) or 0,
                "触发条件": item.get("触发条件", ""),
                "描述": item.get("描述", ""),
            })

    # ── 渲染模板 ──
    template = _jinja_env.get_template("report.html")
    html = template.render(
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
    trade_date_str = report["trade_date"].isoformat() if isinstance(report["trade_date"], date) else str(report["trade_date"])

    if output_path is None:
        output_path = str(PDF_DIR / f"{trade_date_str}.pdf")

    logger.info("  模型 : %s  |  版本 : %s", report["model_name"], report["prompt_version"])

    # 2. 构建 HTML
    html = _build_report_html(report)
    logger.info("HTML 已生成 (%.1f KB)", len(html.encode("utf-8")) / 1024)

    # 3. Playwright 渲染 HTML → PDF
    try:
        with sync_playwright() as p:
            # 自动检测 Chromium 可执行文件路径（跨平台兼容）
            import platform as _platform
            _system = _platform.system()

            # 查找 Playwright 浏览器安装目录
            _pw_base = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
            if not _pw_base:
                if _system == "Windows":
                    _pw_base = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright")
                else:
                    _pw_base = os.path.expanduser("~/.cache/ms-playwright")
            _pw_base = Path(_pw_base)

            # 平台相关：可执行文件名后缀和目录名
            if _system == "Windows":
                _exe_suffix, _chrome_dir = ".exe", "chrome-win"
            elif _system == "Darwin":
                _exe_suffix, _chrome_dir = "", "chrome-mac"
            else:
                _exe_suffix, _chrome_dir = "", "chrome-linux"

            _CHROMIUM_EXECUTABLE = None
            for _prefix in ("chromium-", "chromium_headless_shell-"):
                for _candidate in sorted(_pw_base.glob(f"{_prefix}*"), reverse=True):
                    for _name in (f"chrome{_exe_suffix}", f"headless_shell{_exe_suffix}"):
                        _exe = _candidate / _chrome_dir / _name
                        if _exe.exists():
                            _CHROMIUM_EXECUTABLE = str(_exe)
                            break
                    if _CHROMIUM_EXECUTABLE:
                        break
                if _CHROMIUM_EXECUTABLE:
                    break

            if _CHROMIUM_EXECUTABLE is None:
                raise RuntimeError(
                    "未找到 Playwright Chromium 浏览器，请运行: playwright install chromium"
                )

            launch_kwargs: dict = dict(
                headless=True,
                args=["--disable-gpu", "--no-sandbox", "--disable-setuid-sandbox",
                      "--disable-dev-shm-usage", "--disable-features=Crashpad"],
            )
            launch_kwargs["executable_path"] = _CHROMIUM_EXECUTABLE
            # 阻止 Playwright 尝试通过 channel 查找系统浏览器，
            # 明确使用 executable_path 指定的 Chromium
            launch_kwargs["channel"] = None

            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                viewport={"width": 1280, "height": 1800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                java_script_enabled=False,
                ignore_https_errors=True,
            )
            page = context.new_page()

            # 加载本地 HTML
            page.set_content(html, wait_until="load")
            logger.info("页面渲染完成")

            # 模拟打印媒体（触发 @media print 样式）
            page.emulate_media(media="print")

            # 生成 PDF
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "2cm", "right": "2cm", "bottom": "2cm", "left": "2cm"},
                display_header_footer=True,
                header_template=" ",
                footer_template=(
                    '<div style="font-size:9px;color:#999;text-align:center;width:100%;'
                    'padding:2px 0;">'
                    '第 <span class="pageNumber"></span> 页 / 共 <span class="totalPages"></span> 页'
                    '</div>'
                ),
            )

            # 保存文件
            output = Path(output_path)
            output.write_bytes(pdf_bytes)

            file_size_kb = len(pdf_bytes) / 1024
            logger.info("PDF 生成成功: %s (%.1f KB)", output, file_size_kb)

            browser.close()
            return output, trade_date_str

    except Exception as e:
        logger.exception("PDF 生成失败: %s", e)
        raise RuntimeError(f"PDF 生成失败: {e}") from e
