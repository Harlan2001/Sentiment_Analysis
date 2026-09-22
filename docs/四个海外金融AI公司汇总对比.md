# 四大金融 AI 公司汇总对比（Bloomberg / LSEG / S&P Global / AlphaSense）

> 对比维度：公司性质、客户群体、商业模式、AI 战略、核心产品与主要功能、内容护城河、模型与生态策略。
> 资料截至 2026 年 9 月，均基于各公司官方来源（详见各公司速览文档）。

## 一、公司概览

| 维度 | Bloomberg 彭博 | LSEG 伦敦证交所集团 | S&P Global 标普全球 | AlphaSense |
|---|---|---|---|---|
| 性质 | 私人公司（非上市） | 上市公司（LSE: LSEG） | 上市公司（NYSE: SPGI） | 私有独角兽（非上市） |
| 总部 | 纽约 | 伦敦 | 纽约 | 纽约 |
| 关键里程碑 | 1981 年成立；BloombergGPT 2023 | 2021 年收购 Refinitiv（约 270 亿美元）；2022 年微软 10 年合作 | 2022 年合并 IHS Markit（约 440 亿美元）；2018 年收购 Kensho（5.5 亿美元） | 2011 年成立；2024 年收购 Tegus（9.3 亿美元）；2026 年估值 75 亿美元 |
| 业务范围 | 金融数据终端、媒体、法律/税务 | 金融数据、交易所、指数、风险情报 | 评级、指数、市场情报、大宗商品全链条 | AI 市场情报搜索 + 专家访谈内容 |
| 旗舰产品 | Bloomberg Terminal | LSEG Workspace（前身 Eikon） | S&P Capital IQ Pro | AlphaSense 平台 |
| 客户规模 | 全球主要金融机构（终端订阅制，未公开精确数） | 44,000+ 客户、170+ 国家 | 评级/指数/数据全链条客户（未公开精确数） | 7,000+ 企业客户；85% 的 S&P 100 |

## 二、客户群体与商业模式

| 公司 | 客户类型（B 端/ C 端） | 典型客户 | 收费模式 | 面向客群特点 |
|---|---|---|---|---|
| Bloomberg | **纯 B 端** | 银行、券商、资管、对冲基金、央行、律所 | 终端席位订阅制（按座位年费） | 全市场交易/研究/合规人员，桌面标配 |
| LSEG | **纯 B 端** | 金融机构（数据订阅）+ 交易所客户 + 企业合规部门 | 数据授权订阅制（API/Feed/终端分层） | 数据驱动型机构，重实时行情与数据分发 |
| S&P Global | **纯 B 端** | 投行、资管、企业财务/战略部、评级与指数授权方 | 订阅制 + 评级/指数授权费 | 覆盖投融资决策、评级、指数投资全链条 |
| AlphaSense | **纯 B 端** | 对冲基金、公募、私募、投行、企业战略/竞争情报团队 | 企业席位订阅制（ARR 6 亿美元） | AI 原生用户，重搜索效率与独家专家内容 |

## 三、AI 战略与护城河

| 公司 | AI 战略一句话 | 底层模型策略 | 内容/数据护城河 | 开放生态 |
|---|---|---|---|---|
| Bloomberg | **自研 + 内化**：AI 全部锁在自家终端 | 自研 BloombergGPT（506 亿参数）+ Bloomberg BERT，部分接商业/开源 LLM 与 Anthropic | 数亿文档、每日 5000+ 新闻、800+ 卖方研究、1550 万+ 判例（法律） | 基本封闭；仅通过 MCP 接 Anthropic（BLAW） |
| LSEG | **模型无关 + 开放接入**：数据送进别人 AI | 不自研大模型，接微软/OpenAI/Anthropic/Databricks 等 | 全球最深实时行情与历史数据、Reuters 新闻、ESG/逐笔数据 | MCP 服务器（150+ 客户接入）、Copilot/ChatGPT/Claude |
| S&P Global | **收购补能力 + 标准制定**：评测基准占生态位 | 不自研大模型，接 Anthropic/Cohere + 自研 NLP 工具链 | 评级垄断、S&P 500 指数授权、Capital IQ 财务数据 | MCP：Anthropic/AWS/Salesforce/Cohere |
| AlphaSense | **AI 搜索 + 专家内容闭环**：AI 反向生产内容 | 不自研大模型，借 Cerebras 推理加速（约 10 倍速） | 5 亿+ 文档、Tegus 20 万+ 专家访谈记录 | Agent API、托管 MCP、AWS AI Marketplace |

## 四、核心 AI 产品与主要功能（逐公司）

### Bloomberg

| 产品 | 主要功能 | 上线时间 |
|---|---|---|
| BloombergGPT | 自研 506 亿参数金融大模型，能力内化于自有产品，未开源 | 2023-03 |
| ASKB（Ask Bloomberg） | 终端 agentic 对话主入口：跨数亿文档/新闻/卖方研究统一检索，答案带出处，生成 BQL 代码，研究流程可存模板 | 2026-02 beta（2026-08 移动端） |
| Document Insights / Search & Analysis | 单文档/跨 4 亿+ 文档问答，答案带原文锚点与音频回放 | 2025-04 / 2025-06 |
| BQuant Textual Analytics | 金融 NLP 加购包：Bloomberg BERT 情绪分 + T5 摘要，供量化回测 | 2025 前后 |
| Bloomberg Law AI（BLAW） | grounded 于 1550 万+ 判例的法律 AI 问答，走向 agentic 深度研究 | 2025-01（2026-08 Agentic） |
| Bloomberg Tax AI | 税务 AI 问答 + Deep Thinking Mode 多步研究 | 2025-03（2026-03 升级） |
| Bloomberg Regology | AI 监管变更管理：追踪 135+ 国家法规并映射到内控 | 2026-06 收购品牌化 |
| ESG / SFDR ML 排放估算 | 约 10 万家公司 Scope 1/2/3 碳排放 ML 估算 | 2025 前后 |

