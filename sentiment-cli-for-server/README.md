# sentiment-cli — **for-server build** ⚠️

> **This is a pruned fork for the server agent.** It is derived from the full
> `sentiment-cli` but **only exposes the commands needed on the server**:
> `news` (all) · `factors` (all) · `forecast` (all) · `macro` (all) ·
> `strategy` (`snapshot`+`portfolio`) · `recommend` (all) ·
> `change` (`snapshots`+`compare`) · `graph` (`job-by-news`).
> Hidden by design: `chat` · `report` · `pipeline` · `dashboard` · `auth` ·
> `batch` · and `strategy trigger/sse` · `change trigger` · `graph save`.
> Default backend = `http://10.253.50.112` (nginx :80). No token needed.
> Authoritative command list & flags: `sentiment describe --json` (see `SKILL.md`).
> The rest of this README describes the full-CLI conventions — they still apply
> to the retained commands, but ignore any group/command not in the list above.

# sentiment-cli

An **agent-native CLI** over the *Bond Yield / Sentiment Analysis* backend.

It wraps the running FastAPI backend (46 endpoints) as a structured, deterministic
command-line tool that AI agents can drive with zero external docs. Built with the
[cli-anything](https://github.com/HKUDS) conventions: OpenAPI-driven commands,
`--json` on everything, a `describe` self-description, an interactive REPL, and
deterministic exit codes.

- **Zero third-party dependencies** — Python standard library only (3.8+).
- **Always in sync** — commands are generated from the backend's `/openapi.json`.
- **The backend does the real work** — embedding models, MySQL, internal APIs
  and the LLM gateway stay server-side; this CLI is a thin, safe front-end.

## Quick start

```bash
# no install — run as a module from this directory
python -m sentiment_cli                     # interactive REPL
python -m sentiment_cli describe --json     # capability map (46 ops)
python -m sentiment_cli --json news list    # latest news
python -m sentiment_cli health              # backend probe

# or install the console script
pip install -e .
sentiment groups
```

Default backend `http://10.253.50.112:8000`. Change it:

```bash
sentiment --base-url http://host:8000 health
export SENTIMENT_BASE_URL=http://host:8000
sentiment config set --base-url http://host:8000     # persist to ~/.sentiment/config.json
```

## Local backend (127.0.0.1:8001)

The default backend `10.253.50.112:8000` is a shared remote container
that is frequently down (crash-loop) and **must not be modified**. For
local development, testing, or running the CLI against live data, start the
backend yourself on `127.0.0.1:8001`.

```bash
# MUST use the PROJECT-ROOT .venv (Py3.11, has uvicorn/httpx/pymysql/
# weasyprint/playwright). Do NOT use sentiment-cli/.venv — it is the CLI
# client only and has no uvicorn, so 8001 would never come up.
cd "/d/WorkSpace/CLI conversion project/Sentiment Analysis"
PYTHONPATH=sentiment-cli/stubs .venv/Scripts/python.exe -m uvicorn backend.app:app \
    --host 127.0.0.1 --port 8001
```

Three non-obvious constraints (skip any and it breaks):

1. **`PYTHONPATH=sentiment-cli/stubs` is required.** It loads two local
   stubs so the backend imports cleanly on this machine:
   - `sentiment-cli/stubs/weasyprint/__init__.py` — placeholder. Real
     `weasyprint` cannot import on Windows (missing Pango/cairo native
     libs); the stub lets `from weasyprint import HTML` pass and raises a
     clear error on use. (Server-side `report` PDF is then done via the
     CLI `--local` Playwright path — see below.)
   - `sentiment-cli/stubs/sitecustomize.py` — auto-runs at Python startup
     and rewrites the upstream `proxy={}` dict to `trust_env=False`. The
     upstream code uses `proxy={}`, which `httpx` 0.28 rejects
     (`'dict' object has no attribute 'url'`); on a machine with no proxy
     this would crash at import time. This is the correct implementation of
     the upstream intent (don't fall back to env proxy).
2. **Startup takes ~45–68 s** — wait for MySQL to connect and the faiss
   vector index to load before probing. Verify it is alive with:
   ```bash
   curl http://127.0.0.1:8001/health          # -> 200
   curl http://127.0.0.1:8001/openapi.json     # -> 200, 48 paths
   ```
3. **`cli.py` already clears `NODE_OPTIONS`** at module load (top-level
   `os.environ.pop("NODE_OPTIONS", None)`). This prevents WorkBuddy's
   injected node flags from poisoning Playwright's bundled node driver when
   the CLI renders a PDF locally — no action needed from you.

Then point the CLI at your local backend:

```bash
export SENTIMENT_BASE_URL=http://127.0.0.1:8001
sentiment --base-url http://127.0.0.1:8001 health
```

To run a test script against it without the backend dying at a session
boundary (a stray `uvicorn` can also grab port 8001), launch uvicorn as
a child inside one background shell and kill it when done:

```bash
( PYTHONPATH=sentiment-cli/stubs .venv/Scripts/python.exe -m uvicorn \
      backend.app:app --host 127.0.0.1 --port 8001 & UVPID=$!
  for i in $(seq 1 40); do curl -s -o /dev/null http://127.0.0.1:8001/health && break; sleep 3; done
  python your_test_script.py
  kill $UVPID )
```

### `.env` file support

The CLI also reads `SENTIMENT_*` variables from a `.env` file (standard
library only — **no `python-dotenv` dependency**). Copy `.env.example`
to `.env` and drop it in any one of:

```text
./.env                      # current working directory
sentiment-cli/.env          # this project root (where .env.example ships)
sentiment_cli/.env          # the python package dir
~/.sentiment/.env           # user config dir
```

Only `.env` files that contain at least one `SENTIMENT_` key are loaded,
so the backend's own `.env` (MySQL / kingstar / feishu / ...) is never
ingested. Existing shell environment variables are **not** overridden.
Precedence: `--flag` > `SENTIMENT_*` (this file / shell) >
`~/.sentiment/config.json` > built-in default.

## Command surface

`news · factors · forecast · macro · strategy · recommend · change · chat ·
report · pipeline · graph · dashboard · auth`

Run `sentiment groups` for the full list, `sentiment <group>` to list a group,
and `sentiment <group> <op> --help` for an operation's parameters.

Builtins: `describe [--check]`, `groups`, `health`, `openapi [--refresh]`,
`call M PATH ...`, `config show|set|path`, `version`.

## Output & exit codes

`--json` → `{"ok":bool,"status":int,"command":str,"data":any}`.

`0` ok · `1` unreachable/failure · `2` usage · `3` capability gap · `4` backend error.

## Binary / file responses

Endpoints that return a **file** (e.g. `report download` → PDF) are
detected by `Content-Type` (`application/pdf`, `image/*`, …) or
`Content-Disposition: attachment`. The bytes are **never** decoded as
text/JSON (that would corrupt them); instead they are written to disk
and the envelope reports the saved path + size:

```bash
sentiment report download --filename 2026-07-15.pdf -o report.pdf
# → saved NNN bytes -> report.pdf   (or JSON: {"saved_to":..., "bytes":...})

# any operation can save a binary body with -o / --output:
sentiment call GET /sapi/report/files/2026-07-15.pdf -o report.pdf
```

Without `-o` the file name defaults to the last URL segment.

## Local report generation (bypass the server)

`report generate` / `report download` can run **locally** with `--local`,
reusing the server's frontend (`:80`) + backend (`:8000`) **data** to
render the prediction page, but printing the PDF with the **local** browser
— bypassing the broken server `/sapi/report/*` endpoints (read-only
w.r.t. the server, no container/volume change). Requires the `playwright`
Python package (`pip install playwright`); the browser itself is auto-detected
from a system Microsoft Edge / Google Chrome (no `playwright install` needed).

```bash
# generate the prediction PDF locally (renders server data, prints via local browser)
sentiment report generate --local --report-date 2026-07-15
#   -> writes data/pdf/2026-07-15.pdf on THIS machine

# download a report PDF, entirely local:
sentiment report download --local --filename 2026-07-15.pdf -o report.pdf
#   -> if the local file is missing, it AUTO-FALLS-BACK to `report generate
#      --local` (re-render from server data with the local browser), then
#      reads it back. One command does generate + download.
```

**Why `--local`?** The server's `report download` endpoint
(`/sapi/report/files/{filename}`) returns HTTP 500 — the deployed
`/app/data/pdf/*` is mismatched against the path `get_pdf_file` reads,
and the volume is read-only. We don't modify the backend. `--local` is the
supported workaround and now runs end-to-end on your machine (verified:
830 KB PDF for `2026-07-15`).

A local Chromium-based browser is used automatically, in this priority:

1. `SENTIMENT_REPORT_CHROME` env (explicit `chrome`/`msedge` exe path)
2. **A local Chromium build at `D:/chromium/*/chrome-win/chrome.exe`**
   (auto-detected — used instead of system Edge by default)
3. Playwright's bundled chromium (`playwright install chromium`)
4. A system Microsoft Edge / Google Chrome (auto-detected)

Point at a
different frontend with `SENTIMENT_REPORT_FRONTEND_URL`.

## Chat via the KingStar gateway (direct, bypassing `/sapi/chat`)

`chat ask` prefers a **client-side direct call** to the KingStar OpenAI-
compatible gateway when `SENTIMENT_CHAT_GATEWAY_URL` and
`SENTIMENT_CHAT_GATEWAY_KEY` are configured (e.g. in `.env`). This
bypasses the server's `/sapi/chat`, which currently times out because the
server container cannot egress to the gateway. Falls back to the OpenAPI
`/sapi/chat` call when the gateway env vars are absent.

```bash
sentiment chat ask --messages '[{"role":"user","content":"..."}]' --stream false
```


## Docs

- `SKILL.md` — self-contained skill descriptor (agent discovery).
- `AGENTS.md` — how an agent should operate the CLI.
- `NOT_IMPLEMENTED.md` — capabilities the CLI does **not** wrap (auth, push, scheduler, batch, ops).
- `TEST.md` — test plan and results (62 passed, 2 skipped; the 2 local-PDF render tests need the `playwright` Python package).

## Not implemented / 未实现功能

The 46 REST endpoints are 100% covered. The table below also lists two
**local-deployment-unavailable** capabilities (CLI wraps them, but the local
backend lacks the router / model) — see `NOT_IMPLEMENTED.md` §6.
Query the live list any time with:

```bash
sentiment gaps                 # human-readable
sentiment gaps --json         # machine-readable (same shape as --json envelope)
sentiment describe --json     # also carries a "not_implemented" array
```

Summary (see `NOT_IMPLEMENTED.md` for reasons / impact / workarounds):

| gap | capability | status | priority |
|-----|------------|--------|----------|
| `auth-token-injection` | Bearer token actually sent to backend | not_implemented | medium |
| `push-feishu` | 飞书每日 PDF 推送 | not_implemented | low |
| `push-weixin` | 公众号草稿推送 (Playwright) | not_implemented | low |
| `push-pdf` | PDF 推送 | not_implemented | low |
| `scheduler` | 定时调度器 (server-only) | not_implemented | low |
| `batch-analyzer` | 新闻批量分析 (analyzer_runner) | not_implemented | low |
| `batch-snapshot` | 快照生成脚本 | not_implemented | low |
| `batch-bond-download` | 债券数据下载 (bond_downloader) | not_implemented | medium |
| `dashboard-local-unavailable` | Dashboard 行为分析/会话清理 (本机缺 router, **命令已从 CLI 隐藏**) | not_implemented | medium |
| `pipeline-run-embedding-model` | Pipeline 完整跑通 (本机缺 all-MiniLM-L6-v2, **命令已从 CLI 隐藏**) | not_implemented | medium |
| `deploy-ops` | 部署/运维脚本 | out_of_scope | n/a |

## Tests

```bash
pip install -e ".[test]"
python -m pytest -v
```

E2E tests run against a **local stub backend** (loopback `http.server`), so they
pass with no network and no live backend — fully deterministic.
(62 passed, 2 skipped. The 2 local-PDF render tests require the `playwright`
Python package — `pip install playwright`; they auto-use a system
Edge/Chrome, no `playwright install` needed.)
