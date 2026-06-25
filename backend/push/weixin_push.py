"""
微信公众号 PDF 报告自动推送。

流程：
1. 获取最新 PDF 报告（或指定文件）
2. PDF 逐页转高清图片（200 DPI）
3. Playwright 自动登录微信公众号后台
4. 首页 → 点击"文章" → 进入编辑器
5. 逐张上传图片（保持页码顺序）
6. 填写标题/作者，保存草稿

使用方式：
    python backend/weixin_push.py --pdf-path "data/pdf/2026-04-24.pdf"
    python backend/weixin_push.py                          # 自动找最新 PDF
    python backend/weixin_push.py --publish                # 定时发布（暂未实现）

依赖：
    pip install PyMuPDF playwright
    playwright install chromium
"""

import os
import sys
import re
import time
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from backend.push.pdf_png import get_latest_pdf, pdf_to_images

# ==================== 日志 ====================
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("weixin_push")
logger.setLevel(logging.INFO)

fh = logging.FileHandler(
    LOG_DIR / f"weixin_push_{datetime.now().strftime('%Y%m%d')}.log",
    encoding="utf-8",
)
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
logger.addHandler(ch)

# ==================== 配置 ====================
WECHAT_APPID = os.getenv("WECHAT_APPID", "")
WECHAT_USERNAME = os.getenv("WECHAT_USERNAME", "")
WECHAT_PASSWORD = os.getenv("WECHAT_PASSWORD", "")

ARTICLE_TITLE_TEMPLATE = os.getenv(
    "ARTICLE_TITLE_TEMPLATE", "{} 债券市场预测分析报告",
)
ARTICLE_AUTHOR = os.getenv("ARTICLE_AUTHOR", "AI量化系统")

STORAGE_STATE_PATH = BASE_DIR / "wechat_login_state.json"
WECHAT_MP_URL = "https://mp.weixin.qq.com/"

# ==================== 辅助函数 ====================


def _extract_report_date(pdf_path: str | Path) -> str:
    """从 PDF 文件名提取报告日期，如 2026-04-24.pdf → 2026-04-24"""
    name = Path(pdf_path).stem
    match = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return match.group(1) if match else datetime.now().strftime("%Y-%m-%d")


def _cleanup_old_logs(keep_days: int = 7):
    """清理超过 keep_days 天的旧日志。"""
    now = datetime.now()
    cut_off = now - timedelta(days=keep_days)
    for directory in [LOG_DIR]:
        if not directory.exists():
            continue
        for f in directory.iterdir():
            if f.is_file():
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if mtime < cut_off:
                        f.unlink()
                except Exception:
                    pass


def _save_login_state(context):
    """保存登录状态到文件，下次免扫码。"""
    try:
        context.storage_state(path=str(STORAGE_STATE_PATH))
        logger.info("💾 登录状态已保存")
    except Exception as e:
        logger.warning("保存登录状态失败: %s", e)


# ==================== 登录 ====================


def _is_logged_in(page) -> bool:
    """判断当前页面是否已登录公众号后台。

    日志验证：URL 包含 /cgi-bin/ 100% 是后台页面；
    登录页 URL 始终是 https://mp.weixin.qq.com/，不会有 cgi-bin 路径。
    """
    return "/cgi-bin/" in page.url