### LSEG

| 产品 | 主要功能 | 上线时间 |
|---|---|---|
| Workspace AI Search | 终端自然语言问答 agent，跨 LSEG 数据/新闻/研报检索，答案可验证 | 2026-07 |
| Workspace Deep Research | 投资研究深度 agent，grounded 于 LSEG 数据并带出处，支持 Teams 内使用 | 2026-06 |
| LSEG × Microsoft 合作 | 数据经 MCP 接入 M365 Copilot/Copilot Studio；Financial Meeting Prep 自动生成会前报告 | 2022-12 合作；2025-10 MCP |
| LSEG × OpenAI | 首家向 ChatGPT 提供可信金融数据的 MCP 连接器 | 2025-12 |
| LSEG × Anthropic | Claude for Financial Services，agentic AI 直接调 LSEG 数据 | 2026 |
| Machine Readable News / News Analytics | 新闻 NLP 情绪/相关性/新颖度打分，历史回溯至 2003 年，覆盖 32,000+ 公司 | 路孚特时代起 |
| MarketPsych ESG Analytics | AI NLP 的 ESG 情绪分析，每日处理 200 万+ 文章/帖子 | 路孚特时代起 |
| World-Check 风险情报 AI | 制裁/PEP/负面媒体筛查，智能标记 + API 化机器可读风险数据 | 持续迭代 |

### S&P Global（含 Kensho）

| 产品 | 主要功能 | 上线时间 |
|---|---|---|
| Capital IQ Pro ChatIQ + Document Intelligence | 终端 GenAI 助手 + 多文档智能分析，回答带精确引用、可审计 | 2024-11（2.0 于 2025-10） |
| Kensho LLM-ready API（kFinance） | LLM 原生数据 API：自然语言查 Capital IQ 财务/电话会记录，带源引用；MCP 接入 Claude | 2024-11 beta（2025-07 Claude） |
| Kensho 工具集（Scribe/Extract/NERD/Link） | 金融语音转写、PDF 数据提取（含图表提取）、实体识别（链接近 1 亿实体）、公司关系图谱 | 持续迭代 |
| S&P AI Benchmarks by Kensho | 金融/量化 LLM 能力评测与排名，配套开源基准数据集 | 2024-04 |
| ProntoNLP | 事件检测 + 情绪评分（财报电话会分析），2026 年并入 Capital IQ Pro | 2025-01 收购 |
| Credit Memo Builder | Agentic AI 信贷备忘录生成器，自动收集综合数据出报告 | 2026-06 |
| S&P 500 3AI Sector Rotator Index | 首个 AI 增强指数：ML 模型打分选板块轮动 | 2025-10 |
| MCP 生态（AWS/Salesforce/Cohere） | 数据与文档能力接入 AWS、Salesforce AgentExchange、Cohere | 2025-10 起 |

### AlphaSense（含 Tegus）

| 产品 | 主要功能 | 上线时间 |
|---|---|---|
| Generative Search | 自然语言搜索，秒级返回带引用答案；2025-11 升级为多智能体研究系统 | 2025-03 |
| Generative Grid | 一次跨 5 亿+ 文档提多个问题，结果出成结构化表格，带引用 | 2025-03 |
| Deep Research | 自动多步深度研究（数十次搜索→综合推理→带引用报告），支持移动端 | 2025 |
| AI Agent Interviewer + Channel Checks | AI 自主主持专家 1:1 访谈并出转录摘要；实时渠道信号覆盖 350+ 股票 | 2025-08 |
| Sentiment Analysis & Sentiment Indices | NLP 情绪颜色编码 + 15+ 行业板块情绪指数（-100~+100） | 持续迭代 |
| Smart Summaries | 财报季智能摘要，几分钟提取电话会关键洞察 | 持续迭代 |
| Tegus Expert Transcript Library | 20 万+ 份专家访谈记录、2.4 万+ 家公司（前高管/客户/竞争对手观点） | 2024-07 收购并入 |
| Agent API / MCP / AWS Marketplace | 开放 agent 能力（GenSearch/DeepResearch/MCP 工具），上架 AWS AI Marketplace | 2026 起 |

## 五、关键启示（可借鉴点汇总）

| 公司 | 最值得借鉴的打法 | 不建议模仿的 |
|---|---|---|
| Bloomberg | 选垂直场景做透（法律/税务）；研究流程 agent 化、可复用模板 | 自研数百亿参数金融大模型 |
| LSEG | 答案带出处可验证；数据经 MCP 嵌入客户现有工作流（Teams/Copilot） | 依赖庞大自建数据管道 |
| S&P Global | 用评测基准/榜单占生态位；收购小团队补单点能力（ProntoNLP/Drift AI） | 全链条布局（评级+指数+数据） |
| AlphaSense | AI 自动生产内容（AI 访谈专家）；表格化多文档对比；情绪做成指数产品 | 高估值融资 + 9.3 亿美元级大额收购 |


