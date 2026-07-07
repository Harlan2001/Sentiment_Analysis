import logging
import os
import time
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger("pdf_generator")

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / "data" / "pdf"

# ========== 配置 ==========
# 默认使用 Vite 开发服务器地址（需同时运行 npm run dev）
FRONTEND_BASE_URL = os.getenv(
    "FRONTEND_BASE_URL",
    "http://localhost:5173",
)
# 预测页面路由
PREDICT_PAGE_ROUTE = "/prediction"

# 登录凭据（仅生产环境需要）
FRONTEND_USERNAME = os.getenv("FRONTEND_USERNAME", "")
FRONTEND_PASSWORD = os.getenv("FRONTEND_PASSWORD", "")


def _do_login_ks(page) -> bool:
    """
    针对 KS 平台生产环境的自动登录。
    拦截 oauth/token 请求，将 grant_type=ldap.rdtp 改为 password。
    """
    logger.info("检测到 KS 平台登录页面，执行自动登录...")

    # 设置路由拦截
    def intercept_oauth(route):
        post_data = route.request.post_data or ""
        if "oauth/token" in route.request.url and "grant_type=ldap.rdtp" in post_data:
            route.continue_(
                post_data=post_data.replace("grant_type=ldap.rdtp", "grant_type=password")
            )
        else:
            route.continue_()

    page.route("**/oauth/token**", intercept_oauth)

    try:
        # 等待登录表单
        page.wait_for_selector('input[placeholder*="账号"]', timeout=10000)
        page.locator('input[placeholder*="账号"]').first.fill(FRONTEND_USERNAME)
        page.locator('input[placeholder*="密码"]').first.fill(FRONTEND_PASSWORD)
        page.locator("button:has-text('登 录')").first.click()

        # 等待登录完成
        page.wait_for_load_state("load", timeout=30000)
        time.sleep(2)

        # 检查是否仍在登录页
        if page.locator("button:has-text('登 录')").count() > 0:
            logger.error("KS 平台登录失败")
            return False

        logger.info("KS 平台登录成功")
        return True

    except PlaywrightTimeout:
        logger.error("KS 平台登录超时")
        return False
    except Exception as e:
        logger.exception("KS 平台登录异常: %s", e)
        return False


def _is_ks_platform(url: str) -> bool:
    """判断前端地址是否为 KS 平台（通过 /ui/bond 路径识别）"""
    return "/ui/bond" in url


