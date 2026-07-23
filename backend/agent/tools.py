"""
Agent Skill / Tool 定义模块

定义 8 个 Skill 的 OpenAI function-calling 格式规范。
所有工具均为只读查询，不产生副作用。
"""

TOOL_DEFINITIONS = [
    # ── 新闻类 ──
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": (
                "按关键词搜索债券市场新闻，在标题和内容中进行模糊匹配。"
                "适用于用户询问「最近XX有什么新闻」「有关XX的消息」等场景。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，如「降息」「MLF」「通胀」",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数上限，默认10，最大30",
                        "default": 10,
                    },
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news_by_date",
            "description": (
                "获取指定日期的债券市场新闻列表，可按新闻来源过滤。"
                "适用于用户询问「今天的新闻」「昨天有什么大事」等场景。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "查询日期，格式 YYYY-MM-DD，如 2025-07-23",
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选，新闻来源过滤，支持 wallstreetcn / yicai 等",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数上限，默认20，最大50",
                        "default": 20,
                    },
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news_detail",
            "description": (
                "获取单条新闻的完整详情，包括全文内容、AI 分析结果（方向/期限/理由）"
                "以及关联的影响因子列表。适用于用户询问「这条新闻具体说了什么」等场景。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "news_id": {
                        "type": "integer",
                        "description": "新闻 ID",
                    },
                },
                "required": ["news_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_similar_news",
            "description": (
                "通过语义向量搜索，找到与指定新闻在内容上相似的历史新闻。"
                "适用于用户想了解「历史上类似的事件」「这个事件以前出现过吗」等场景。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "news_id": {
                        "type": "integer",
                        "description": "参考新闻 ID",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回最相似的 K 条新闻，默认5",
                        "default": 5,
                    },
                },
                "required": ["news_id"],
            },
        },
    },
    # ── 因子类 ──
    {
        "type": "function",
        "function": {
            "name": "list_factors",
            "description": (
                "列出系统中所有可用的影响因子，可按类别过滤。"
                "因子是对债券收益率产生影响的经济/政策/市场因素。"
                "类别包括：POLICY（政策）、MACRO（宏观）、LIQUIDITY（流动性）、"
                "RISK（风险）、SENTIMENT（情绪）、INDUSTRY（行业）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "可选，按类别过滤：POLICY / MACRO / LIQUIDITY / RISK / SENTIMENT / INDUSTRY",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news_by_factor",
            "description": (
                "获取与指定因子代码关联的新闻列表。"
                "适用于用户询问「哪些新闻影响了XX因子」「XX因子最近有什么相关事件」等场景。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "factor_code": {
                        "type": "string",
                        "description": "因子代码，如 MLF_RATE、CPI_YOY、GDP_GROWTH",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数上限，默认20",
                        "default": 20,
                    },
                },
                "required": ["factor_code"],
            },
        },
    },
    # ── 宏观信号类 ──
    {
        "type": "function",
        "function": {
            "name": "compute_macro_signal",
            "description": (
                "计算指定因子在某个时间范围内的宏观信号。支持两种信号类型：\n"
                "- presence（存在性）：因子是否有相关新闻，返回 0/1\n"
                "- directional（方向性）：因子的方向信号，-1（看跌）/0（中性）/1（看涨），"
                "使用时间衰减加权（越近的新闻权重越大）\n"
                "适用于用户询问「最近XX因子的信号如何」「市场对XX的反应方向」等场景。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "factor_code": {
                        "type": "string",
                        "description": "因子代码，支持逗号分隔多个，如 MLF_RATE,CPI_YOY",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "开始时间，ISO 格式如 2025-07-01T00:00:00",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "结束时间，ISO 格式如 2025-07-23T23:59:59",
                    },
                    "signal_type": {
                        "type": "string",
                        "enum": ["presence", "directional"],
                        "description": "信号类型：presence（存在性）或 directional（方向性）",
                        "default": "directional",
                    },
                    "decay_lambda": {
                        "type": "number",
                        "description": "时间衰减系数，仅 directional 生效，默认 0.1",
                        "default": 0.1,
                    },
                },
                "required": ["factor_code", "start_time", "end_time"],
            },
        },
    },
    # ── 市场数据类 ──
    {
        "type": "function",
        "function": {
            "name": "get_yield_curve",
            "description": (
                "获取指定日期范围内的国债收益率曲线数据。"
                "适用于用户询问「最近收益率走势」「XX期限的收益率变化」等场景。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "开始日期，格式 YYYY-MM-DD",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "结束日期，格式 YYYY-MM-DD",
                    },
                    "period": {
                        "type": "string",
                        "description": "债券期限，如 1年/3年/5年/10年/30年，默认10年",
                        "default": "10年",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
]

# 工具中文名映射（前端展示用）
TOOL_DISPLAY_NAMES: dict[str, str] = {
    "search_news": "新闻搜索",
    "get_news_by_date": "按日期获取新闻",
    "get_news_detail": "新闻详情",
    "find_similar_news": "相似新闻搜索",
    "list_factors": "因子列表",
    "get_news_by_factor": "因子关联新闻",
    "compute_macro_signal": "宏观信号计算",
    "get_yield_curve": "收益率曲线",
}

# 工具图标映射（前端展示用）
TOOL_ICONS: dict[str, str] = {
    "search_news": "📰",
    "get_news_by_date": "📅",
    "get_news_detail": "🔍",
    "find_similar_news": "🔗",
    "list_factors": "📊",
    "get_news_by_factor": "🏷️",
    "compute_macro_signal": "⚡",
    "get_yield_curve": "📈",
}
