"""
系统配置中心
"""

import os
from pathlib import Path
from typing import Dict, Optional
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

# 基础路径配置
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"

# 数据文件路径
BOND_XLSX = DATA_DIR / "GovernmentBonds.xlsx"
INDEX_PATH = DATA_DIR / "faiss.index"
ID_MAP_PATH = DATA_DIR / "id_map.json"


# 工具函数：环境变量读取
def _get_env_str(name: str) -> str:
    return os.getenv(name, "").strip()


def _require_env_str(name: str) -> str:
    """读取必填配置，禁止回退到机器相关的真实密钥。"""
    value = _get_env_str(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_env_int(name: str, default: int) -> int:
    value = _get_env_str(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


# ====================== 日志配置 ======================
LOG_LEVEL = _get_env_str("LOG_LEVEL") or "INFO"
LOG_DIR = _get_env_str("LOG_DIR") or str(BASE_DIR / "logs")
LOG_MAX_DAYS = int(_get_env_str("LOG_MAX_DAYS") or "30")

# ====================== 本地快照配置 ======================
# 【临时兼容】SaaS 无法访问内网 API 时，使用本地快照文件替代实时 API 调用
# 使用前需在内网环境运行 scripts/generate_snapshot.py 生成快照文件
# 本地快照目录：默认 data/snapshots；可用 SNAPSHOT_DIR 环境变量覆盖
# （相对路径基于项目根目录解析，绝对路径直接使用）
_snapshot_dir_env = _get_env_str("SNAPSHOT_DIR")
if _snapshot_dir_env:
    SNAPSHOT_DIR = Path(_snapshot_dir_env)
    if not SNAPSHOT_DIR.is_absolute():
        SNAPSHOT_DIR = BASE_DIR / SNAPSHOT_DIR
else:
    SNAPSHOT_DIR = DATA_DIR / "snapshots"
USE_LOCAL_SNAPSHOT = _is_truthy(_get_env_str("USE_LOCAL_SNAPSHOT") or "false")


# ====================== 代理配置 ======================
def is_outbound_proxy_enabled() -> bool:
    raw_value = _get_env_str("OUTBOUND_PROXY_ENABLED")
    return _is_truthy(raw_value) if raw_value else True


def get_outbound_proxy_url() -> Optional[str]:
    if not is_outbound_proxy_enabled():
        return None
    return (
        _get_env_str("OUTBOUND_PROXY_URL")
        or _get_env_str("HTTPS_PROXY")
        or _get_env_str("HTTP_PROXY")
    )


def get_requests_proxies() -> Optional[Dict[str, Optional[str]]]:
    proxy = get_outbound_proxy_url()
    if not proxy:
        # 必须显式设为 None，不能返回 None — requests 库在 proxies=None 时会
        # 回退到环境变量 HTTP_PROXY / HTTPS_PROXY，导致代理开关不生效
        return {"http": None, "https": None}
    return {"http": proxy, "https": proxy}


# OpenAI 客户端
# 始终返回 Client 实例：代理启用时走代理，禁用时用 trust_env=False 防止
# httpx 回退读取环境变量 HTTP_PROXY / HTTPS_PROXY
def create_openai_http_client() -> httpx.Client:
    proxy_url = get_outbound_proxy_url()
    if proxy_url:
        return httpx.Client(proxy=proxy_url, timeout=120.0)
    return httpx.Client(trust_env=False, timeout=120.0)


def create_openai_async_http_client() -> httpx.AsyncClient:
    proxy_url = get_outbound_proxy_url()
    if proxy_url:
        return httpx.AsyncClient(proxy=proxy_url, timeout=120.0)
    return httpx.AsyncClient(trust_env=False, timeout=120.0)


# ====================== LLM 服务配置 ======================
def get_llm_api_key() -> Optional[str]:
    """LLM API Key 环境变量值（LLM_API_KEY）。"""
    return _get_env_str("LLM_API_KEY")


def get_llm_base_url() -> Optional[str]:
    """LLM Base URL 环境变量值（LLM_BASE_URL）。"""
    return _get_env_str("LLM_BASE_URL")


# ====================== 数据库配置 ======================
# 复用工具函数读取环境变量，消除重复逻辑
MYSQL_CONFIG = {
    "host": _require_env_str("MYSQL_HOST"),
    "port": _get_env_int("MYSQL_PORT", 3306),
    "user": _require_env_str("MYSQL_USER"),
    "password": _require_env_str("MYSQL_PASSWORD"),
    "database": _require_env_str("MYSQL_DATABASE"),
    "charset": _get_env_str("MYSQL_CHARSET") or "utf8mb4",
    "autocommit": _is_truthy(_get_env_str("MYSQL_AUTOCOMMIT") or "true"),
}

# 期限映射（动态生成反向映射，消除冗余变量）
PERIOD_MAP = {
    "3月": "3M",
    "6月": "6M",
    "1年": "1Y",
    "2年": "2Y",
    "3年": "3Y",
    "5年": "5Y",
    "7年": "7Y",
    "10年": "10Y",
    "30年": "30Y",
}
PERIOD_REVERSE_MAP = {v: k for k, v in PERIOD_MAP.items()}

# 因子分类中文映射（数据库英文 → 前端展示中文）
FACTOR_CATEGORY_MAP = {
    "POLICY": "政策",
    "MACRO": "宏观",
    "LIQUIDITY": "流动性",
    "RISK": "风险",
    "SENTIMENT": "情绪",
    "INDUSTRY": "行业",
}

# ====================== 分析模型配置 ======================
ANALYSIS_MODEL_PRIORITY = ["glm", "deepseek", "qwen", "default"]

# 简化注册表
ANALYSIS_MODEL_REGISTRY = {
    "deepseek": {
        "provider_model": "deepseek-v4-pro",
        "description": "DeepSeek 模型",
        "enabled": True,
    },
    "qwen": {
        "provider_model": "qwen3.7-flash",
        "description": "Qwen 模型",
        "enabled": True,
    },
    "glm": {
        "provider_model": "glm-5.2",
        "description": "智谱 模型",
        "enabled": True,
    },
    "kimi": {
        "provider_model": "kimi-k3",
        "description": "KIMI 模型",
        "enabled": True,
    },
}


def get_default_analysis_model_name() -> str:
    return _get_env_str("ANALYSIS_MODEL_NAME") or "glm"


def get_analysis_model_info(model_name: str) -> dict:
    return ANALYSIS_MODEL_REGISTRY.get(model_name, ANALYSIS_MODEL_REGISTRY["glm"])


def get_chat_model_name() -> str:
    # Agent 聊天默认模型短名，与分析模型统一风格：
    # 填短名（如 glm），provider model 由注册表解析；缺省跟随默认分析模型。
    return _get_env_str("CHAT_MODEL_NAME") or get_default_analysis_model_name()


# ====================== 新闻源配置 ======================
NEWS_SOURCES = {
    "wallstreetcn": "华尔街见闻",
    "yicai": "第一财经",
}

# 新闻源脱敏标签（合规）：对外展示通用数据源名，不暴露具体媒体名称
NEWS_SOURCE_LABELS = {
    "wallstreetcn": "数据源1",
    "yicai": "数据源2",
}


def mask_news_source(source_key: str) -> str:
    """新闻源脱敏：返回通用「数据源N」标签，避免暴露具体媒体（合规）。"""
    return NEWS_SOURCE_LABELS.get(source_key, "数据源")


# ====================== 投资组合策略配置 ======================

# 组合策略时区：统一使用北京时间进行日期计算和时间戳生成
PORTFOLIO_TZ = ZoneInfo("Asia/Shanghai")

# 每日定时自动生成 AI 策略推荐（STRATEGY_AUTO_ENABLED=true 时生效）
STRATEGY_AUTO_ENABLED = _is_truthy(_get_env_str("STRATEGY_AUTO_ENABLED") or "true")
# 触发时间（cron 格式，仅取小时字段，如 "0 9 * * *" = 每天 9:00）
STRATEGY_AUTO_CRON = _get_env_str("STRATEGY_AUTO_CRON") or "0 9 * * *"

# 组合策略默认模型：可通过环境变量 PORTFOLIO_STRATEGY_MODEL 覆盖
PORTFOLIO_MODEL = os.getenv("PORTFOLIO_STRATEGY_MODEL", "glm-5.2")

# 债券评级枚举：AI 输出中允许的最低评级取值集合
RATING_ENUM = {"不限", "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+"}

# 按债券种类分布键：AI 输出 distribution_by_category 必须包含的 9 个种类键
CATEGORY_KEYS = [
    "gov_bond",  # 国债
    "local_gov_bond",  # 地方政府债
    "corp_credit_bond",  # 企业信用债
    "financial_bond_non_policy",  # 非政策性金融债
    "other_bond",  # 其他债券
    "policy_financial_bond",  # 政策性金融债
    "gov_supported_institution_bond",  # 政府支持机构债
    "cd",  # 同业存单
    "abs",  # 资产支持证券
]

# 按债券类型分布键：AI 输出 distribution_by_type 必须包含的 2 个类型键
TYPE_KEYS = ["interest_rate_bond", "credit_bond"]

# ====================== API 路由前缀 ======================
# 可通过环境变量 API_PREFIX 覆盖（默认 /sapi）
API_PREFIX = _get_env_str("API_PREFIX") or "/sapi"

# 工作台会话历史长度上限（agent_chat_stream 传给 Agent 的最大历史消息数）
CONVERSATION_HISTORY_LIMIT = _get_env_int("WORKBENCH_CONVERSATION_HISTORY_LIMIT", 50)

# ====================== 看板配置 ======================
# 情感方向映射
DIR_MAP = {"positive": "看涨", "negative": "看跌", "neutral": "中性"}

# 债券期限列表（展示顺序）
PERIOD_LIST = ["3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "30Y"]

# 页面路由 → 中文标题映射
PAGE_TITLES = {
    # 新版工作台板块
    "/market": "市场",
    "/returns": "收益",
    "/forecast": "预测",
    "/watchlist": "关注列表",
    "/portfolio": "投资组合",
    "/workflow": "工作流",
    "/computer/strategies": "策略开发",
    "/computer/reports": "研报分析",
    "/computer/news": "每日新闻总结",
    "/computer": "工作台",
    "/custom/mcp": "MCP连接",
    "/custom/skills": "Skills",
    "/projects": "项目",
    "/chat": "对话",
    "/settings": "设置",
    # 旧页面
    "/news": "新闻",
    "/factors": "因子",
    "/prediction": "预测",
    "/agents": "Agent",
    "/strategies": "策略",
    "/change": "变动对比",
    "/dashboard": "看板",
    "/login": "登录",
    "/my-usage": "我的使用",
    "/macro-data": "宏观数据",
    "/research": "研报",
    "/ai-strategy-generation": "AI策略生成",
}

# 看板页面分布图表中应展示的完整路由列表（含未访问页面的零值补全）
ALL_PAGE_ROUTES = [
    "/market",
    "/returns",
    "/forecast",
    "/watchlist",
    "/portfolio",
    "/workflow",
    "/computer",
    "/computer/strategies",
    "/computer/reports",
    "/computer/news",
    "/custom/mcp",
    "/custom/skills",
    "/projects",
    "/chat",
    "/settings",
    "/factors",
    "/news",
]

# 会话冷却时间（秒）：冷却时间内复用同一会话
SESSION_COOLING_SEC = 10

# 看板指标缓存有效期（秒）
CACHE_TTL_SEC = 60

# 行为日志保留天数（超过自动清理）
BEHAVIOR_LOG_RETENTION_DAYS = 180

# 行为日志默认查询天数（前端默认只显示最近N天）
BEHAVIOR_LOG_DEFAULT_DAYS = 10

# ====================== 认证配置 ======================
# 是否启用登录认证（true=需要登录，false=免登录）
AUTH_ENABLED = _is_truthy(_get_env_str("AUTH_ENABLED") or "false")

# JWT 密钥（启用认证时必填，建议 32 位以上随机字符串）
JWT_SECRET_KEY = _get_env_str("JWT_SECRET_KEY")
if AUTH_ENABLED and not JWT_SECRET_KEY:
    raise RuntimeError(
        "Missing required environment variable: JWT_SECRET_KEY when AUTH_ENABLED=true"
    )

# JWT 过期时间（小时），默认 24 小时
JWT_EXPIRY_HOURS = int(_get_env_str("JWT_EXPIRY_HOURS") or "24")
