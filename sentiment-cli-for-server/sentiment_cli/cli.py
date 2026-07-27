"""Command dispatch, argument building and output rendering for the CLI."""
from __future__ import annotations

import argparse
import json
import os
import sys

# WorkBuddy 等宿主会给子进程注入 NODE_OPTIONS（含 --use-system-ca /
# --require=...cjs），Playwright 的 node driver 启动即拒绝这些 flag 而崩。
# CLI 是 Python 进程，不需要 NODE_OPTIONS；在模块加载即进程级清除，
# 保证后续 spawn 的 Playwright driver 继承到干净的 env（不碰任何后端源码）。
os.environ.pop("NODE_OPTIONS", None)
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import NAME, __version__
from .client import BackendError, Client, NetworkError
from .config import (
    EXIT_BACKEND,
    EXIT_FAILURE,
    EXIT_GAPS,
    EXIT_OK,
    EXIT_USAGE,
    Config,
    load_dotenv,
)
from .skin import Skin
from .spec import KNOWN_GAPS, Operation, Spec, load_spec, save_bundled

# ---------------------------------------------------------------------------
# WorkBuddy / host-injected NODE_OPTIONS compatibility
# ---------------------------------------------------------------------------
# 宿主（如 WorkBuddy 的 Bash 工具）会向所有子进程注入 NODE_OPTIONS
# （含 --use-system-ca / require hook）。Playwright 自带的 node driver 在
# 启动时继承该变量并拒绝这些 flag，导致 driver 进程崩溃、连接关闭、
# 报 'PlaywrightContextManager' object has no attribute '_playwright'。
# Monkeypatch sync_playwright：进入前清除 NODE_OPTIONS，使其 node driver
# 干净启动。一次性改动，覆盖所有 sync_playwright() 调用点。
try:
    import playwright.sync_api as _pwsa
    _pw_orig_sync = _pwsa.sync_playwright

    def _pw_patched_sync_playwright(*a, **k):
        os.environ.pop("NODE_OPTIONS", None)
        return _pw_orig_sync(*a, **k)

    _pwsa.sync_playwright = _pw_patched_sync_playwright
except Exception:  # playwright 未安装时不影响其他功能
    pass

# NOTE: "batch" is intentionally excluded in this for-server build — it
# shells out to backend/tools/bond_downloader.py (a standalone script, not
# a REST endpoint) and is not part of the retained command set.
BUILTINS = {"describe", "health", "openapi", "groups", "gaps", "call", "config", "version", "help", "repl"}


# ---------------------------------------------------------------------------
# value coercion
# ---------------------------------------------------------------------------
def coerce(raw: Optional[str], ptype: str) -> Any:
    if raw is None:
        return None
    try:
        if ptype == "integer":
            return int(raw)
        if ptype == "number":
            return float(raw)
        if ptype == "boolean":
            return str(raw).lower() in ("1", "true", "yes", "y", "on")
        if ptype in ("array", "object"):
            return json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise UsageError(f"invalid value for type {ptype}: {raw!r} ({exc})")
    return raw


class UsageError(Exception):
    pass


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------
def emit(status: int, data: Any, command: str, as_json: bool, skin: Skin, out=None) -> None:
    out = out or sys.stdout
    if as_json:
        env = {
            "ok": 200 <= status < 300,
            "status": status,
            "command": command,
            "data": data,
        }
        out.write(json.dumps(env, ensure_ascii=False) + "\n")
    else:
        if isinstance(data, (dict, list)):
            out.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        elif data is not None:
            out.write(str(data) + "\n")
        skin.status(f"[{command}] HTTP {status}")
    out.flush()


def _default_download_name(req_path: str) -> str:
    """Derive a file name from the request URL when -o/--output is omitted."""
    segs = [s for s in req_path.split("/") if s and not s.startswith("{")]
    return segs[-1] if segs else "download.bin"


def _save_response(data: bytes, output: Optional[str], req_path: str,
                  command: str, as_json: bool, skin: Skin) -> int:
    """Write a binary/file response to disk and report where it landed.

    Used for endpoints that return e.g. a PDF. The bytes are never
    embedded in the JSON envelope — we report the saved path + size.
    """
    out = sys.stdout
    path = output or _default_download_name(req_path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    if as_json:
        env = {
            "ok": True,
            "status": 200,
            "command": command,
            "data": {"saved_to": path, "bytes": len(data)},
        }
        out.write(json.dumps(env, ensure_ascii=False) + "\n")
    else:
        skin.success(f"saved {len(data)} bytes -> {path}")
        out.write(f"[{command}] HTTP 200\n")
    out.flush()
    return EXIT_OK


# ---------------------------------------------------------------------------
# per-operation argument parser
# ---------------------------------------------------------------------------
def build_op_parser(op: Operation) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=f"{NAME} {op.group} {op.name}",
        description=op.summary or op.description or op.op_id,
        add_help=True,
    )
    for param in op.params:
        kwargs: Dict[str, Any] = {"dest": param.name, "default": None}
        help_bits = [f"({param.location}/{param.type})"]
        if param.required:
            help_bits.append("REQUIRED")
        if param.description:
            help_bits.append(param.description)
        kwargs["help"] = " ".join(help_bits)
        if param.enum:
            kwargs["choices"] = [str(e) for e in param.enum]
        if param.type == "boolean":
            kwargs["nargs"] = "?"
            kwargs["const"] = "true"
        if param.required:
            kwargs["required"] = True
        p.add_argument(param.cli_flag(), **kwargs)
    if op.group == "report":
        p.add_argument("--local", dest="__local", action="store_true",
                   help="本地生成/读取 PDF：自动选择可用渲染器（weasyprint 或本机 Playwright/Chromium），"
                        "复用服务器模板与数据库取数，不修改后端源码")
    p.add_argument("--body-json", dest="__body_json", default=None,
                   help="raw JSON object to use as the request body (merged with --field flags)")
    p.add_argument("--output", "-o", dest="__output", default=None,
                   help="write a binary/file response (e.g. a PDF) to this path "
                        "instead of printing it (default name derived from the URL)")
    p.add_argument("--json", dest="__as_json", action="store_true",
                   help="emit a machine-readable JSON envelope")
    return p


def _is_loopback(url: Optional[str]) -> bool:
    """True when *url* points at this machine (127.0.0.1 / localhost / ::1)."""
    if not url:
        return False
    try:
        host = (str(url).split("://", 1)[-1].split("/", 1)[0]
                .split(":", 1)[0].lower())
    except Exception:
        return False
    return host in ("127.0.0.1", "localhost", "::1", "0.0.0.0")


# ---------------------------------------------------------------------------
# per-command backend routing
#
# The same `backend/app.py` runs as TWO deployments that are NOT interchangeable:
#   * server  :8000  — has the `all-MiniLM` vector model, but its KingStar
#                   egress proxy has been degraded/hanging since 07-17, so any
#                   multi-step LLM call times out there.
#   * local   :8001  — direct KingStar (healthy), but no vector model.
#   * report  — has NO usable server mode (backend Playwright bug + read-only
#                   volume); must render locally (auto when base-url is loopback).
#
# So each command gets an ORDERED candidate list (best-first). We probe
# `/health` and pick the first reachable one; if none answer, we still use the
# first preference so the real error surfaces. An explicit `--base-url` overrides
# all of this (honored as-is, no auto-routing).
# ---------------------------------------------------------------------------
# Both backend URLs are env-overridable (host/port included); the defaults
# below match the current deployment.
LOCAL_BACKEND = os.environ.get("SENTIMENT_LOCAL_BACKEND", "http://127.0.0.1:8001")
SERVER_BACKEND = os.environ.get("SENTIMENT_SERVER_BACKEND", "http://10.253.50.112:8000")

