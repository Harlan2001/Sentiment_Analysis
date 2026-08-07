"""BondSense 工作台后端配置中心。"""

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent.parent
# 先复用旧系统环境；工作台自己的 .env 只作为可选覆盖。
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)


def _get_env_str(name: str) -> str:
    return os.getenv(name, "").strip()


def _get_first_env(*names: str) -> str:
    for name in names:
        value = _get_env_str(name)
        if value:
            return value
    return ""


def _require_first_env(*names: str) -> str:
    value = _get_first_env(*names)
    if not value:
        joined = " or ".join(names)
        raise RuntimeError(f"Missing required environment variable: {joined}")
    return value


def _get_env_int(name: str, default: int) -> int:
    value = _get_env_str(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc


API_PREFIX = _get_env_str("WORKBENCH_API_PREFIX") or "/api/workbench"
LEGACY_API_BASE_URL = _get_env_str("LEGACY_API_BASE_URL") or "http://127.0.0.1:8000"
LEGACY_API_TIMEOUT_SECONDS = _get_env_int("WORKBENCH_LEGACY_TIMEOUT_SECONDS", 180)
CONVERSATION_HISTORY_LIMIT = _get_env_int("WORKBENCH_CONVERSATION_HISTORY_LIMIT", 50)

CORS_ORIGINS = [
    origin.strip()
    for origin in (
        _get_env_str("WORKBENCH_CORS_ORIGINS")
        or "http://127.0.0.1:5173,http://localhost:5173"
    ).split(",")
    if origin.strip()
]

MYSQL_CONFIG = {
    "host": _require_first_env("WORKBENCH_MYSQL_HOST", "MYSQL_HOST"),
    "port": int(_get_first_env("WORKBENCH_MYSQL_PORT", "MYSQL_PORT") or "3306"),
    "user": _require_first_env("WORKBENCH_MYSQL_USER", "MYSQL_USER"),
    "password": _require_first_env("WORKBENCH_MYSQL_PASSWORD", "MYSQL_PASSWORD"),
    "database": _require_first_env("WORKBENCH_MYSQL_DATABASE", "MYSQL_DATABASE"),
    "charset": _get_first_env("WORKBENCH_MYSQL_CHARSET", "MYSQL_CHARSET") or "utf8mb4",
    "autocommit": True,
}

# 第一批工作台后端只允许操作测试库，防止误连旧系统业务库。
if MYSQL_CONFIG["database"] != "Sentiment_analysis_test":
    raise RuntimeError("Workbench backend only permits MYSQL database Sentiment_analysis_test")

