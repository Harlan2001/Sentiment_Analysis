"""Configuration resolution for the sentiment CLI.

Precedence (highest first):
    1. explicit CLI flag (--base-url / --token / --timeout ...)
    2. environment variable (SENTIMENT_BASE_URL / SENTIMENT_TOKEN / ...)
       (these may also be supplied via a ``.env`` file — see load_dotenv)
    3. user config file  (~/.sentiment/config.json)
    4. built-in defaults

The backend paths already carry the ``/sapi`` prefix (they come straight from
the backend's OpenAPI document), so ``base_url`` must NOT include it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---- deterministic exit codes -------------------------------------------------
EXIT_OK = 0          # success (HTTP 2xx)
EXIT_FAILURE = 1     # unexpected failure / network unreachable / exception
EXIT_USAGE = 2       # bad arguments (argparse also uses 2)
EXIT_GAPS = 3        # partial / capability gap (e.g. describe --check found holes)
EXIT_BACKEND = 4     # backend returned an error status (HTTP 4xx / 5xx)

# Default backend URL. For the **for-server** build the agent runs ON the
# server, so the default points at the nginx front-end (port 80) which
# reverse-proxies /sapi/* to the backend (8000). Overridable via
# SENTIMENT_SERVER_BACKEND / --base-url / config file.
DEFAULT_BASE_URL = os.environ.get(
    "SENTIMENT_SERVER_BACKEND", "http://10.253.50.112")
DEFAULT_TIMEOUT = 30.0

CONFIG_DIR = Path(os.path.expanduser("~")) / ".sentiment"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _load_file() -> Dict[str, Any]:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def _unquote(value: str) -> str:
    """Strip a single layer of matching single/double quotes."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def load_dotenv() -> List[str]:
    """Load ``SENTIMENT_*`` variables from discovered ``.env`` files (stdlib only).

    Candidate locations, in order:
        1. ``<cwd>/.env``
        2. ``<cli-project>/.env``   (where ``.env.example`` ships)
        3. ``<repo-root>/.env``      (unified project config — backend + CLI)
        4. ``<package>/.env``        (sentiment_cli/.env)
        5. ``~/.sentiment/.env``       (user config dir)

    A ``.env`` file is only applied when it contains at least one
    ``SENTIMENT_`` key — this prevents accidentally ingesting the
    backend's own ``.env`` (MySQL / kingstar / feishu / ...).
    Existing shell environment variables are never overridden (dotenv default).

    Returns the list of ``.env`` paths that were actually loaded.
    """
    here = Path(os.getcwd()) / ".env"
    proj = Path(__file__).resolve().parent.parent / ".env"
    repo = Path(__file__).resolve().parent.parent.parent / ".env"
    pkg = Path(__file__).resolve().parent / ".env"
    user = CONFIG_DIR / ".env"
    loaded: List[str] = []
    for cand in (here, proj, repo, pkg, user):
        if not cand.is_file():
            continue
        try:
            text = cand.read_text(encoding="utf-8")
        except OSError:
            continue
        if "SENTIMENT_" not in text:
            continue  # not a CLI .env — ignore (e.g. the backend's .env)
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), _unquote(val.strip())
            if key.startswith("SENTIMENT_") and key not in os.environ:
                os.environ[key] = val
        loaded.append(str(cand))
    return loaded


class Config:
    """Resolved runtime configuration."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: Optional[float] = None,
        use_proxy: Optional[bool] = None,
    ):
        f = _load_file()

        self.base_url = (
            base_url
            or os.environ.get("SENTIMENT_BASE_URL")
            or f.get("base_url")
            or DEFAULT_BASE_URL
        ).rstrip("/")

        self.token = (
            token
            or os.environ.get("SENTIMENT_TOKEN")
            or f.get("token")
            or None
        )

        _t = (
            timeout
            if timeout is not None
            else os.environ.get("SENTIMENT_TIMEOUT")
            or f.get("timeout")
            or DEFAULT_TIMEOUT
        )
        try:
            self.timeout = float(_t)
        except (TypeError, ValueError):
            self.timeout = DEFAULT_TIMEOUT

        # By default bypass any system HTTP proxy: the backend lives on an
        # internal network and a local proxy (e.g. 127.0.0.1:7897) would break
        # reachability. Set use_proxy=True to honour the environment proxy.
        if use_proxy is not None:
            self.use_proxy = bool(use_proxy)
        elif os.environ.get("SENTIMENT_USE_PROXY") is not None:
            self.use_proxy = os.environ["SENTIMENT_USE_PROXY"].lower() in ("1", "true", "yes")
        elif "use_proxy" in f:
            self.use_proxy = bool(f["use_proxy"])
        else:
            self.use_proxy = False

        # ---- chat gateway (client-side direct call to KingStar, bypasses /sapi/chat) ----
        # Values are READ from the server's /opt/sentiment/.env (kingstar_*)
        # and configured into the local CLI environment (see .env.example).
        # When both are set, `chat ask` calls the OpenAI-compatible gateway
        # directly instead of proxying through the (currently broken) /sapi/chat.
        self.chat_gateway_url = (
            os.environ.get("SENTIMENT_CHAT_GATEWAY_URL")
            or f.get("chat_gateway_url")
            or None
        )
        self.chat_gateway_key = (
            os.environ.get("SENTIMENT_CHAT_GATEWAY_KEY")
            or f.get("chat_gateway_key")
            or None
        )
        self.chat_gateway_model = (
            os.environ.get("SENTIMENT_CHAT_MODEL")
            or f.get("chat_gateway_model")
            or "volcengine/doubao-seed-2-0-code-preview-260215"
        )

        # Optional path to a specific openapi.json (set by the CLI layer).
        self.spec_path: Optional[str] = None

    # ---- persistence ---------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url,
            "token": self.token,
            "timeout": self.timeout,
            "use_proxy": self.use_proxy,
            "chat_gateway_url": self.chat_gateway_url,
            "chat_gateway_key": self.chat_gateway_key,
            "chat_gateway_model": self.chat_gateway_model,
        }

    @staticmethod
    def save(values: Dict[str, Any]) -> Path:
        """Merge ``values`` into the on-disk config file and return its path."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        current = _load_file()
        current.update({k: v for k, v in values.items() if v is not None})
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(current, fh, ensure_ascii=False, indent=2)
        return CONFIG_FILE
