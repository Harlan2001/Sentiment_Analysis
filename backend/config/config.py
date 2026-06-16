"""
系统配置中心
"""
from pathlib import Path
import os
import httpx
from dotenv import load_dotenv
from typing import Optional, Dict

# 基础路径配置
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"

# 数据文件路径
ANALYSIS_PATH = DATA_DIR / "analysis.jsonl"
BOND_XLSX = DATA_DIR / "GovernmentBonds.xlsx"
INDEX_PATH = DATA_DIR / "faiss.index"
ID_MAP_PATH = DATA_DIR / "id_map.json"
YIELD_INDEX_DIR = DATA_DIR / "yield_indices"

# 工具函数：环境变量读取
def _get_env_str(name: str) -> str:
    return os.getenv(name, "").strip()

def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}

# ====================== 代理配置 ======================
def is_outbound_proxy_enabled() -> bool:
    raw_value = _get_env_str("OUTBOUND_PROXY_ENABLED")
    return _is_truthy(raw_value) if raw_value else True

def get_outbound_proxy_url() -> Optional[str]:
    if not is_outbound_proxy_enabled():
        return None
    return _get_env_str("OUTBOUND_PROXY_URL") or _get_env_str("HTTPS_PROXY") or _get_env_str("HTTP_PROXY")

def get_requests_proxies() -> Optional[Dict[str, str]]:
    proxy = get_outbound_proxy_url()
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}

# OpenAI 客户端
def create_openai_http_client() -> Optional[httpx.Client]:
    proxy_url = get_outbound_proxy_url()
    return httpx.Client(proxy=proxy_url) if proxy_url else None

def create_openai_async_http_client() -> Optional[httpx.AsyncClient]:
    proxy_url = get_outbound_proxy_url()
    return httpx.AsyncClient(proxy=proxy_url) if proxy_url else None

# ====================== 数据库配置 ======================
# 复用工具函数读取环境变量，消除重复逻辑
MYSQL_CONFIG = {
    "host": _get_env_str("MYSQL_HOST") or "10.253.50.134",
    "port": int(_get_env_str("MYSQL_PORT") or 3306),
    "user": _get_env_str("MYSQL_USER") or "root",
    "password": _get_env_str("MYSQL_PASSWORD") or "123456",
    "database": _get_env_str("MYSQL_DATABASE") or "Sentiment_analysis",
    "charset": _get_env_str("MYSQL_CHARSET") or "utf8mb4",
    "autocommit": _is_truthy(_get_env_str("MYSQL_AUTOCOMMIT") or "true"),
}

# 期限映射（动态生成反向映射，消除冗余变量）
PERIOD_MAP = {
    "3月": "3M", "6月": "6M", "1年": "1Y", "2年": "2Y",
    "3年": "3Y", "5年": "5Y", "7年": "7Y", "10年": "10Y", "30年": "30Y",
}
PERIOD_REVERSE_MAP = {v: k for k, v in PERIOD_MAP.items()}

# ====================== 分析模型配置 ======================
ANALYSIS_MODEL_PRIORITY = ["doubao", "deepseek", "qwen", "default"]

# 简化注册表
ANALYSIS_MODEL_REGISTRY = {
    "doubao": {"provider_model": "volcengine/doubao-seed-2-0-code-preview-260215", "description": "豆包模型", "enabled": True},
    "deepseek": {"provider_model": "aliyun/deepseek-v4-pro", "description": "DeepSeek 模型", "enabled": True},
    "qwen": {"provider_model": "aliyun/qwen3.6-flash", "description": "Qwen 模型", "enabled": True},
}

def get_default_analysis_model_name() -> str:
    return _get_env_str("ANALYSIS_MODEL_NAME") or "doubao"

def get_analysis_model_info(model_name: str) -> dict:
    return ANALYSIS_MODEL_REGISTRY.get(model_name, ANALYSIS_MODEL_REGISTRY["doubao"])

def get_analysis_model_name_by_provider_model(provider_model: str) -> str:
    for short_name, info in ANALYSIS_MODEL_REGISTRY.items():
        if info["provider_model"] == provider_model:
            return short_name
    return provider_model

# ====================== 新闻源配置 ======================
NEWS_SOURCES = {
    "cls": "财联社", "wechat": "微信公众号",
    "wallstreetcn": "华尔街见闻", "yicai": "第一财经",
}
DEFAULT_NEWS_SOURCES = []