# LLM multi-step commands: server proxy is down -> prefer local, fall back to server.
_LLM_MULTISTEP = {
    "change trigger", "strategy portfolio", "recommend analyze",
    "news analyze", "chat ask",
}

# Commands whose server-side LLM/compute can take well over the 30s
# default (KingStar multi-step calls, snapshot builds). When the user does
# NOT pass an explicit --timeout, these get a higher default so they
# aren't cut off mid-computation. (Includes the two strategy snapshot
# triggers which also fan out to the LLM gateway.)
_SLOW_TIMEOUT_OPS = _LLM_MULTISTEP | {"strategy trigger", "strategy sse"}
DEFAULT_TIMEOUT_SLOW = 180.0


def backend_candidates(op: Operation) -> List[str]:
    """Ordered backend URLs to try for *op*, best-first."""
    if op.group == "report":
        # No usable server mode — local rendering only (auto on loopback).
        return [LOCAL_BACKEND]
    if op.key in _LLM_MULTISTEP:
        return [LOCAL_BACKEND, SERVER_BACKEND]
    if op.key == "news similar":
        # `all-MiniLM` only exists in the server container.
        return [SERVER_BACKEND]
    # read-only / light commands: server first (canonical), local fallback.
    return [SERVER_BACKEND, LOCAL_BACKEND]


def pick_reachable(candidates: List[str], use_proxy: bool,
                   probe_timeout: float = 2.0) -> str:
    """Return the first candidate answering `/health` 200; else the first."""
    for url in candidates:
        try:
            cfg = Config(base_url=url, timeout=probe_timeout, use_proxy=use_proxy)
            _st, _ = Client(cfg).health()
            if _st == 200:
                return url
        except (NetworkError, BackendError):
            continue
    return candidates[0]


def run_operation(op: Operation, argv: List[str], client: Client, skin: Skin,
                  force_json: bool = False, base_is_local: bool = False) -> int:
    parser = build_op_parser(op)
    try:
        ns = parser.parse_args(argv)
    except SystemExit as exc:  # argparse error/help
        return int(exc.code or 0)
    values = vars(ns)
    as_json = force_json or values.pop("__as_json", False)
    output = values.pop("__output", None)
    body_json = values.pop("__body_json", None)

    path_values: Dict[str, Any] = {}
    query: Dict[str, Any] = {}
    body: Dict[str, Any] = {}
    if body_json:
        try:
            parsed = json.loads(body_json)
            if isinstance(parsed, dict):
                body.update(parsed)
        except json.JSONDecodeError as exc:
            skin.error(f"--body-json is not valid JSON: {exc}")
            return EXIT_USAGE

    try:
        for param in op.params:
            raw = values.get(param.name)
            if raw is None:
                continue
            val = coerce(raw, param.type)
            if param.location == "path":
                path_values[param.name] = val
            elif param.location == "query":
                query[param.name] = val
            else:
                body[param.name] = val
    except UsageError as exc:
        skin.error(str(exc))
        return EXIT_USAGE

    # report group: local generation/read via backend.push.pdf_generator
    # (bypasses the broken /sapi/report/* endpoints; read-only w.r.t. server).
    # `--local` is also implied when the backend is a loopback address
    # (e.g. --base-url http://127.0.0.1:8001): that is the local
    # backend, so report rendering must run locally too.
    local = values.pop("__local", False) or base_is_local
    if local:
        # Local mode makes no server request, so path-location params
        # (e.g. `filename` for `report download`) must also be
        # visible to the local handler via `query`.
        query.update(path_values)
    if op.key == "report generate" and local:
        return _report_generate_local(op, query, output, as_json, skin)
    if op.key == "report download" and local:
        return _report_download_local(op, query, output, as_json, skin)

    path = op.render_path(path_values)
    body_payload: Any = body if (body or op.body_params()) else None
    if op.method == "GET":
        body_payload = None

    try:
        if op.streaming:
            skin.status(f"[{op.key}] streaming {op.method} {path} (Ctrl-C to stop)")
            try:
                for line in client.stream(op.method, path, query=query, body=body_payload):
                    if line:
                        sys.stdout.write(line + "\n")
                        sys.stdout.flush()
            except (BackendError, NetworkError):
                raise  # surfaced by the outer handlers below
            except Exception as exc:  # long-lived SSE: a read/close timeout
                # after the initial data is a normal end-of-stream for a CLI.
                skin.warning(f"stream closed: {exc}")
            return EXIT_OK
        # chat ask: prefer a client-side direct gateway call when configured.
        # The server's /sapi/chat currently times out (its container
        # cannot egress to the KingStar gateway); calling the gateway
        # directly from the CLI bypasses that broken endpoint entirely.
        if (op.key == "chat ask"
                and getattr(client.config, "chat_gateway_url", None)
                and getattr(client.config, "chat_gateway_key", None)):
            try:
                content, usage = client.chat_gateway(
                    messages=body.get("messages"),
                    model=client.config.chat_gateway_model,
                    stream=body.get("stream", False),
                    enable_tools=body.get("enable_tools", False),
                )
            except BackendError as exc:
                emit(exc.status, {"error": str(exc.body)}, op.key, as_json, skin)
                skin.error(f"chat gateway error HTTP {exc.status}")
                return EXIT_BACKEND
            except NetworkError as exc:
                skin.error(str(exc))
                return EXIT_FAILURE
            emit(200, {"content": content, "usage": usage}, op.key, as_json, skin)
            return EXIT_OK
        status, data = client.request(op.method, path, query=query, body=body_payload)
        if isinstance(data, (bytes, bytearray)):
            # Binary / file response — save it, don't print/embed it.
            return _save_response(data, output, path, op.key, as_json, skin)
        emit(status, data, op.key, as_json, skin)
        return EXIT_OK
    except BackendError as exc:
        emit(exc.status, exc.body, op.key, as_json, skin)
        skin.error(f"backend error HTTP {exc.status}")
        return EXIT_BACKEND
    except NetworkError as exc:
        skin.error(str(exc))
        return EXIT_FAILURE
    except KeyboardInterrupt:
        skin.warning("interrupted")
        return EXIT_OK


# ---------------------------------------------------------------------------
# local browser resolution (for `report generate --local`)
# ---------------------------------------------------------------------------
# Idempotency guard: {id(chromium_class): executable_path} so we never
# stack multiple wrappers on the same class.
_LOCAL_BROWSER_PATCH: Dict[int, str] = {}


