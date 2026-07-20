"""
系统配置中心
"""
from pathlib import Path
import os
import httpx
from dotenv import load_dotenv
from typing import Optional, Dict
from zoneinfo import ZoneInfo

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

# ====================== 日志配置 ======================
LOG_LEVEL = _get_env_str("LOG_LEVEL") or "INFO"
LOG_DIR = _get_env_str("LOG_DIR") or str(BASE_DIR / "logs")
LOG_MAX_DAYS = int(_get_env_str("LOG_MAX_DAYS") or "30")

# ====================== 本地快照配置 ======================
# 【临时兼容】SaaS 无法访问内网 API 时，使用本地快照文件替代实时 API 调用
# 使用前需在内网环境运行 scripts/generate_snapshot.py 生成快照文件
SNAPSHOT_DIR = DATA_DIR / "snapshots"
USE_LOCAL_SNAPSHOT = _is_truthy(_get_env_str("USE_LOCAL_SNAPSHOT") or "false")

# ====================== 代理配置 ======================
def is_outbound_proxy_enabled() -> bool:
    raw_value = _get_env_str("OUTBOUND_PROXY_ENABLED")
    return _is_truthy(raw_value) if raw_value else True

def get_outbound_proxy_url() -> Optional[str]:
    if not is_outbound_proxy_enabled():
        return None
    return _get_env_str("OUTBOUND_PROXY_URL") or _get_env_str("HTTPS_PROXY") or _get_env_str("HTTP_PROXY")

def get_requests_proxies() -> Optional[Dict[str, Optional[str]]]:
    proxy = get_outbound_proxy_url()
    if not proxy:
        # 必须显式设为 None，不能返回 None — requests 库在 proxies=None 时会
        # 回退到环境变量 HTTP_PROXY / HTTPS_PROXY，导致代理开关不生效
        return {"http": None, "https": None}
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
    "wallstreetcn": "华尔街见闻", "yicai": "第一财经",
}
DEFAULT_NEWS_SOURCES = []

# ====================== 投资组合策略配置 ======================

# 组合策略时区：统一使用北京时间进行日期计算和时间戳生成
PORTFOLIO_TZ = ZoneInfo("Asia/Shanghai")

# 组合策略默认模型：可通过环境变量 PORTFOLIO_STRATEGY_MODEL 覆盖
PORTFOLIO_MODEL = os.getenv("PORTFOLIO_STRATEGY_MODEL", "volcengine/doubao-seed-2-0-code-preview-260215")

# 债券评级枚举：AI 输出中允许的最低评级取值集合
RATING_ENUM = {"不限", "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+"}

# 按债券种类分布键：AI 输出 distribution_by_category 必须包含的 9 个种类键
CATEGORY_KEYS = [
    "gov_bond",                       # 国债
    "local_gov_bond",                 # 地方政府债
    "corp_credit_bond",               # 企业信用债
    "financial_bond_non_policy",      # 非政策性金融债
    "other_bond",                     # 其他债券
    "policy_financial_bond",          # 政策性金融债
    "gov_supported_institution_bond", # 政府支持机构债
    "cd",                             # 同业存单
    "abs",                            # 资产支持证券
]

# 按债券类型分布键：AI 输出 distribution_by_type 必须包含的 2 个类型键
TYPE_KEYS = ["interest_rate_bond", "credit_bond"]

# ====================== API 路由前缀 ======================
# 可通过环境变量 API_PREFIX 覆盖（默认 /sapi）
API_PREFIX = _get_env_str("API_PREFIX") or "/sapi"

# ====================== 看板配置 ======================
# 情感方向映射
DIR_MAP = {"positive": "看涨", "negative": "看跌", "neutral": "中性"}

# 债券期限列表（展示顺序）
PERIOD_LIST = ["3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "30Y"]

# 页面路由 → 中文标题映射
PAGE_TITLES = {
    "/news": "新闻", "/factors": "因子", "/data": "数据", "/prediction": "预测",
    "/agents": "Agent", "/select-strategy": "AI推荐", "/strategies": "策略",
    "/change": "变动对比", "/macro-signal-logs": "信号日志", "/dashboard": "看板", "/login": "登录",
}

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
JWT_SECRET_KEY = _get_env_str("JWT_SECRET_KEY") or "sentiment-jwt-secret-change-me"

# JWT 过期时间（小时），默认 24 小时
JWT_EXPIRY_HOURS = int(_get_env_str("JWT_EXPIRY_HOURS") or "24")
