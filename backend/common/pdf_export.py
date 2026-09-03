"""Playwright HTML → PDF 渲染：收敛 export_service 与 push.pdf_generator 的浏览器生命周期样板。

调用方各自构造 HTML；本模块负责 playwright 依赖探测、临时文件与浏览器资源回收。
@font-face 需要 file:// 源才能读取本地字体文件，因此统一「写临时 HTML + file:// goto」，
而非 page.set_content()（about:blank 源无法访问本地字体）。
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable


class PlaywrightUnavailableError(RuntimeError):
    """playwright 依赖或 Chromium 浏览器不可用时的降级异常。"""


@contextmanager
def _launch_page(
    sync_playwright: Callable[..., Any], html_content: str, wait_until: str
) -> Iterator[Any]:
    """写临时 HTML 并以 file:// 加载，yield 已就绪的 page。

    嵌套 finally：无论渲染成败都确保浏览器关闭、临时 HTML 删除，
    避免异常路径泄漏 Chromium 进程或残留临时文件。
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", encoding="utf-8", delete=False
            ) as tmp:
                tmp.write(html_content)
                tmp_path = tmp.name
            try:
                page = browser.new_page()
                page.goto(f"file:///{tmp_path.replace(os.sep, '/')}", wait_until=wait_until)
                yield page
            finally:
                os.unlink(tmp_path)
        finally:
            browser.close()


def render_html_to_pdf(
    html_content: str,
    *,
    output_path: str | os.PathLike[str] | None = None,
    margins: dict[str, str] | None = None,
    wait_until: str = "networkidle",
    page_format: str = "A4",
    print_background: bool = True,
) -> bytes | str:
    """将整页 HTML 渲染为 PDF。

    - ``output_path`` 提供时写入该文件并返回路径字符串（pdf_generator 用例）；
    - 否则返回 PDF bytes（export_service 用例，内部用临时 PDF 文件，finally 删除）。
    - playwright 缺失时抛 :class:`PlaywrightUnavailableError`（RuntimeError 子类），
      由调用方按各自文案包装；
    - 渲染期异常不做二次包装，原样上抛，调用方按自身错误文案处理。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaywrightUnavailableError(
            "PDF 渲染不可用：playwright 未安装，请执行 "
            "`pip install playwright && playwright install chromium`"
        ) from exc

    pdf_kwargs: dict[str, Any] = {"format": page_format, "print_background": print_background}
    if margins:
        pdf_kwargs["margin"] = margins

    with _launch_page(sync_playwright, html_content, wait_until) as page:
        if output_path is None:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_pdf = Path(tmp.name)
            try:
                page.pdf(path=str(tmp_pdf), **pdf_kwargs)
                return tmp_pdf.read_bytes()
            finally:
                tmp_pdf.unlink(missing_ok=True)
        page.pdf(path=str(output_path), **pdf_kwargs)
        return str(output_path)