def _resolve_local_browser() -> Optional[str]:
    """Pick a Chromium-based browser for LOCAL PDF rendering.

    Priority:
      1. ``SENTIMENT_REPORT_CHROME`` env (explicit executable path)
      2. A local Chromium build on ``D:/chromium/*/chrome-win/chrome.exe``
         (user-preferred browser on this machine — used instead of Edge)
      3. Playwright's bundled chromium (if ``playwright install`` succeeded)
      4. A system Microsoft Edge / Google Chrome (auto-detected)

    Returns an executable path, or ``None`` to let Playwright use its own
    bundled browser unchanged.
    """
    override = os.environ.get("SENTIMENT_REPORT_CHROME")
    if override and os.path.isfile(override):
        return override
    # 2. Local D: chromium build (preferred over system Edge/Chrome)
    import glob as _glob
    for _pat in (
        "D:/chromium/*/chrome-win/chrome.exe",
        "D:/Chromium/*/chrome-win/chrome.exe",
    ):
        _hits = sorted(_glob.glob(_pat), reverse=True)
        if _hits and os.path.isfile(_hits[0]):
            return _hits[0]
    # 3. Playwright's own chromium already installed?
    try:
        import playwright.sync_api as _spa
        with _spa.sync_playwright() as _p:
            _ep = _p.chromium.executable_path
            if callable(_ep):
                _ep = _ep()
        if _ep and os.path.isfile(_ep):
            return None  # let Playwright use its bundled browser
    except Exception:
        pass
    # 4. Auto-detect a system Chromium-based browser
    candidates = [
        r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        r"C:/Program Files/Microsoft/Edge/Application/msedge.exe",
        r"C:/Program Files/Google/Chrome/Application/chrome.exe",
        r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    import shutil
    for name in ("msedge", "google-chrome", "chrome", "chromium"):
        loc = shutil.which(name)
        if loc:
            return loc
    return None


def _patch_local_browser(executable_path: str) -> None:
    """Monkeypatch Playwright's ``chromium.launch`` to use *executable_path*.

    **Non-invasive**: does NOT modify the server's ``pdf_generator.py``.
    The patch is applied to the chromium ``BrowserType`` class, so the
    server function (which calls ``p.chromium.launch(headless=True, ...)``)
    transparently drives the local browser. Idempotent per executable path.
    """
    if not executable_path or not os.path.isfile(executable_path):
        return
    import functools
    import playwright.sync_api as _spa
    with _spa.sync_playwright() as _p:
        cls = type(_p.chromium)
    if _LOCAL_BROWSER_PATCH.get(id(cls)) == executable_path:
        return

    orig = cls.launch

    def _launch(self, *args, **kwargs):
        kwargs.setdefault("executable_path", executable_path)
        return orig(self, *args, **kwargs)

    cls.launch = _launch
    _LOCAL_BROWSER_PATCH[id(cls)] = executable_path


def _latest_forecast_date(skin: Skin):
    """Newest ``full_report`` trade_date in ``forecast_report`` (direct MySQL).

    Used by ``report generate --local`` when no --report-date is given, since
    the rewritten backend pdf_generator (DB + weasyprint) requires an explicit
    date while the CLI's original behaviour was "latest when omitted".
    """
    try:
        import pymysql
        proj, _ = _resolve_backend_env()
        cfg = _mysql_config_from_env(proj)
        conn = pymysql.connect(**cfg, connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT MAX(trade_date) FROM forecast_report "
                    "WHERE forecast_type = 'full_report'")
                row = cur.fetchone()
        finally:
            conn.close()
        return row[0] if row and row[0] else None
    except Exception as exc:
        skin.warning(f"[report] latest-date lookup failed: {exc}")
        return None


def _playwright_chromium_executable() -> Optional[str]:
    """Resolve a Chromium executable for LOCAL Playwright PDF rendering.

    Returns an explicit path (system Edge / local chromium build / ...) to pass
    as ``executable_path``, or ``None`` to let Playwright use its own bundled
    chromium — but only when the bundled binary actually exists on disk.

    Handles both Playwright API shapes: ``chromium.executable_path`` (str
    property on newer versions) and ``chromium.executable_path()`` (callable on
    older versions).
    """
    try:
        import playwright.sync_api as _spa
        with _spa.sync_playwright() as _p:
            _ep = _p.chromium.executable_path
            if callable(_ep):
                _ep = _ep()
        if isinstance(_ep, str) and _ep and os.path.isfile(_ep):
            return None  # bundled chromium is usable; let Playwright drive it
    except Exception:
        pass
    # Fall back to a system / local Chromium build (may be None if none found).
    return _resolve_local_browser()


def _playwright_available() -> bool:
    """True if a Playwright-drivable Chromium is available on this host."""
    if _playwright_chromium_executable() is not None:
        return True
    # executable() returned None → either bundled chromium exists, or nothing
    # found. Re-check the bundled binary explicitly to disambiguate.
    try:
        import playwright.sync_api as _spa
        with _spa.sync_playwright() as _p:
            _ep = _p.chromium.executable_path
            if callable(_ep):
                _ep = _ep()
        return bool(isinstance(_ep, str) and _ep and os.path.isfile(_ep))
    except Exception:
        return False


def _detect_pdf_renderer(skin: Skin) -> str:
    """Pick a working PDF renderer for ``report generate --local``.

    Device-condition branch, order of preference:

    1. ``weasyprint`` — the real package can render (Linux/container). On this
       Windows host the import is satisfied by a *stub* whose ``HTML()`` raises,
       so we probe with a trivial document and treat any failure as "unavailable".
    2. ``playwright`` — a Chromium-based browser is present (system Edge / local
       chromium / Playwright bundled). We reuse the server's
       ``_build_report_html`` to produce identical HTML, then render via
       ``page.pdf()``.
    3. ``none`` — neither works; the caller emits a clear error.

    Does NOT modify any backend source file.
    """
    # 1) weasyprint (real)
    try:
        import io
        from weasyprint import HTML
        probe = HTML(string="<html><body>probe</body></html>")
        probe.render().write_pdf(target=io.BytesIO())
        return "weasyprint"
    except Exception as exc:
        skin.info(f"[report] weasyprint 不可用，回退 Playwright: {exc}")
    # 2) playwright + chromium
    if _playwright_available():
        return "playwright"
    return "none"


def _report_generate_local_playwright(report_date, output_path, skin: Skin):
    """Render the prediction report to PDF via local Chromium (Playwright).

    Reuses the SERVER's ``backend.push.pdf_generator._build_report_html`` so the
    HTML is byte-for-byte identical to what weasyprint would receive — only the
    final rasterisation differs. Non-invasive: the server's ``pdf_generator.py``
    is never imported for PDF *writing*, only read for the pure HTML builder and
    the DB fetcher.

    Returns ``(out_path, trade_date_str)`` like the server's function.
    """
    from backend.push.pdf_generator import _fetch_report_from_db, _build_report_html, PDF_DIR
    from datetime import date as _date

    report = _fetch_report_from_db(report_date)
    html = _build_report_html(report)
    trade_date_str = (
        report["trade_date"].isoformat()
        if isinstance(report["trade_date"], _date) else str(report["trade_date"])
    )
    if not output_path:
        output_path = str(PDF_DIR / f"{trade_date_str}.pdf")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    exe = _playwright_chromium_executable()
    try:
        import playwright.sync_api as _spa
        with _spa.sync_playwright() as _p:
            launch = dict(headless=True, args=["--no-sandbox", "--disable-gpu"])
            if exe:
                launch["executable_path"] = exe
            browser = _p.chromium.launch(**launch)
            try:
                page = browser.new_page()
                # HTML is fully self-contained (inline CSS, no external assets),
                # so "load" fires quickly; no network/CDN dependency.
                page.set_content(html, wait_until="load")
                page.pdf(
                    path=str(out),
                    print_background=True,
                    prefer_css_page_size=True,  # honour @page { size:A4; margin:2cm }
                )
            finally:
                browser.close()
    except Exception as exc:
        raise RuntimeError(f"Playwright 渲染 PDF 失败: {exc}") from exc

    skin.status(
        f"[report] Playwright 已生成 PDF: {out} "
        f"(使用浏览器: {exe or 'bundled chromium'})"
    )
    return str(out), trade_date_str


def _report_generate_local(op: Operation, query: Dict[str, Any], output: Optional[str],
                          as_json: bool, skin: Skin) -> int:
    """Generate the prediction PDF LOCALLY, device-condition branch.

    Reuses the SERVER's report template + DB fetcher (read-only w.r.t. the
    server). Picks a working renderer without modifying ``pdf_generator.py``:

    * ``weasyprint`` — real weasyprint present (Linux/container) → use as-is.
    * ``playwright`` — a local Chromium-based browser is present → render the
      same HTML that ``_build_report_html`` produces via ``page.pdf()``.
    * ``none`` — emit a clear error.
    """
    try:
        import sys
        from pathlib import Path as _P
        proj = _P(__file__).resolve().parent.parent.parent  # sentiment_cli/../.. = Sentiment Analysis (repo root)
        if str(proj) not in sys.path:
            sys.path.insert(0, str(proj))
        # The backend's pure-python deps (jinja2, pymysql, ...) live in the
        # repo-root .venv. APPEND (not prepend) so the CLI interpreter's OWN
        # working packages — notably playwright/greenlet built for Python 3.13 —
        # win over the 3.11 venv's incompatible compiled extensions.
        _repo_sp = proj / ".venv" / "Lib" / "site-packages"
        if _repo_sp.is_dir() and str(_repo_sp) not in sys.path:
            sys.path.append(str(_repo_sp))
        # The weasyprint stub (Windows without Pango) must win over any real
        # package — insert it at the very front.
        _stubs = _P(__file__).resolve().parents[1] / "stubs"
        if _stubs.is_dir() and str(_stubs) not in sys.path:
            sys.path.insert(0, str(_stubs))
        from backend.push.pdf_generator import generate_prediction_pdf
    except Exception as exc:
        skin.error(f"本地报告生成需要 backend 包及其依赖(jinja2 等): {exc}")
        return EXIT_FAILURE
    rd = None
    rd_raw = query.get("report_date")
    if rd_raw:
        try:
            from datetime import date as _d
            rd = _d.fromisoformat(str(rd_raw))
        except ValueError:
            skin.error(f"report_date 格式错误: {rd_raw}，请用 YYYY-MM-DD")
            return EXIT_USAGE
    if rd is None:
        # New pdf_generator (DB+weasyprint mode) requires an explicit date.
        # Preserve the old "no date -> latest report" behaviour by looking up
        # the newest full_report trade_date straight from MySQL.
        rd = _latest_forecast_date(skin)
        if rd is None:
            skin.error("未指定 --report-date 且数据库中无 full_report 记录可回退")
            return EXIT_FAILURE
        skin.status(f"[report] no --report-date given; using latest full_report date {rd}")
    try:
        # New pdf_generator reads the report from MySQL (DB mode) — the CLI
        # process must initialise the backend's connection pool first.
        from backend.common.database import init_database, DatabaseConfig
        _cfg = _mysql_config_from_env(proj)
        init_database(DatabaseConfig(
            host=_cfg["host"], port=_cfg["port"], user=_cfg["user"],
            password=_cfg["password"], database=_cfg["database"],
            charset=_cfg.get("charset", "utf8mb4"),
        ))
        # Device-condition branch: pick a working PDF renderer without
        # modifying the server's pdf_generator.py (which only knows weasyprint).
        renderer = _detect_pdf_renderer(skin)
        skin.status(f"[report] 选择 PDF 渲染器: {renderer}")
        if renderer == "weasyprint":
            out_path, trade_date = generate_prediction_pdf(
                report_date=rd, output_path=output,
            )
        elif renderer == "playwright":
            out_path, trade_date = _report_generate_local_playwright(rd, output, skin)
        else:
            skin.error(
                "本机无可用 PDF 渲染器：weasyprint 不可用且未检测到 "
                "Playwright/Chromium。可在 Linux 服务器部署版执行，"
                "或安装 Playwright 浏览器（playwright install chromium）。"
            )
            return EXIT_FAILURE
    except Exception as exc:
        skin.error(f"本地报告生成失败: {exc}")
        return EXIT_FAILURE
    # The server's pdf_generator *ignores* ``output`` once it extracts a
    # trade_date and writes to PDF_DIR/<date>.pdf. Honour the user's
    # --output without touching the server: copy the produced file there.
    if output and Path(output).resolve() != Path(out_path).resolve():
        try:
            import shutil as _sh
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            _sh.copyfile(out_path, output)
            out_path = Path(output)
        except Exception as exc:
            skin.warning(f"无法写入 --output，仍使用: {out_path} ({exc})")
    _out_p = Path(out_path)
    data = {
        "report_date": trade_date,
        "file_path": str(_out_p),
        "file_name": _out_p.name,
        "file_size_bytes": _out_p.stat().st_size,
    }
    emit(200, data, op.key, as_json, skin)
    return EXIT_OK


def _report_download_local(op: Operation, query: Dict[str, Any], output: Optional[str],
                           as_json: bool, skin: Skin) -> int:
    """Read a previously-generated PDF from a local data/pdf directory."""
    from pathlib import Path as _P
    fname = query.get("filename")
    if not fname:
        skin.error("report download --local 需要 --filename")
        return EXIT_USAGE
    proj = _P(__file__).resolve().parent.parent.parent
    # output dir: `report download --local` may point at the same dir that
    # `report generate --local --output <dir>/X.pdf` wrote into.
    out_dir = _P(output).parent if output else _P(".")
    report_dir = _P(os.environ.get("SENTIMENT_REPORT_DIR", "."))
    candidates = [
        _P(fname),
        _P("reports") / fname,
        out_dir / fname,
        report_dir / fname,
        _P("data") / "pdf" / fname,
        proj / "data" / "pdf" / fname,
    ]
    found = next((c for c in candidates if c.is_file()), None)
    if not found:
        # Fall back to LOCAL generation: re-render the report from the
        # server's data with a local browser (system Edge via the playwright
        # monkeypatch), then read it back. This bypasses the broken
        # server `/sapi/report/files/*` endpoint (writes to a read-only
        # volume -> HTTP 500) entirely, so `report download --local`
        # runs end-to-end on the local machine.
        date_part = _P(fname).stem  # "2026-07-15.pdf" -> "2026-07-15"
        generated = False
        try:
            from datetime import date as _d
            _d.fromisoformat(date_part)  # only fall back for YYYY-MM-DD filenames
            skin.status(
                f"本地未找到 {fname}，回退到本地生成 "
                f"(report generate --local，从服务器取数 + 本机浏览器渲染)..."
            )
            sub_q = dict(query)
            sub_q["report_date"] = date_part
            if _report_generate_local(op, sub_q, output, as_json, skin) == EXIT_OK:
                generated = True
                found = next((c for c in candidates if c.is_file()), None)
        except ValueError:
            pass  # not a date-named file; skip fallback
        except Exception as exc:
            skin.warning(f"本地生成回退失败: {exc}")
        if not generated:
            skin.error(
                f"本地未找到报告文件: {fname}"
                f"（本地生成也未产出；可直接运行 `report generate --local "
                f"--report-date {date_part}` 排查）"
            )
            return EXIT_FAILURE
    data = found.read_bytes()
    return _save_response(data, output, f"/local/{fname}", op.key, as_json, skin)


# ---------------------------------------------------------------------------
# built-in commands
# ---------------------------------------------------------------------------
def cmd_describe(spec: Spec, config: Config, client: Client, argv: List[str], skin: Skin) -> int:
    check = "--check" in argv
    reachable: Optional[bool] = None
    if check:
        try:
            status, _ = client.health()
            reachable = 200 <= status < 300
        except Exception:
            reachable = False
    doc = build_description(spec, config, reachable)
    sys.stdout.write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    if check and not reachable:
        return EXIT_GAPS
    return EXIT_OK


def build_description(spec: Spec, config: Config, reachable: Optional[bool] = None) -> Dict[str, Any]:
    groups = []
    for gname in sorted(spec.groups):
        ops = []
        for op in spec.groups[gname]:
            ops.append({
                "name": op.name,
                "invoke": f"{NAME} {op.group} {op.name}",
                "method": op.method,
                "path": op.path,
                "summary": op.summary,
                "streaming": op.streaming,
                "params": [
                    {
                        "flag": p.cli_flag(),
                        "in": p.location,
                        "type": p.type,
                        "required": p.required,
                        **({"enum": p.enum} if p.enum else {}),
                    }
                    for p in op.params
                ],
            })
        groups.append({"name": gname, "operation_count": len(ops), "operations": ops})
    return {
        "name": NAME,
        "version": __version__,
        "description": "Agent-native CLI wrapping the Bond Yield / Sentiment Analysis backend over HTTP.",
        "backend": {
            "title": spec.title,
            "spec_version": spec.version,
            "base_url": config.base_url,
            **({"reachable": reachable} if reachable is not None else {}),
        },
        "exit_codes": {
            "0": "success",
            "1": "unexpected failure / backend unreachable",
            "2": "usage error",
            "3": "partial / capability gap",
            "4": "backend returned an error status",
        },
        "global_flags": [
            "--base-url URL", "--token TOKEN", "--timeout SECONDS",
            "--use-proxy", "--json", "--spec PATH",
        ],
        "conventions": {
            "json_envelope": {"ok": "bool", "status": "int", "command": "str", "data": "any"},
            "body_override": "--body-json '{...}' on any operation",
            "raw_escape_hatch": f"{NAME} call <METHOD> <path> [--query k=v] [--body '{{...}}']",
        },
        "operation_total": len(spec.operations),
        "groups": groups,
        "not_implemented": [
            {
                "id": g["id"],
                "title": g["title"],
                "category": g["category"],
                "status": g["status"],
                "priority": g["priority"],
                "reason": g["reason"],
                "impact": g["impact"],
                "workaround": g["workaround"],
            }
            for g in KNOWN_GAPS
        ],
    }


def cmd_health(client: Client, as_json: bool, skin: Skin) -> int:
    try:
        status, data = client.health()
        emit(status, data, "health", as_json, skin)
        return EXIT_OK
    except NetworkError as exc:
        skin.error(str(exc))
        return EXIT_FAILURE


def cmd_openapi(config: Config, client: Client, argv: List[str], skin: Skin) -> int:
    if "--refresh" in argv:
        try:
            raw = client.fetch_openapi()
        except NetworkError as exc:
            skin.error(str(exc))
            return EXIT_FAILURE
        path = save_bundled(raw)
        skin.success(f"refreshed OpenAPI cache: {path} ({len(raw.get('paths', {}))} paths)")
        return EXIT_OK
    spec = load_spec(config.spec_path)
    summary = {
        "title": spec.title,
        "version": spec.version,
        "paths": len(spec.raw.get("paths", {})),
        "operations": len(spec.operations),
        "groups": {g: len(ops) for g, ops in sorted(spec.groups.items())},
    }
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return EXIT_OK


def cmd_groups(spec: Spec, skin: Skin) -> int:
    for gname in sorted(spec.groups):
        ops = spec.groups[gname]
        skin.info(f"{gname}  ({len(ops)})")
        for op in ops:
            sys.stdout.write(f"  {gname} {op.name:<24} {op.method:<5} {op.summary}\n")
    return EXIT_OK


def cmd_gaps(as_json: bool, skin: Skin) -> int:
    """List capabilities the CLI does NOT wrap (from spec.KNOWN_GAPS)."""
    rows = [
        {
            "id": g["id"],
            "title": g["title"],
            "category": g["category"],
            "status": g["status"],
            "priority": g["priority"],
            "reason": g["reason"],
            "impact": g["impact"],
            "workaround": g["workaround"],
        }
        for g in KNOWN_GAPS
    ]
    if as_json:
        sys.stdout.write(
            json.dumps(
                {"ok": True, "status": 200, "command": "gaps", "data": rows},
                ensure_ascii=False,
            )
            + "\n"
        )
        return EXIT_OK
    counts: Dict[str, int] = {}
    for g in rows:
        counts[g["status"]] = counts.get(g["status"], 0) + 1
    skin.info(f"Known gaps (not wrapped by this CLI): {len(rows)} "
              f"[{', '.join(f'{k}={v}' for k, v in sorted(counts.items()))}]")
    for g in rows:
        skin.label(g["status"], f"{g['title']}  ({g['id']})")
        sys.stdout.write(f"   category  : {g['category']}\n")
        sys.stdout.write(f"   priority  : {g['priority']}\n")
        sys.stdout.write(f"   reason    : {g['reason']}\n")
        sys.stdout.write(f"   impact    : {g['impact']}\n")
        sys.stdout.write(f"   workaround: {g['workaround']}\n")
    return EXIT_OK


def cmd_call(client: Client, argv: List[str], skin: Skin, force_json: bool) -> int:
    p = argparse.ArgumentParser(prog=f"{NAME} call", add_help=True)
    p.add_argument("method")
    p.add_argument("path")
    p.add_argument("--query", action="append", default=[], metavar="k=v")
    p.add_argument("--body", default=None, help="raw JSON body")
    p.add_argument("--output", "-o", dest="output", default=None,
                   help="write a binary/file response to this path")
    p.add_argument("--json", dest="as_json", action="store_true")
    try:
        ns = p.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    query: Dict[str, Any] = {}
    for item in ns.query:
        if "=" not in item:
            skin.error(f"--query expects k=v, got {item!r}")
            return EXIT_USAGE
        k, v = item.split("=", 1)
        query[k] = v
    body = None
    if ns.body:
        try:
            body = json.loads(ns.body)
        except json.JSONDecodeError as exc:
            skin.error(f"--body is not valid JSON: {exc}")
            return EXIT_USAGE
    path = ns.path if ns.path.startswith("/") else "/" + ns.path
    try:
        status, data = client.request(ns.method, path, query=query, body=body)
        if isinstance(data, (bytes, bytearray)):
            return _save_response(
                data, ns.output, path,
                f"call {ns.method.upper()} {path}", force_json or ns.as_json, skin,
            )
        emit(status, data, f"call {ns.method.upper()} {path}", force_json or ns.as_json, skin)
        return EXIT_OK
    except BackendError as exc:
        emit(exc.status, exc.body, f"call {ns.method.upper()} {path}", force_json or ns.as_json, skin)
        return EXIT_BACKEND
    except NetworkError as exc:
        skin.error(str(exc))
        return EXIT_FAILURE


def cmd_config(argv: List[str], config: Config, skin: Skin) -> int:
    if not argv or argv[0] == "show":
        data = config.to_dict()
        if data.get("token"):
            data["token"] = data["token"][:8] + "…(hidden)"
        sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        return EXIT_OK
    if argv[0] == "path":
        from .config import CONFIG_FILE
        sys.stdout.write(str(CONFIG_FILE) + "\n")
        return EXIT_OK
    if argv[0] == "set":
        p = argparse.ArgumentParser(prog=f"{NAME} config set")
        p.add_argument("--base-url")
        p.add_argument("--token")
        p.add_argument("--timeout", type=float)
        p.add_argument("--use-proxy", choices=["true", "false"])
        try:
            ns = p.parse_args(argv[1:])
        except SystemExit as exc:
            return int(exc.code or 0)
        values: Dict[str, Any] = {}
        if ns.base_url is not None:
            values["base_url"] = ns.base_url
        if ns.token is not None:
            values["token"] = ns.token
        if ns.timeout is not None:
            values["timeout"] = ns.timeout
        if ns.use_proxy is not None:
            values["use_proxy"] = ns.use_proxy == "true"
        path = Config.save(values)
        skin.success(f"saved config to {path}")
        return EXIT_OK
    skin.error(f"unknown config subcommand: {argv[0]} (use show|set|path)")
    return EXIT_USAGE


# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------
def print_help(spec: Spec, skin: Skin) -> None:
    out = sys.stdout
    out.write(f"{NAME} — agent-native CLI for the Bond Yield / Sentiment Analysis backend\n\n")
    out.write("USAGE\n")
    out.write(f"  {NAME} [global-flags] <group> <operation> [--flags]\n")
    out.write(f"  {NAME} <builtin> [args]\n")
    out.write(f"  {NAME}                     # no args -> interactive REPL\n\n")
    out.write("GLOBAL FLAGS\n")
    out.write("  --base-url URL   backend base url (default from config/env)\n")
    out.write("  --token TOKEN    bearer token (when AUTH_ENABLED)\n")
    out.write("  --timeout SEC    request timeout\n")
    out.write("  --use-proxy      honour system HTTP proxy (default: bypass)\n")
    out.write("  --json           machine-readable JSON envelope\n")
    out.write("  --spec PATH      use a specific openapi.json\n\n")
    out.write("BUILTINS\n")
    out.write("  describe [--check]   full JSON self-description of all commands\n")
    out.write("  gaps                 list capabilities NOT wrapped by this CLI\n")
    out.write("  groups               list command groups and operations\n")
    out.write("  health               backend health probe\n")
    out.write("  openapi [--refresh]  show/refresh the OpenAPI cache\n")
    out.write("  call M PATH ...      raw request escape hatch\n")
    out.write("  config show|set|path manage saved config\n")
    out.write("  batch analyze|bond-download  wrap backend standalone scripts\n")
    out.write("  version              print version\n\n")
    out.write("COMMAND GROUPS\n")
    for gname in sorted(spec.groups):
        names = ", ".join(op.name for op in spec.groups[gname])
        out.write(f"  {gname:<12} {names}\n")
    out.write(f"\nRun '{NAME} <group>' to list a group, or '{NAME} <group> <op> --help' for details.\n")


# ---------------------------------------------------------------------------
# global-flag peeling + dispatch
# ---------------------------------------------------------------------------
GLOBAL_WITH_VALUE = {"--base-url", "--token", "--timeout", "--spec"}
GLOBAL_FLAGS = {"--use-proxy", "--json", "--no-banner"}


def split_globals(argv: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    opts: Dict[str, Any] = {}
    rest: List[str] = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in GLOBAL_WITH_VALUE:
            if i + 1 >= len(argv):
                raise UsageError(f"{tok} requires a value")
            opts[tok.lstrip("-")] = argv[i + 1]
            i += 2
        elif tok in GLOBAL_FLAGS:
            opts[tok.lstrip("-")] = True
            i += 1
        else:
            rest.append(tok)
            i += 1
    return opts, rest


def make_context(gopts: Dict[str, Any]) -> Tuple[Config, Client, Spec, Skin, bool]:
    config = Config(
        base_url=gopts.get("base-url"),
        token=gopts.get("token"),
        timeout=float(gopts["timeout"]) if gopts.get("timeout") else None,
        use_proxy=True if gopts.get("use-proxy") else None,
    )
    config.spec_path = gopts.get("spec")  # type: ignore[attr-defined]
    spec = load_spec(config.spec_path)
    client = Client(config)
    skin = Skin()
    force_json = bool(gopts.get("json"))
    return config, client, spec, skin, force_json


# ---------------------------------------------------------------------------
# `batch` builtin — wrap backend standalone scripts (no HTTP endpoint).
#
# These scripts (backend/analysis/analyzer_runner.py,
# backend/tools/bond_downloader.py) are argparse/main() standalone
# tools, NOT REST endpoints. We run them as subprocesses (no backend
# source is modified) so they surface through the CLI.
# ---------------------------------------------------------------------------
def _resolve_backend_env() -> Tuple[str, str]:
    """Return (project_root, python_exe) for running backend standalone scripts.

    The scripts run with cwd=<repo root> and a Python that has the backend
    deps installed. Their config (MySQL / KingStar) is injected from
    ``<repo>/backend/.env`` by ``_run_backend_script`` — no repo-root .env
    is required. Honors SENTIMENT_BACKEND_DIR / SENTIMENT_BACKEND_PYTHON.
    """
    here = Path(__file__).resolve()
    candidates: List[Path] = []
    if os.environ.get("SENTIMENT_BACKEND_DIR"):
        candidates.append(Path(os.environ["SENTIMENT_BACKEND_DIR"]))
    cur = here
    for _ in range(6):
        if (cur / "backend" / "analysis" / "analyzer_runner.py").exists():
            candidates.append(cur)
            break
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    proj = candidates[0] if candidates else here.parent.parent.parent
    py = os.environ.get("SENTIMENT_BACKEND_PYTHON")
    if not py:
        if os.name == "nt":
            cand = proj / ".venv" / "Scripts" / "python.exe"
        else:
            cand = proj / ".venv" / "bin" / "python"
        py = str(cand) if cand.exists() else sys.executable
    return str(proj), py


def _backend_env_file(proj: str) -> str:
    """Canonical env file for backend standalone scripts: ``<repo>/backend/.env``
    (the user-maintained config). Falls back to ``<repo>/.env`` for compat."""
    be = os.path.join(proj, "backend", ".env")
    return be if os.path.exists(be) else os.path.join(proj, ".env")


def _run_backend_script(script_rel: str, args: List[str], skin: Skin) -> int:
    """Run a backend standalone script as a subprocess, streaming its output.

    The standalone scripts load ``<repo>/.env`` at import time, but the real
    config lives in ``<repo>/backend/.env`` (user-maintained). We therefore
    read ``backend/.env`` and inject it into the subprocess environment, so the
    script picks up MySQL / KingStar config without a repo-root .env file.
    """
    from dotenv import dotenv_values
    proj, py = _resolve_backend_env()
    script = os.path.join(proj, script_rel)
    if not os.path.exists(script):
        skin.error(f"backend script not found: {script}")
        skin.info("set SENTIMENT_BACKEND_DIR to the repo root that contains backend/")
        return EXIT_USAGE
    env = dict(os.environ)
    env_file = _backend_env_file(proj)
    if os.path.exists(env_file):
        skin.status(f"[batch] env <- {env_file}")
        for k, v in dotenv_values(env_file).items():
            if v is not None:
                env[k] = v
    # make the repo root importable for ``import backend`` inside the script
    env["PYTHONPATH"] = proj + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [py, script, *args]
    skin.status(f"[batch] {' '.join(cmd)}")
    rc = subprocess.run(cmd, cwd=proj, env=env).returncode
    if rc != 0:
        skin.error(f"[batch] {script_rel} exited with code {rc}")
    return EXIT_OK if rc == 0 else rc


def _mysql_config_from_env(proj: str) -> Dict[str, Any]:
    """Build the MySQL connection dict for a direct (no-HTTP) read.

    Precedence: real environment vars > ``backend/.env`` > built-in defaults.
    Mirrors ``backend/config/config.py``'s ``MYSQL_CONFIG`` defaults so a bare
    checkout with only ``backend/.env`` works exactly like the backend does.
    """
    from dotenv import dotenv_values
    file_vals: Dict[str, str] = {}
    env_file = _backend_env_file(proj)
    if os.path.exists(env_file):
        file_vals = {k: v for k, v in dotenv_values(env_file).items() if v is not None}

    def pick(name: str, default: str) -> str:
        return os.environ.get(name) or file_vals.get(name) or default

    return {
        "host": pick("MYSQL_HOST", "10.253.50.134"),
        "port": int(pick("MYSQL_PORT", "3306")),
        "user": pick("MYSQL_USER", "root"),
        "password": pick("MYSQL_PASSWORD", "123456"),
        "database": pick("MYSQL_DATABASE", "Sentiment_analysis"),
        "charset": pick("MYSQL_CHARSET", "utf8mb4"),
    }


def _run_bond_yields(ns: argparse.Namespace, as_json: bool, skin: Skin) -> int:
    """Read bond yields straight from MySQL ``yield_data`` — no HTTP, no SSH.

    The ``bond-download`` step already imports the downloaded ChinaBond excel
    into MySQL, so *reading* the latest curve never needs paramiko / the xlsx
    file: we just query ``yield_data`` directly from this machine. Requires
    ``pymysql`` on the CLI interpreter (already present on the system python
    that the CLI is installed into).
    """
    try:
        import pymysql
    except ImportError:
        skin.error("pymysql is required for `batch bond-yields` (direct DB read).")
        skin.info(f'install: "{sys.executable}" -m pip install pymysql')
        return EXIT_USAGE

    proj, _ = _resolve_backend_env()
    cfg = _mysql_config_from_env(proj)
    table = os.environ.get("SENTIMENT_YIELD_TABLE", "yield_data")

    where: List[str] = []
    params: List[Any] = []
    if ns.date:
        where.append("date = %s")
        params.append(ns.date)
    if ns.start:
        where.append("date >= %s")
        params.append(ns.start)
    if ns.end:
        where.append("date <= %s")
        params.append(ns.end)
    if not where:  # default: latest available trading day
        where.append("date = (SELECT MAX(date) FROM %s)" % table)
    sql_where = " AND ".join(where)
    order = ("FIELD(period,'3M','6M','1Y','2Y','3Y','5Y','7Y','10Y','30Y','3月','6月',"
             "'1年','2年','3年','5年','7年','10年','30年')")
    sql = (f"SELECT date, period, value FROM {table} WHERE {sql_where} "
           f"ORDER BY date, {order}")

    try:
        conn = pymysql.connect(**cfg, connect_timeout=10)
    except Exception as exc:
        emit(503, {"error": f"MySQL connect failed: {exc}",
                   "host": cfg["host"], "database": cfg["database"]},
             "batch bond-yields", as_json, skin)
        return 1
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    data = [
        {"date": str(d), "period": str(p), "value": (float(v) if v is not None else None)}
        for d, p, v in rows
    ]
    emit(200, data, "batch bond-yields", as_json, skin)
    if not as_json and not rows:
        skin.info("[batch] no rows — has bond-download imported any data yet?")
    return EXIT_OK


def _ssh_stream(client, cmd: str, skin: Skin, timeout: int = 900) -> int:
    """Run ``cmd`` on an open SSH client, stream merged output, return exit status."""
    import time
    transport = client.get_transport()
    if transport is None:
        skin.error("[batch/ssh] no transport")
        return 1
    chan = transport.open_session()
    chan.settimeout(5)
    chan.exec_command(cmd)
    out = sys.stdout
    deadline = time.time() + timeout
    while True:
        if chan.exit_status_ready():
            while chan.recv_ready():
                _dump(chan.recv(65536), out)
            while chan.recv_stderr_ready():
                _dump(chan.recv_stderr(65536), sys.stderr)
            break
        if chan.recv_ready():
            _dump(chan.recv(65536), out)
        elif chan.recv_stderr_ready():
            _dump(chan.recv_stderr(65536), sys.stderr)
        else:
            if time.time() > deadline:
                skin.error("[batch/ssh] timed out")
                try:
                    chan.close()
                except Exception:
                    pass
                return 1
            time.sleep(0.05)
    try:
        return chan.recv_exit_status()
    except Exception:
        return 0


def _dump(data, stream) -> None:
    """Write bytes/str to a stream, tolerating buffer-less wrappers."""
    try:
        if isinstance(data, (bytes, bytearray)):
            stream.buffer.write(data)
            stream.buffer.flush()
        else:
            stream.write(data)
            stream.flush()
    except Exception:
        try:
            text = data.decode("utf-8", "replace") if isinstance(data, (bytes, bytearray)) else data
            stream.write(text)
            stream.flush()
        except Exception:
            pass


def _run_backend_script_ssh(script_rel: str, args: List[str], skin: Skin) -> int:
    """Run a backend standalone script on the REMOTE server via SSH + docker exec.

    Used by ``sentiment batch bond-download --ssh``: the ChinaBond download
    only succeeds from the server's egress IP (local runs hit ChinaBond's HTML
    login wall). We SSH into the server and run the script inside the
    ``sentiment-backend`` docker container (which has requests + the backend
    package), without modifying any server file.

    Credentials come from env vars (never hardcoded):
      SENTIMENT_BOND_SSH_HOST       (default 10.253.50.112)
      SENTIMENT_BOND_SSH_PORT       (default 22)
      SENTIMENT_BOND_SSH_USER       (default admin)
      SENTIMENT_BOND_SSH_PASS       (required; prompt via getpass if unset)
      SENTIMENT_BOND_SSH_CONTAINER (default sentiment-backend)
      SENTIMENT_BOND_SSH_APP_DIR   (default /app)
    """
    # paramiko is an optional dep, lazily imported only for --ssh. The CLI is
    # expected to run from sentiment-cli/.venv (which also has paramiko), so a
    # plain ``import paramiko`` just works. As a fallback for a CLI running on
    # a *different* interpreter, also probe sentiment-cli/.venv's site-packages.
    _cli_venv_sp = (Path(__file__).resolve().parents[1]
                     / ".venv" / "Lib" / "site-packages")
    if _cli_venv_sp.is_dir() and str(_cli_venv_sp) not in sys.path:
        sys.path.insert(0, str(_cli_venv_sp))
    try:
        import paramiko
    except ImportError:
        skin.error("paramiko is required for --ssh mode.")
        skin.info("install it into the SAME python that runs the CLI:")
        skin.info(f'  "{sys.executable}" -m pip install "paramiko>=3.0"')
        return EXIT_USAGE

    host = os.environ.get("SENTIMENT_BOND_SSH_HOST", "10.253.50.112")
    port = int(os.environ.get("SENTIMENT_BOND_SSH_PORT", "22"))
    user = os.environ.get("SENTIMENT_BOND_SSH_USER", "admin")
    password = os.environ.get("SENTIMENT_BOND_SSH_PASS")
    if not password:
        import getpass
        password = getpass.getpass(f"SSH password for {user}@{host}: ")
    container = os.environ.get("SENTIMENT_BOND_SSH_CONTAINER", "sentiment-backend")
    app_dir = os.environ.get("SENTIMENT_BOND_SSH_APP_DIR", "/app")

    py = f"{app_dir}/.venv/bin/python"
    remote = (f"docker exec -w {app_dir} -e PYTHONPATH={app_dir} "
              f"{container} {py} {script_rel} {' '.join(args)}")
    skin.status(f"[batch/ssh] {user}@{host}:{port}  ->  {remote}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(host, port=port, username=user,
                      password=password, timeout=20)
    except Exception as exc:
        skin.error(f"[batch/ssh] connect failed: {exc}")
        return 1
    try:
        skin.status("[batch/ssh] connected; running remote script ...")
        rc = _ssh_stream(client, remote, skin, timeout=900)
        if rc != 0:
            skin.error(f"[batch/ssh] remote exited with code {rc}")
            return rc
        # verify the produced xlsx is a real Excel (PK magic), not an HTML wall
        verify = (
            f"docker exec {container} sh -c "
            f"'F=$(ls -t {app_dir}/data/*.xlsx 2>/dev/null | head -1); "
            f"[ -n \"$F\" ] && {{ echo FILE=$F; "
            f"ls -la --time-style=+%m-%d_%H:%M:%S \"$F\"; "
            f"echo MAGIC=; head -c 16 \"$F\" | od -A n -t x1 | head -1; }} "
            f"|| echo NO_XLSX'"
        )
        skin.status("[batch/ssh] verifying output ...")
        _ssh_stream(client, verify, skin, timeout=30)
    finally:
        client.close()
    return EXIT_OK


def cmd_batch(argv: List[str], skin: Skin, force_json: bool = False) -> int:
    """Wrap backend standalone batch scripts: analyze / bond-download / bond-yields."""
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(
            "usage: sentiment batch <subcommand> [args] [--ssh]\n"
            "  analyze        batch-analyze pending news "
            "(wraps backend/analysis/analyzer_runner.py)\n"
            "  bond-download  download ChinaBond yield excel + import to DB "
            "(wraps backend/tools/bond_downloader.py)\n"
            "  bond-yields    read the yield curve straight from MySQL "
            "(no HTTP, no SSH, no xlsx)\n"
            "      add --ssh to run on the server via SSH+docker exec "
            "(ChinaBond egress only works from the server IP;\n"
            "      local runs hit ChinaBond's HTML login wall). "
            "Credentials read from SENTIMENT_BOND_SSH_* env vars.\n"
        )
        return EXIT_OK if argv else EXIT_USAGE
    sub = argv[0]
    rest = argv[1:]
    if sub == "analyze":
        rest = list(rest)
        if "--ssh" in rest:
            rest.remove("--ssh")
            skin.info("[batch] analyze runs locally (direct KingStar); --ssh ignored")
        p = argparse.ArgumentParser(prog="sentiment batch analyze")
        p.add_argument("--max-concurrent", type=int, default=10)
        p.add_argument("--batch-size", type=int, default=100)
        p.add_argument("--limit", type=int, default=1000)
        p.add_argument("--mode", default="model_missing",
                       choices=["model_missing", "force_rerun"])
        p.add_argument("--start-time", default=None)
        p.add_argument("--end-time", default=None)
        p.add_argument("--news-ids", default=None,
                       help="comma-separated news ids")
        try:
            ns = p.parse_args(rest)
        except SystemExit as exc:
            return int(exc.code or 0)
        args: List[str] = []
        if ns.max_concurrent != 10:
            args += ["--max-concurrent", str(ns.max_concurrent)]
        if ns.batch_size != 100:
            args += ["--batch-size", str(ns.batch_size)]
        if ns.limit != 1000:
            args += ["--limit", str(ns.limit)]
        if ns.mode != "model_missing":
            args += ["--mode", ns.mode]
        if ns.start_time:
            args += ["--start-time", ns.start_time]
        if ns.end_time:
            args += ["--end-time", ns.end_time]
        if ns.news_ids:
            args += ["--news-ids", ns.news_ids]
        return _run_backend_script(
            "backend/analysis/analyzer_runner.py", args, skin)
    if sub == "bond-download":
        rest2 = list(rest)
        use_ssh = False
        if "--ssh" in rest2:
            use_ssh = True
            rest2.remove("--ssh")
        p = argparse.ArgumentParser(prog="sentiment batch bond-download")
        p.add_argument("--excel-path", default=None)
        p.add_argument("--days", type=int, default=365)
        p.add_argument("--gjqx", default="0")
        p.add_argument("--locale", default="zh_CN")
        p.add_argument("--name-type", default="1")
        try:
            ns = p.parse_args(rest2)
        except SystemExit as exc:
            return int(exc.code or 0)
        args = []
        if ns.excel_path:
            args += ["--excel-path", ns.excel_path]
        if ns.days != 365:
            args += ["--days", str(ns.days)]
        if use_ssh and ns.days == 365:
            skin.info("[batch/ssh] --days not given; defaulting to 3 "
                      "(not 365) to avoid a full-year pull on the server")
            args += ["--days", "3"]
        if ns.gjqx != "0":
            args += ["--gjqx", ns.gjqx]
        if ns.locale != "zh_CN":
            args += ["--locale", ns.locale]
        if ns.name_type != "1":
            args += ["--name-type", ns.name_type]
        if use_ssh:
            return _run_backend_script_ssh(
                "backend/tools/bond_downloader.py", args, skin)
        return _run_backend_script(
            "backend/tools/bond_downloader.py", args, skin)
    if sub == "bond-yields":
        p = argparse.ArgumentParser(prog="sentiment batch bond-yields")
        p.add_argument("--date", default=None,
                       help="exact trading day YYYY-MM-DD (default: latest)")
        p.add_argument("--start", default=None, help="range start YYYY-MM-DD")
        p.add_argument("--end", default=None, help="range end YYYY-MM-DD")
        try:
            ns = p.parse_args(rest)
        except SystemExit as exc:
            return int(exc.code or 0)
        return _run_bond_yields(ns, force_json, skin)
    skin.error(f"unknown batch subcommand '{sub}'")
    return EXIT_USAGE


def dispatch(rest: List[str], config: Config, client: Client, spec: Spec,
             skin: Skin, force_json: bool,
             explicit_base_url: Optional[str] = None,
             explicit_timeout: Optional[str] = None) -> int:
    if not rest or rest[0] in ("help", "-h", "--help"):
        print_help(spec, skin)
        return EXIT_OK
    cmd = rest[0]
    tail = rest[1:]

    if cmd == "version":
        sys.stdout.write(f"{NAME} {__version__}\n")
        return EXIT_OK
    if cmd == "describe":
        return cmd_describe(spec, config, client, tail, skin)
    if cmd == "health":
        return cmd_health(client, force_json, skin)
    if cmd == "openapi":
        return cmd_openapi(config, client, tail, skin)
    if cmd == "groups":
        return cmd_groups(spec, skin)
    if cmd == "gaps":
        return cmd_gaps(force_json, skin)
    if cmd == "call":
        return cmd_call(client, tail, skin, force_json)
    if cmd == "config":
        return cmd_config(tail, config, skin)

    # dynamic: <group> <operation>
    if cmd in spec.groups:
        if not tail or tail[0] in ("-h", "--help"):
            skin.info(f"group '{cmd}' operations:")
            for op in spec.groups[cmd]:
                sys.stdout.write(f"  {cmd} {op.name:<24} {op.method:<5} {op.summary}\n")
            return EXIT_OK if tail else EXIT_USAGE
        op = spec.find(cmd, tail[0])
        if not op:
            skin.error(f"unknown operation '{tail[0]}' in group '{cmd}'")
            return EXIT_USAGE
        # Auto-route to the backend most likely to succeed for this command,
        # unless the user pinned an explicit --base-url (honored as-is).
        if explicit_base_url is None:
            chosen = pick_reachable(backend_candidates(op), config.use_proxy)
            if chosen != config.base_url:
                config.base_url = chosen.rstrip("/")
                client = Client(config)
            if chosen == LOCAL_BACKEND:
                skin.status(
                    f"[backend] auto-selected {chosen} for '{op.key}' "
                    f"(server proxy down / local works)")
        # Slow LLM/compute commands: bump the default client timeout from
        # 30s to DEFAULT_TIMEOUT_SLOW ONLY when the user did not pass an
        # explicit --timeout (which is always honored as-is).
        if explicit_timeout is None and op.key in _SLOW_TIMEOUT_OPS:
            if config.timeout != DEFAULT_TIMEOUT_SLOW:
                config.timeout = DEFAULT_TIMEOUT_SLOW
                client = Client(config)
                skin.status(
                    f"[timeout] {op.key} default raised to {DEFAULT_TIMEOUT_SLOW:.0f}s "
                    f"(slow LLM/compute command)")
        return run_operation(op, tail[1:], client, skin, force_json,
                              base_is_local=_is_loopback(config.base_url))

    skin.error(f"unknown command '{cmd}'. Run '{NAME} help' or '{NAME} groups'.")
    return EXIT_USAGE


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    load_dotenv()  # must run before Config reads SENTIMENT_* env vars
    try:
        gopts, rest = split_globals(argv)
    except UsageError as exc:
        sys.stderr.write(f"usage error: {exc}\n")
        return EXIT_USAGE

    # No sub-command -> REPL.
    if not rest:
        from .repl import run_repl
        try:
            config, client, spec, skin, force_json = make_context(gopts)
        except FileNotFoundError:
            sys.stderr.write("openapi spec not found; run 'sentiment openapi --refresh'\n")
            return EXIT_FAILURE
        return run_repl(config, client, spec, skin, no_banner=bool(gopts.get("no-banner")))

    try:
        config, client, spec, skin, force_json = make_context(gopts)
    except FileNotFoundError:
        sys.stderr.write("openapi spec not found; run 'sentiment openapi --refresh'\n")
        return EXIT_FAILURE
    try:
        return dispatch(rest, config, client, spec, skin, force_json,
                       explicit_base_url=gopts.get("base-url"),
                       explicit_timeout=gopts.get("timeout"))
    except KeyboardInterrupt:
        skin.warning("interrupted")
        return EXIT_OK
    except UsageError as exc:
        skin.error(str(exc))
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