def generate_prediction_pdf(
    report_date: date = None,
    output_path: str = None,
    frontend_url: str = None,
) -> tuple:
    """
    使用 Playwright 打开前端预测页面，生成 PDF 保存到 data/pdf/。

    支持两种模式：
    1. 本地开发模式（默认）：连接到 http://localhost:5173/prediction（Vite dev server）
    2. 生产 KS 平台模式：设置 FRONTEND_BASE_URL 和 FRONTEND_USERNAME/FRONTEND_PASSWORD

    :param report_date: 报告日期，为 None 则不修改前端日期选择器，使用页面当前显示的日期。
    :param output_path: 可选，指定 PDF 输出路径，默认 data/pdf/{report_date}.pdf。
    :param frontend_url: 可选，覆盖前端基地址。
    :return: (PDF文件路径, 从页面提取的实际 trade_date) 的元组。
    """

    PDF_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        # 若有指定日期则用于初始文件名，否则用临时名（后续会被页面提取值覆盖）
        temp_name = f"{report_date.isoformat()}.pdf" if report_date else "_temp.pdf"
        output_path = str(PDF_DIR / temp_name)

    base_url = (frontend_url or FRONTEND_BASE_URL).rstrip("/")
    is_ks = _is_ks_platform(base_url)

    if is_ks:
        # KS 平台使用 hash 路由
        page_url = f"{base_url}/#/main/ai/quotation/predict"
    else:
        # 本地开发使用标准路由
        page_url = f"{base_url}{PREDICT_PAGE_ROUTE}"

    logger.info("开始生成预测报告 PDF")
    logger.info("  前端地址 : %s", page_url)
    logger.info("  报告日期 : %s", report_date if report_date else "(页面当前日期)")
    logger.info("  输出路径 : %s", output_path)
    logger.info("  平台模式 : %s", "KS 平台" if is_ks else "本地开发")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-gpu", "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 1800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                java_script_enabled=True,
                ignore_https_errors=True,
            )
            page = context.new_page()

            # ---------- 1. 导航到预测页面 ----------
            page.goto(page_url, wait_until="load", timeout=30000)
            logger.info("页面加载完成: %s", page.url)

            # ---------- 2. 登录（仅 KS 平台需要） ----------
            if is_ks:
                if not FRONTEND_USERNAME or not FRONTEND_PASSWORD:
                    raise RuntimeError(
                        "KS 平台需要登录，请设置 FRONTEND_USERNAME/FRONTEND_PASSWORD 环境变量"
                    )

                # 检查是否需要登录
                if "登 录" in page.inner_text("body"):
                    login_ok = _do_login_ks(page)
                    if not login_ok:
                        raise RuntimeError("KS 平台登录失败")

                    # 登录后重新导航到预测页面
                    page.goto(page_url, wait_until="load", timeout=30000)
                    time.sleep(2)

                    # 处理锁屏
                    if page.locator(".lock-screen-form").count() > 0:
                        logger.info("检测到锁屏，正在解锁...")
                        page.locator(".lock-screen-form input[type=password]").first.fill(FRONTEND_PASSWORD)
                        page.keyboard.press("Enter")
                        page.wait_for_load_state("load", timeout=15000)
                        time.sleep(2)

            # ---------- 3. 等待页面内容加载 ----------
            page.wait_for_selector('input[type="date"]', timeout=15000)
            logger.info("日期输入框已出现")

            # ---------- 4. 设置报告日期（仅当指定了日期时） ----------
            if report_date is not None:
                date_str = report_date.isoformat()
                date_input = page.locator('input[type="date"]').first
                date_input.click()
                date_input.fill("")
                date_input.type(date_str, delay=50)
                page.evaluate(
                    '(input) => input.dispatchEvent(new Event("change", { bubbles: true }))',
                    date_input.element_handle(),
                )
                logger.info("已设置查询日期: %s", date_str)

            # ---------- 5. 等待数据加载 ----------
            page.wait_for_load_state("networkidle", timeout=20000)

            # 等待 loading 消失
            loading_selector = "text=加载预测数据..."
            try:
                page.wait_for_selector(loading_selector, state="detached", timeout=15000)
            except PlaywrightTimeout:
                logger.warning("Loading 状态未检测到消失，继续执行")

            time.sleep(2)

            # ---------- 6. 提取 trade_date & 更新文件名 ----------
            # 从页面 <h3>2026-06-10 市场预测分析报告</h3> 中提取实际日期
            actual_trade_date = None
            try:
                page_text = page.inner_text("body")
                # 从 "2026-04-24 市场预测分析报告" 中提取日期
                import re
                trade_date_match = re.search(r'(\d{4}-\d{2}-\d{2})\s*市场预测分析报告', page_text)
                if trade_date_match:
                    actual_trade_date = trade_date_match.group(1)
                    logger.info("从页面提取 trade_date: %s", actual_trade_date)
                    # 用 trade_date 覆盖文件名
                    output_path = str(PDF_DIR / f"{actual_trade_date}.pdf")
                else:
                    logger.warning("未从页面提取到 trade_date")
            except Exception as e:
                logger.warning("提取 trade_date 失败: %s", e)

            if actual_trade_date is None:
                raise RuntimeError("无法从页面提取报告日期，请确认页面显示了有效的预测报告")

            # ---------- 7. 检测有效内容 ----------
            empty_texts = ["暂无预测报告", "格式错误", "加载失败"]
            page_text = page.inner_text("body")
            if any(t in page_text for t in empty_texts):
                logger.warning("页面显示无数据或错误状态，生成的 PDF 可能为空")

            page.emulate_media(media="print")

            # ---------- 8. DOM 清理（JS 直接删除交互元素，比 CSS 更可靠） ----------
            page.evaluate("""
                (function() {
                    // 1) 删除 MainLayout 顶部 header（"📊 债券市场智能分析"）
                    var header = document.querySelector('header');
                    if (header) header.remove();

                    // 2) 删除 PredictionPage 的前3个子元素（标题、日期选择、标签页）
                    // 注意：标签页导航已通过 CSS no-print 类隐藏，此处为额外保障
                    var containers = document.querySelectorAll('.space-y-6');
                    var outerContainer = null;
                    for (var ci = 0; ci < containers.length; ci++) {
                        if (containers[ci].querySelector('.page-header')) {
                            outerContainer = containers[ci];
                            break;
                        }
                    }
                    if (outerContainer) {
                        var children = outerContainer.children;
                        for (var i = 0; i < children.length && i < 3; i++) {
                            children[0].remove();  // 每次都删第一个
                        }
                    }

                    // 3) 删除所有图表 / canvas / 图表容器
                    var chartSelectors = [
                        '[class*="echart"]', '[class*="EChart"]',
                        '[class*="chart"]', '[class*="Chart"]',
                        'canvas', 'svg'
                    ];
                    chartSelectors.forEach(function(sel) {
                        document.querySelectorAll(sel).forEach(function(el) { el.remove(); });
                    });

                    // 4) 删除所有空的 div 容器（占位垃圾）
                    document.querySelectorAll('div:empty, span:empty').forEach(function(el) { el.remove(); });

                    console.log('PDF DOM cleanup done');
                })();
            """)
            logger.info("DOM 清理完成（header + 交互元素 + 图表 + 空标签）")
            logger.info("最终 PDF 输出路径: %s", output_path)

            # ---------- 9. 生成 PDF ----------
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

            # ---------- 10. 保存到文件 ----------
            output = Path(output_path)
            output.write_bytes(pdf_bytes)

            file_size_kb = len(pdf_bytes) / 1024
            logger.info("PDF 生成成功: %s (%.1f KB)", output, file_size_kb)

            browser.close()
            return output, actual_trade_date

    except PlaywrightTimeout as e:
        logger.error("页面加载超时: %s", e)
        raise RuntimeError(f"预测页面加载超时: {e}") from e
    except Exception as e:
        logger.exception("PDF 生成失败: %s", e)
        raise RuntimeError(f"PDF 生成失败: {e}") from e