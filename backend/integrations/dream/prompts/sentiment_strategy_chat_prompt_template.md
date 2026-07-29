【我的策略需求】{{USER_REQUIREMENT}}

【当前市场情况】产生时点：{{MARKET_AS_OF}}
策略标的：{{INSTRUMENT}}
标的情报范围：{{MARKET_SCOPE}}
策略频率：{{FREQUENCY}}
价格/技术状态：{{MARKET_TECHNICAL_STATE}}
市场验证信息：{{YIELD_CURVE_SUMMARY}}

【本轮 Sentiment 新闻分析】产生时点：{{REPORT_GENERATED_AT}}；数据窗口：{{WINDOW_START}} 至 {{WINDOW_END}}（{{WINDOW_DAYS}}日）；分析模型：{{ANALYSIS_MODEL}}。
一、提取来源：仅使用与当前标的情报范围匹配的 news（新闻标题/时间）+ analysis（方向/期限/传导理由）+ factor/news_factor（因子和方向）。
二、新闻提取结果：方向明确{{DIRECTIONAL_EVENT_COUNT}}条：正向{{POSITIVE_EVENT_COUNT}}条、负向{{NEGATIVE_EVENT_COUNT}}条；短期{{SHORT_HORIZON_COUNT}}条。代表性事件：
{{REPRESENTATIVE_EVENTS}}
三、因子整合：正向因子：{{POSITIVE_FACTORS}}。负向因子：{{NEGATIVE_FACTORS}}。
四、市场验证：{{YIELD_CURVE_DETAIL}}
五、给策略 AI 的使用方式：{{SENTIMENT_CONCLUSION}}；{{SENTIMENT_STRATEGY_ACTION}}。这是外部市场上下文，不代替价格、流动性和回测验证，不得单独作为交易触发。

【请生成策略】请根据以上策略需求、当前市场情况和标的相关 Sentiment 新闻分析生成策略。
逻辑概要请简短说明：
1. 当前相关新闻分析的总体判断；
2. 新闻分析在本策略中的实际用途：方向确认、交易过滤、提高开仓阈值、风险降级或不使用；
3. 当新闻判断与价格信号冲突时的处理方式。
