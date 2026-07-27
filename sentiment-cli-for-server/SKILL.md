---
name: sentiment-cli
description: >-
  Agent-native CLI for the Bond Yield / Sentiment Analysis backend, **for-server build**.
  Use when an AI agent running on the server needs to query bond-market news, factors,
  macro signals, yield forecasts, AI strategy/target recommendations, change snapshots,
  or knowledge-graph jobs — all over the backend's HTTP API. This build is a
  **pruned fork**: only the commands listed under "Retained commands" are exposed;
  chat / report / pipeline / dashboard / auth / batch and the non-retained
  sub-operations are intentionally hidden. Every command supports --json;
  `describe --json` is the authoritative live schema (flags included).
version: 0.1.0-for-server
keywords: [bond, sentiment, news, factor, macro, forecast, strategy, recommendation, change, graph, cli-anything, agent-native, openapi, for-server]
---

# sentiment — agent-native CLI for the Bond Yield backend (for-server build)

`sentiment` wraps the running **Bond Yield Backend** (FastAPI) as a structured,
machine-parseable CLI for AI agents. It is **OpenAPI-driven**: every command is
generated from the backend's own `/openapi.json`, so the CLI never drifts from
the API. Zero third-party dependencies (Python stdlib only).

> **This is the `for-server` build.** It is a pruned fork of the full `sentiment-cli`
> intended to run **on the server** (as a skill the platform agent can call).
> Only the commands below are exposed. Hidden by design: `chat`, `report`,
> `pipeline`, `dashboard`, `auth`, `batch`, and the non-retained
> sub-operations (`strategy trigger`/`sse`, `change trigger`, `graph save`).
> To see the live, complete schema (incl. every flag) run `sentiment describe --json`.

## Server background

- **Default backend**: `http://10.253.50.112` (nginx :80, which reverse-proxies
  `/sapi/*` to the backend on :8000). Override with `--base-url`, `SENTIMENT_BASE_URL`,
  or persist via `sentiment config set --base-url ...`.
- **No auth / token needed**: the read endpoints are public on the internal network
  (verified: plain GET to `/sapi/news`, `/sapi/factors`, `/sapi/macro/signal`,
  `/sapi/forecast`, `/sapi/strategy/snapshot`, `/sapi/change/snapshots`,
  `/sapi/ai-strategy-recommendation/latest`, `/sapi/graph-augment/job-by-news/{id}`
  all return 200 without a token). Do **not** set `--token` unless the server
  later requires it.
- **Untested against the live server** by design (build-time constraint): the
  command surface was verified and the retained endpoints were read-probed to 200.
  Treat first live runs as smoke tests.

## Install / run

```bash
# From the package directory (no install needed):
python -m sentiment_cli <command> ...

# Or install as a console script:
pip install -e .
sentiment <command> ...
```

## First moves for an agent

```bash
sentiment describe --json     # AUTHORITATIVE live schema of all retained operations
sentiment groups              # list retained command groups & operations
sentiment health              # backend health probe (via default nginx :80)
sentiment gaps                # list intentionally hidden capabilities
```

## Invocation shape

```
sentiment [global-flags] <group> <operation> [--flags]
sentiment <builtin> [args]
sentiment                        # no args -> interactive REPL
```

Global flags: `--base-url URL`, `--token TOKEN`, `--timeout SEC`,
`--use-proxy`, `--json`, `--spec PATH`.

Path/query/body parameters are all exposed as `--flags` (dashes for underscores).
Whole-body override: `--body-json '{...}'`. Raw escape hatch:
`sentiment call <METHOD> <path> [--query k=v] [--body '{...}']`.

## Retained commands (the only ones in this build)

| Group | Operations | Maps to backend |
|---|---|---|
| `news` | `list`, `detail`, `yield`, `analyze`, `similar`, `sources`, `latest-trading-day`, `by-factor`, `yields` | `/sapi/news*`, `/sapi/factor/{code}/news`, `/sapi/yields` |
| `factors` | `list`, `by-category` | `/sapi/factors`, `/sapi/factors/by-category/{category}` |
| `forecast` | `latest`, `history` | `/sapi/forecast`, `/sapi/forecast/history` |
| `macro` | `signal`, `signal-logs` | `/sapi/macro/signal`, `/sapi/macro/signal/logs` |
| `strategy` | `snapshot`, `portfolio` | `/sapi/strategy/snapshot`, `/sapi/strategy/portfolio-analysis` |
| `recommend` | `analyze`, `latest`, `history`, `strategies` | `/sapi/ai-strategy-recommendation/*` |
| `change` | `snapshots`, `compare` | `/sapi/change/snapshots`, `/sapi/change/compare` |
| `graph` | `job-by-news` | `/sapi/graph-augment/job-by-news/{news_id}` |

Builtins (always available): `describe`, `health`, `openapi`, `groups`,
`gaps`, `call`, `config`, `version`, `help`, `repl`.

> Examples:
> ```bash
> sentiment news list --limit 20 --json
> sentiment news detail --news-id 14345
> sentiment factors by-category --category policy
> sentiment macro signal --factor-code MLF_RATE
> sentiment forecast latest
> sentiment strategy snapshot
> sentiment recommend latest
> sentiment change compare --version-id 50
> sentiment graph job-by-news --news-id 14345
> ```

## Intentionally hidden (not in this build)

Run `sentiment gaps` for the full machine-readable list. Summary:

- `chat ask` — conversational LLM endpoint (not needed for structured queries).
- `report generate` / `report download` — PDF report generation (out of scope).
- `strategy trigger` / `strategy sse` — triggering & streaming (not in retained set).
- `change trigger` — change-trigger analysis (not in retained set).
- `graph save` — persisting graph jobs (not in retained set).
- `pipeline run` — embedding pipeline (needs all-MiniLM model; out of scope).
- `dashboard *` (13 ops) — behavior/usage dashboards (out of scope).
- `auth login` / `auth status` — auth (endpoints are public; no login needed).
- `batch` — standalone `backend/tools/bond_downloader.py` subprocess (not a REST op; removed).

## Output & exit codes

`--json` prints a stable envelope: `{"ok":bool,"status":int,"command":str,"data":any}`.
Without `--json` the response body is pretty-printed and a status line goes to stderr.

| code | meaning |
|------|---------|
| 0 | success (HTTP 2xx) |
| 1 | unexpected failure / backend unreachable |
| 2 | usage error (bad/missing args) |
| 3 | partial / capability gap (`describe --check` when offline) |
| 4 | backend returned an error status (HTTP 4xx/5xx) |

## Notes for the calling agent

- Always prefer `sentiment describe --json` to discover exact flags for an operation
  before calling it — the schema is generated from the live backend spec.
- Path params are required (e.g. `--news-id`, `--factor-code`, `--category`,
  `--news-id` for graph). Missing required params yield HTTP 422 from the backend.
- LLM-backed operations (`news analyze`, `recommend analyze`) depend on the
  backend's KingStar gateway being reachable; they may be slower — the CLI
  auto-raises the timeout for known slow operations.
