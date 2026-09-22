# S&P Global 金融 AI 产品速览

> 公司：**S&P Global（标普全球，NYSE: SPGI）**，总部纽约的金融信息服务上市公司，业务覆盖评级（S&P Global Ratings）、指数（S&P Dow Jones Indices，含 S&P 500）、市场情报（S&P Capital IQ Pro）、大宗商品洞察（Platts）等全链条；旗舰产品为 S&P Capital IQ Pro（机构订阅制数据与分析平台）。旗下 Kensho 为集团 AI 引擎（2018 年以约 5.5 亿美元收购，保持独立品牌），2022 年 2 月完成与 IHS Markit 约 440 亿美元合并。

## 一、主推金融 AI 产品（精选 8 个）

### 1. S&P Capital IQ Pro ChatIQ + Document Intelligence（终端 GenAI 助手）
2024 年 11 月发布 ChatIQ——与 Kensho 合作开发的生成式 AI 助手，支持公司、行业与板块研究，并同步上线 Document Intelligence 文档智能；2025 年 10 月升级 Document Intelligence 2.0，利用生成式 AI 跨海量文档库做多文档研究分析，回答带精确引用、可完整审计。
- [官方新闻稿（ChatIQ + Document Intelligence，2024-11）](https://press.spglobal.com/2024-11-12-S-P-Global-Transforms-S-P-Capital-IQ-Pro-Experience-with-the-Launch-of-New-Generative-AI-Powered-Capabilities)
- [官方新闻稿（Document Intelligence 2.0，2025-10）](https://press.spglobal.com/2025-10-22-S-P-Global-Redefines-Financial-Insights-with-New-AI-Powered-Multi-Document-Research-and-Analysis-Tool-in-Capital-IQ-Pro-ChatIQ)

### 2. Kensho LLM-ready API（kFinance，数据接入 AI 的 LLM 原生 API）
2024 年 11 月开放 beta：面向 LLM 优化的结构化数据 API（简化结构、支持 function calling），用户用自然语言查询 S&P Capital IQ 财务数据、盈利电话会记录、公司情报、私募公司财务等，回答带源文件引用；2025 年 7 月由 Kensho 开发 MCP 服务器，把该 API 接入 Anthropic Claude；2026 年 6 月扩展与 Cohere 合作。
- [官方新闻稿（LLM-ready API beta，2024-11）](https://press.spglobal.com/2024-11-13-S-P-Global-Launches-Kensho-LLM-ready-API-beta-,-Making-its-Structured-Data-Accessible-for-Generative-AI)
- [官方新闻稿（Anthropic Claude 集成，2025-07）](https://press.spglobal.com/2025-07-15-S-P-Global-and-Anthropic-Announce-Integration-of-S-P-Globals-Trusted-Financial-Data-into-Claude)
- [Kensho 官方产品页](https://kensho.com/solutions/llm-ready-api)

### 3. Kensho 工具集：Scribe / Extract / NERD / Link（AI 底层能力四件套）
Scribe 为金融术语优化的语音转写（官方称准确率比通用转写服务高约 25 个百分点）；Extract 做文档/PDF 数据提取（含专利的 Figure Extraction 图表数据提取、表格结构识别），其 Kenverters 为开源转换工具；NERD（Named Entity Recognition and Disambiguation）做命名实体识别与消歧，把文本中的公司、人物、事件链接到 S&P Capital IQ 与 Wikimedia 的近 1 亿实体；Link 构建公司实体关系图谱。另有 Grounding Agent 提供带引用的接地检索。
- [Kensho NERD 官方页](https://kensho.com/nerd)
- [Kensho Extract 官方文档（Toolkit/Kenverters）](https://docs.kensho.com/extract/toolkit)
- [Kensho 产品新闻（Figure Extraction）](https://kensho.com/news/category/Product)

### 4. S&P AI Benchmarks by Kensho（金融 LLM 能力评测基准）
2024 年 4 月发布 beta：对大型语言模型在金融与量化场景的推理能力、领域专业度做评估与排名，并配套发布用于评测/训练 LLM 的金融基准数据集（Finance Fundamentals 数据集，部分开源），成为 S&P 在"AI 评测标准"上建立话语权的独特打法。
- [官方新闻稿（S&P AI Benchmarks by Kensho，2024-04）](https://press.spglobal.com/2024-04-03-S-P-Global-Redefines-Financial-AI-Benchmarking-with-S-P-AI-Benchmarks-by-Kensho-Beta)
- [Kensho Datasets 官方页](https://datasets.kensho.com/)

### 5. ProntoNLP（收购，事件检测与情绪分析）
2025 年 1 月收购 ProntoNLP：提供事件检测与情绪评分的 AI 解决方案，含财报电话会预交付分析（Script Insight）等，整合进 S&P Global Market Intelligence；2026 年 3 月其分析能力加入 Capital IQ Pro，与固定收益、生物医药、私募市场数据扩容同步上线。
- [官方新闻稿（收购 ProntoNLP，2025-01）](https://press.spglobal.com/2025-01-06-S-P-Global-Acquires-ProntoNLP,-Expanding-its-Generative-AI-Powered-Product-Portfolio)
- [官方新闻稿（ProntoNLP 加入 Capital IQ Pro，2026-03）](https://press.spglobal.com/2026-03-12-S-P-Global-Enhances-Capital-IQ-Pro-with-Expanded-Fixed-Income,-Biopharma-and-Private-Markets-Data-Content-and-AI-Capabilities)

### 6. Credit Memo Builder™（Agentic AI 信贷备忘录生成器）
2026 年 6 月发布：agentic AI 驱动的信贷决策报告生成工具，自动完成信贷备忘录的数据收集与综合，显著缩短撰写时间，让分析师聚焦于战略风险评估。
- [官方新闻稿（Credit Memo Builder，2026-06）](https://press.spglobal.com/2026-06-04-S-P-Global-Launches-Agentic-AI-Powered-Credit-Memo-Builder-TM-to-Streamline-Credit-Analysis)

### 7. S&P 500 3AI Sector Rotator Index（AI 增强指数）
2025 年 10 月 S&P Dow Jones Indices 推出其首个 AI 增强指数：用 3AI 的机器学习模型对板块打分，选出三个最高分板块做轮动，是标普把 AI 预测建模引入指数设计的第一步。
- [官方新闻稿（首个 AI 增强指数，2025-10）](https://press.spglobal.com/2025-10-23-S-P-Global-to-Launch-its-First-AI-Enhanced-Sector-Rotation-Index)

### 8. AI 开放生态接入（MCP / Agentic 市场）
沿 MCP 协议把 S&P 数据与文档能力送进主流 AI 生态：2025 年 10 月 Capital IQ Pro Document Intelligence 上线 Salesforce AgentExchange（agentic AI 市场，原生接入 Agentforce 数字劳动力平台）；2025 年 12 月与 AWS 合作提供两个 MCP 服务器集成，把 Capital IQ Financials、盈利电话会记录等数据接入 AWS AI 工作流；2026 年 2 月发布面向 Claude 的 S&P Global Plugin（开源 spglobal-agent-skills，基于 MCP 技能）；2026 年 7 月与 Farsight 合作，为 Capital IQ Pro 提供生成 pitch deck、CIM、估值材料的 AI 工作流插件。
- [官方新闻稿（Salesforce AgentExchange，2025-10）](https://press.spglobal.com/2025-10-14-S-P-Global-Launches-S-P-Capital-IQ-Pro-Document-Intelligence-on-Salesforces-AgentExchange,-Transforming-Document-Analysis-with-Generative-AI)
- [官方新闻稿（AWS MCP 集成，2025-12）](https://press.spglobal.com/2025-12-01-S-P-Global-Collaborates-with-AWS-to-Bring-Trusted-Data-Directly-to-Customer-AI-Workflows)
- [Kensho 新闻（S&P Global Plugin，2026-02）](https://kensho.com/news/sp-global-brings-financial-skills-to-ai-agents-with-new-plugin)
- [官方新闻稿（Farsight 合作，2026-07）](https://press.spglobal.com/2026-07-23-S-P-Global-Market-Intelligence-Partners-with-Farsight-to-Launch-AI-powered-Financial-Workflow-Capability-for-Capital-IQ-Pro)

## 二、GitHub 开源情况

- 官方 GitHub 组织：<https://github.com/kensho-technologies>（Kensho，S&P Global 旗下 AI 引擎，48 个公开仓库，含近期活跃更新的金融 AI 项目）
- 与金融 AI/数据直接相关的开源仓库：
  - <https://github.com/kensho-technologies/kfinance>（Kensho LLM-ready API 的 Python 库，Apache-2.0）
  - <https://github.com/kensho-technologies/spglobal-agent-skills>（Claude 版 S&P Global Plugin 的技能仓库，Apache-2.0）
  - <https://github.com/kensho-technologies/kenverters>（Kensho Extract 开源转换工具）
  - <https://github.com/kensho-technologies/graphql-compiler>（把 GraphQL 查询编译为优化数据库查询，Kensho 经典开源项目）
  - <https://github.com/kensho-technologies/sequence_align>、<https://github.com/kensho-technologies/grits>（表格提取评测等 ML 基础设施）
- 官方开发者文档站：<https://developer.spglobal.com>；Kensho 文档站：<https://docs.kensho.com>；开源/研究数据集：<https://datasets.kensho.com>
- **S&P Global 未开源自研金融大模型**——与彭博不同，其开源重点在 AI 工具链、Agent 技能与评测数据集（如 AI Benchmarks 配套的 Finance Fundamentals 基准数据），底层模型走"接多家 LLM"路线。

## 三、说明

- S&P Global 为纽约上市公司（NYSE: SPGI），有公开财报；多数 AI 产品定价与具名客户未披露。本速览链接均取自已核验的官方来源。
- 战略特征：**收购补能力 + 开放生态 + 标准制定**——2018 年收购 Kensho（约 5.5 亿美元）建立 AI 引擎，2025 年收购 ProntoNLP（事件/情绪）、2026 年 3 月收购 Drift AI（自然语言金融建模，整合进 Capital IQ Pro Excel 插件），并通过 MCP 把数据接入 Anthropic/AWS/Salesforce/Cohere 生态；S&P AI Benchmarks 是其以"评测标准"切入 AI 产业的独特打法。
- 与彭博（自研内化）、LSEG（模型无关开放接入）相比，S&P 的差异点在于：拥有评级+指数+数据全链条，AI 分布在各业务线（终端、数据 API、指数、信贷工具），并用收购快速补齐 AI 能力。
- 资料截至 2026 年 9 月。




S&P Global 是纯 B 端、**纽约上市公司**（NYSE: SPGI）。它不是一家 "金融数据公司" 那么简单 —— 它同时拥有评级（标普评级）、指数（标普 500）、市场情报（Capital IQ Pro）和大宗商品数据（Platts）四大垄断性业务，相当于金融信息界的 "规则制定者"。AI 引擎 Kensho 是 2018 年花 5.5 亿美元买来的。

**AI 产品在干什么（四个层次）：**

1. **终端内做 AI 助手**——Capital IQ Pro 里的 ChatIQ 对话助手 + Document Intelligence 文档智能（跨海量文档自动研究，答案带精确引用、可审计），对标彭博 ASKB；
2. **把数据送进别人的 AI**——Kensho LLM-ready API 通过 MCP 协议接入 Anthropic Claude、AWS、Salesforce、Cohere，和 LSEG 打法相同；
3. **独特的 "卖铲子" 打法**——S&P AI Benchmarks：专门给各家大模型做 "金融能力评测排名"，顺便把配套评测数据集开源，试图定义金融 AI 的行业标准；底层工具（语音转写、PDF 提取、实体识别）也单独卖；
4. **把 AI 用进自己的老本行**——AI 增强指数（S&P 500 3AI 板块轮动指数）、Agentic 信贷备忘录生成器（Credit Memo Builder）。

**它的战略本质：** **收购补能力 + 开放生态 + 抢占标准**。自己不搞大模型，靠买（Kensho、ProntoNLP、Drift AI）补齐 AI 能力，再用评测基准建立话语权。

**做 "评测基准 / 标准" 占生态位** 学 S&P AI Benchmarks：发布一个 "中文金融 LLM 能力评测榜单"，不花大钱就能建立行业话语权和品牌势能，还能沉淀数据集 |
**用收购 / 小团队补齐能力，不搞大模型** 学它收购 ProntoNLP、Drift AI：买小团队做 "事件检测 / 情绪 / 自然语言建模" 这类单点能力，比自研快得多 
**文档智能带精确引用** 学 Document Intelligence 2.0：多文档研究分析 + 引用可审计，这是金融机构付费的核心诉求