def _smart_login(page, context) -> bool:
    """登录公众号：优先复用 storage_state，否则等待手机扫码。"""
    # 直接访问后台 cgi-bin 页面：已登录则停留，未登录则服务器重定向到登录页
    # 这样 URL 检测就能 100% 判断登录状态
    logger.info("访问微信公众号后台...")
    page.goto(WECHAT_MP_URL + "cgi-bin/home", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(2000)

    if _is_logged_in(page):
        logger.info("✅ 已登录（storage_state 有效）")
        return True

    logger.info("🔐 请用手机微信扫码登录（等待上限 180 秒）")
    deadline = time.time() + 180
    while time.time() < deadline:
        time.sleep(3)
        if _is_logged_in(page):
            logger.info("✅ 扫码登录成功")
            _save_login_state(context)
            return True
        logger.info("⏳ 已等待 %d 秒...", int(time.time() - deadline + 180))

    logger.error("❌ 扫码登录超时")
    return False


# ==================== 图文编辑器 ====================


def _is_on_editor(page) -> bool:
    """判断当前页面是否是公众号图文编辑器。"""
    url = page.url
    if "/cgi-bin/appmsg" in url and "action=edit" in url:
        return True
    # DOM 兜底
    for sel in ["#js_toolbar_0", ".ProseMirror"]:
        try:
            page.wait_for_selector(sel, state="attached", timeout=2000)
            return True
        except PlaywrightTimeout:
            continue
    return False


def _create_new_article(page):
    """
    进入图文编辑器：首页 → 点击"文章" → 切换到新标签页。

    Returns:
        (True, active_page)  成功
        (False, None)        失败
    """
    logger.info("进入图文编辑器...")

    # 1. 跳转首页
    try:
        page.goto(WECHAT_MP_URL, wait_until="domcontentloaded", timeout=12000)
    except Exception as e:
        logger.error("跳转公众号首页失败: %s", e)
        return False, None

    # 2. 等待"新的创作"面板
    try:
        page.wait_for_selector(".new-creation__menu-item", state="visible", timeout=10000)
    except PlaywrightTimeout:
        logger.error("❌ '新的创作'面板未加载")
        return False, None

    # 3. 点击"文章"，用 expect_page 捕获新标签页
    article_loc = page.locator(".new-creation__menu-title").filter(has_text="文章").first
    article_loc.wait_for(state="visible", timeout=5000)

    try:
        with page.context.expect_page(timeout=15000) as page_info:
            article_loc.click()
        new_page = page_info.value
        logger.info("  已打开编辑器标签页: %s", (new_page.url or "...")[:120])
    except Exception:
        logger.error("❌ 未捕获到编辑器新标签页")
        return False, None

    # 4. 切换到编辑器，等待加载
    new_page.bring_to_front()
    try:
        new_page.wait_for_load_state("domcontentloaded", timeout=20000)
    except PlaywrightTimeout:
        pass

    # 5. 等待编辑器 DOM 就绪
    for sel in ["#js_toolbar_0", ".ProseMirror"]:
        try:
            new_page.wait_for_selector(sel, state="attached", timeout=20000)
            break
        except PlaywrightTimeout:
            continue

    if _is_on_editor(new_page):
        logger.info("✅ 进入编辑器")
        return True, new_page

    logger.error("❌ 无法进入编辑器，URL: %s", new_page.url[:200])
    return False, None


# ==================== 图片上传 ====================


def _upload_images_in_editor(page, image_paths: list) -> bool:
    """
    按顺序逐张上传图片到编辑器正文。

    流程：点击"图片"→"本地上传"→选文件→等待上传→光标移到末尾→换行
    上传后光标移至正文末尾并换行，确保下一张图片插入在最后面，保持页码顺序。
    """
    total = len(image_paths)
    logger.info("在编辑器中上传 %d 张图片...", total)

    for i, img_path in enumerate(image_paths):
        img_name = Path(img_path).name
        logger.info("[%d/%d] %s (%.0f KB)", i + 1, total, img_name,
                    os.path.getsize(img_path) / 1024)

        # 1) 点击"图片"按钮打开下拉菜单（JS click 绕过视口限制）
        page.evaluate("""() => {
            const el = document.querySelector('#js_editor_insertimage');
            if (el) el.click();
        }""")
        time.sleep(0.5)

        # 2) 找到 file input 并上传图片
        file_input = page.locator('.tpl_dropdown_menu_item input[type="file"]').first
        file_input.set_input_files(str(img_path))

        # 3) 等待上传完成（进度条消失）
        try:
            page.wait_for_selector(".weui-loading", state="hidden", timeout=60000)
        except PlaywrightTimeout:
            logger.warning("  上传进度条等待超时，继续...")
        time.sleep(2)  # 等待编辑器完成图片渲染

        # 4) 点击"确定"（如果有）
        try:
            page.locator("button:has-text('确定')").first.click(timeout=3000)
            time.sleep(0.5)
        except Exception:
            pass

        # 5) 光标移到正文末尾 + 换行（确保下一张图片插入在最后）
        page.evaluate("""() => {
            const pm = document.querySelector('.ProseMirror');
            if (!pm) return;
            pm.focus();
            const sel = window.getSelection();
            const range = document.createRange();
            range.selectNodeContents(pm);
            range.collapse(false);
            sel.removeAllRanges();
            sel.addRange(range);
        }""")
        page.keyboard.press("Enter")

        logger.info("  ✅ [%d/%d] 上传完成", i + 1, total)

    logger.info("✅ 全部图片已插入正文")
    return True


# ==================== 文章元数据 & 保存 ====================


def _fill_article_meta(page, report_date: str):
    """填写文章标题和作者。"""
    title = ARTICLE_TITLE_TEMPLATE.format(report_date)[:64]
    logger.info("填写标题: %s", title)

    # 标题：使用 ProseMirror 编辑器（#title textarea 在页面中是隐藏的）
    try:
        title_pm = page.locator(".title-editor__input .ProseMirror").first
        title_pm.click()
        page.keyboard.press("Control+a")
        page.keyboard.insert_text(title)
        logger.info("  标题已填写")
    except Exception as e:
        logger.warning("  标题填写失败: %s", e)

    # 作者
    try:
        page.locator("#author").first.fill(ARTICLE_AUTHOR)
        logger.info("  作者已填写")
    except Exception as e:
        logger.warning("  作者填写失败: %s", e)


def _save_as_draft(page) -> bool:
    """保存文章为草稿。"""
    logger.info("保存草稿...")
    try:
        page.locator("button:has-text('保存为草稿')").first.click(timeout=5000)
        logger.info("✅ 已保存为草稿")
        time.sleep(2)
        return True
    except Exception:
        logger.warning("⚠️ 未找到保存按钮")
        return False


# ==================== 主流程 ====================


def push_report_to_wechat(
    pdf_path: str | Path = None,
    publish: bool = False,
    dpi: int = 200,
) -> bool:
    """
    将 PDF 报告推送到微信公众号。
    """
    # Step 1: 确定 PDF
    if pdf_path:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.error("PDF 文件不存在: %s", pdf_path)
            return False
    else:
        latest = get_latest_pdf()
        if not latest:
            logger.error("未找到任何 PDF 文件")
            return False
        pdf_path = latest

    report_date = _extract_report_date(pdf_path)
    logger.info("=" * 60)
    logger.info("  微信公众号 PDF 报告推送")
    logger.info("  PDF: %s", pdf_path)
    logger.info("  报告日期: %s", report_date)
    logger.info("=" * 60)

    _cleanup_old_logs(keep_days=7)

    # Step 2: PDF → 图片
    logger.info("📄 PDF → 图片 (DPI=%d)", dpi)
    try:
        image_paths = pdf_to_images(pdf_path=pdf_path, dpi=dpi)
        if not image_paths:
            logger.error("PDF 转图片失败：未生成任何图片")
            return False
        logger.info("生成 %d 张图片", len(image_paths))
    except Exception:
        logger.exception("PDF 转图片失败")
        return False

    # Step 3: 浏览器自动化
    logger.info("🌐 启动浏览器...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=80,
            args=["--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--disable-infobars"],
        )

        state_file = str(STORAGE_STATE_PATH) if STORAGE_STATE_PATH.exists() else None
        context = browser.new_context(
            storage_state=state_file,
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            # 3a: 登录
            if not _smart_login(page, context):
                return False

            # 3b: 进入编辑器
            ok, page = _create_new_article(page)
            if not ok:
                return False

            # 3c: 上传图片
            if not _upload_images_in_editor(page, image_paths):
                return False

            # 3d: 填写标题/作者
            _fill_article_meta(page, report_date)

            # 3e: 保存草稿
            if _save_as_draft(page):
                logger.info("\n" + "=" * 60)
                logger.info("  ✅ 文章已保存到草稿箱！")
                logger.info("  报告日期: %s", report_date)
                logger.info("  图片数量: %d 张", len(image_paths))
                logger.info("=" * 60)
            else:
                logger.warning("⚠️ 保存可能未成功")

            return True

        except Exception:
            logger.exception("浏览器自动化异常")
            return False
        finally:
            try:
                browser.close()
            except Exception:
                pass
            logger.info("浏览器已关闭")


def main():
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        description="微信公众号 PDF 报告自动推送",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python backend/weixin_push.py --pdf-path "data/pdf/2026-04-24.pdf"
  python backend/weixin_push.py                           # 自动找最新 PDF
  python backend/weixin_push.py --publish                 # 定时发布

首次运行：用手机微信扫码登录，后续自动复用登录状态。
配置（.env）：WECHAT_APPID, ARTICLE_AUTHOR 等
        """,
    )
    parser.add_argument("--pdf-path", default=None,
                        help="PDF 文件路径（默认自动查找 data/pdf/ 下最新文件）")
    parser.add_argument("--publish", action="store_true", default=False,
                        help="定时发布模式（默认仅保存草稿）")
    parser.add_argument("--dpi", type=int, default=200,
                        help="图片 DPI（默认 200）")
    args = parser.parse_args()

    success = push_report_to_wechat(
        pdf_path=args.pdf_path, publish=args.publish, dpi=args.dpi,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
