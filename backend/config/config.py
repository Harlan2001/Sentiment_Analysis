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
LOG_MAX_DAYS = _get_env_int("LOG_MAX_DAYS", 30)


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


def get_requests_proxies() -> Dict[str, Optional[str]]:
    proxy = get_outbound_proxy_url()
    if not proxy:
        # 必须显式设为 None，不能返回 None — requests 库在 proxies=None 时会
        # 回退到环境变量 HTTP_PROXY / HTTPS_PROXY，导致代理开关不生效
        return {"http": None, "https": None}
    return {"http": proxy, "https": proxy}


# OpenAI 客户端
# 始终返回 Client 实例：代理启用时走代理，禁用时用 trust_env=False 防止
# httpx 回退读取环境变量 HTTP_PROXY / HTTPS_PROXY
_HTTP_TIMEOUT_SECONDS = 120.0


def _http_client_options() -> dict:
    """httpx 客户端共用选项：代理 URL（启用时）或禁用环境代理回退。"""
    proxy_url = get_outbound_proxy_url()
    if proxy_url:
        return {"proxy": proxy_url}
    return {"trust_env": False}


def create_openai_http_client() -> httpx.Client:
    return httpx.Client(timeout=_HTTP_TIMEOUT_SECONDS, **_http_client_options())


def create_openai_async_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS, **_http_client_options())


# ====================== LLM 服务配置 ======================
def get_llm_api_key() -> str:
    """LLM API Key 环境变量值（LLM_API_KEY，可能为空字符串）。"""
    return _get_env_str("LLM_API_KEY")


def get_llm_base_url() -> str:
    """LLM Base URL 环境变量值（LLM_BASE_URL，可能为空字符串）。"""
    return _get_env_str("LLM_BASE_URL")


# ====================== 数据库配置 ======================
# 复用工具函数读取环境变量，消除重复逻辑
MYSQL_CONFIG = {
    "host": _require_env_str("MYSQL_HOST"),
    "port": _get_env_int("MYSQL_PORT", 3306),
    "user": _require_env_str("MYSQL_USER"),
    "password": _require_env_str("MYSQL_PASSWORD"),
    # 生产/主库。集成测试通过独立连接参数连测试库，不在生产配置里做库切换
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
# 分析模型优先级（越小越优先，default 兜底；历史 doubao 走 ELSE 999）
ANALYSIS_MODEL_PRIORITY = ["glm", "kimi", "deepseek", "qwen", "default"]

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


# ====================== 新闻推荐打分配置（S3-2） ======================
# 设计说明：静态重要性分 I_news（0-100）预计算落 news_importance_score，
# 读时再叠加时间衰减 final = I * EXP(-lambda * age_days)。调参只改本处。
RECOMMEND_SCORE_VERSION = "v1"
RECOMMEND_DECAY_LAMBDA = 0.08          # 半衰期约 8.7 天，适配 7-30 天推荐窗口
RECOMMEND_WINDOW_DAYS = 7              # 推荐流默认窗口
RECOMMEND_MAX_WINDOW_DAYS = 30         # 推荐流窗口硬上限
RECOMMEND_HOLDING_DAYS = 5             # 命中率先验取 factor_event_study 的持有期
RECOMMEND_MIN_STUDY_SAMPLES = 20       # 事件研究样本充足门槛，不足向 0.5 收缩

# 因子类别权重：利率交易员视角（政策 > 宏观 > 资金面 > 风险 > 情绪 > 行业）
FACTOR_CATEGORY_WEIGHTS = {
    "POLICY": 1.00,
    "MACRO": 0.90,
    "LIQUIDITY": 0.85,
    "RISK": 0.70,
    "SENTIMENT": 0.55,
    "INDUSTRY": 0.45,
}

# 九个信号在静态分中的权重，和必须为 1（test_importance 会校验）
NEWS_IMPORTANCE_WEIGHTS = {
    "direction": 0.18,   # 最佳模型方向强度
    "agreement": 0.14,   # 多模型方向一致性
    "horizon": 0.08,     # 期限（中期最贴合仓位决策）
    "category": 0.20,    # 关联因子的最高类别权重
    "hit": 0.12,         # 因子事件研究命中率先验
    "nfactor": 0.10,     # 关联因子数量（5 个饱和）
    "rich": 0.08,        # 内容丰富度（图/表/标题块）
    "policy": 0.07,      # 政策标记（POLICY 因子或标题关键词）
    "source": 0.03,      # 来源权重（v1 两源同分，保留配置位）
}

# 政策标题关键词（无实体表，POLICY 因子之外的兜底政策信号）
POLICY_TITLE_KEYWORDS = (
    "降准", "降息", "MLF", "LPR", "逆回购", "公开市场", "国债", "财政部",
    "央行", "货币政策", "再贷款", "再贴现", "国库定存", "SLF", "PSL",
)

# 来源权重：合规脱敏后 v1 不人为区分，待行为数据上线再拉开
NEWS_SOURCE_WEIGHTS = {
    "wallstreetcn": 1.0,
    "yicai": 1.0,
}


# ====================== 组合策略配置 ======================

# 组合策略时区：统一使用北京时间进行日期计算和时间戳生成
PORTFOLIO_TZ = ZoneInfo("Asia/Shanghai")

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
    "/info": "信息",
    "/backtest": "回测仿真",
    "/returns": "收益",
    "/forecast": "预测",
    "/watchlist": "关注列表",
    "/portfolio": "投资组合",
    "/futures": "期货持仓",
    "/credit-spread": "信用利差",
    "/treasury-spread": "中美利差",
    "/workflow": "工作流",
    "/computer/strategies": "策略生成",
    "/computer/reports": "研报分析",
    "/computer/news": "每日新闻总结",
    "/computer/policy": "政策文件分析",
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
    "/info",
    "/backtest",
    "/returns",
    "/forecast",
    "/watchlist",
    "/portfolio",
    "/futures",
    "/credit-spread",
    "/treasury-spread",
    "/workflow",
    "/computer",
    "/computer/strategies",
    "/computer/reports",
    "/computer/news",
    "/computer/policy",
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
JWT_EXPIRY_HOURS = _get_env_int("JWT_EXPIRY_HOURS", 24)

# 是否启用手机号登录（true=启用，false=关闭，仅账号密码登录；默认 true）
AUTH_PHONE_LOGIN = _is_truthy(_get_env_str("AUTH_PHONE_LOGIN") or "true")

# 规范角色（全库唯一词汇表）：普通用户一律为 user，member 为历史遗留叫法
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_USER = "user"
