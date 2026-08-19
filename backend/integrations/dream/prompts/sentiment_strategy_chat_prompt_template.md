【交易规则与策略需求】
{{USER_REQUIREMENT}}

【输出顺序】先创建或更新包含完整可执行代码的策略版本，再运行回测，最后返回简短概要与回测结果。参数已完整时不得只输出规划、推演或“将生成代码”的说明；没有创建策略代码版本的文本回复视为未完成。

【执行要求】以上交易参数为本轮生成与回测的约束。代码必须使用平台当前可用的策略 API、数据订阅与交易品种；不得臆造接口、数据字段或品种代码。请在最终回复前实际执行回测：若编译、初始化、数据订阅或交易逻辑报错，先依据回测日志修复后再次回测。只有得到终态回测结果后再输出策略代码、策略概要与回测结果；若平台或数据确实无法完成回测，应如实说明阻塞原因和完整日志，不得把未执行或进行中的回测表述为失败。

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

【请生成策略】请根据以上交易规则、策略需求、当前市场情况和标的相关 Sentiment 新闻分析生成策略。
逻辑概要请简短说明：
1. 当前相关新闻分析的总体判断；
2. 新闻分析在本策略中的实际用途：方向确认、交易过滤、提高开仓阈值、风险降级或不使用；
3. 当新闻判断与价格信号冲突时的处理方式。
