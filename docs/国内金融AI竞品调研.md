# 国内金融 AI 产品竞品调研



***

## 一、竞品分层总览



| 阵营          | 公司      | 代表 AI 产品                                   | 开源情况                  | 主要客户           |
| ----------- | ------- | ------------------------------------------ | --------------------- | -------------- |
| 金融 IT | 恒生电子    | LightGPT + 光子系列                            | LightGPT-7B 曾宣布面向机构开源 | 券商 / 基金 / 银行   |
|金融 IT | 金证股份    | K-GPT / K-CODE / KOCA-AI                   | 闭源（对接 DeepSeek 等开源底座） | 券商 / 基金 / 银行   |
|金融 IT| 顶点软件    | 智能体工场 / C6 AI / IM3                        | 闭源（接入 DeepSeek）       | 券商 / 资管 / 信托   |
| 金融数据 / 投研终端 | Wind 万得 | 万得 AI（Wind Alice）/ WindClaw / AIFin Market | 闭源（基于火山引擎豆包 + 本地精调）   | 机构 / 专业个人      |
| 金融信息 + AI   | 同花顺     | 问财 HithinkGPT / Indicator-Instruct         | 闭源（权重未公开）             | 券商 / 基金 / C 端  |
| 金融信息 + AI   | 东方财富    | 妙想金融大模型                                    | 闭源                    | C 端 / 零售       |
| 大厂互联网金融     | 蚂蚁集团    | 百灵 Ling / 支小宝 / 支小助                        | **开源（inclusionAI）**   | 支付宝生态 / 机构     |
| 大厂金融科技      | 京东科技    | 言犀大模型 / 言犀百晓                               | 闭源                    | 财富 / 零售 / 金融机构 |
| 大厂金融 AI     | 度小满     | 轩辕 XuanYuan 大模型                            | **开源（GitHub）**        | 信贷 / 理财 / 机构   |
| 云 / 平台型     | 百度智能云   | 千帆慧金金融大模型                                  | 闭源（文心底座，商业 API）       | 银行 / 金融机构      |
| 云 / 平台型     | 腾讯金融云   | 混元大模型 / 信贷助手                               | 混元基座部分开源，金融方案闭源       | 银行 / 保险 / 券商   |




***

## 二、分公司详细调研

### 1. 恒生电子 — LightGPT（光子系列）



* **公司类型**：金融 IT 服务商（行业龙头）

* **AI 产品**：


  * **LightGPT**：金融行业大语言模型，基于超 4000 亿 tokens 金融数据训练，覆盖投研、投顾、客服、合规风控、代码等场景。

  * **光子系列**：基于 LightGPT 的应用产品矩阵（投顾、客服、投研、运营、风控、合规、研发）。

  * **LightGPT 推理一体机**：基于昇腾 AI 软硬件，软硬一体私有化方案。

  * **LightGPTs**：金融大模型 + 插件一体化方案。

* **技术路线**：自研金融语料 + 通用底座；宣称模型效果提升 15%、安全合规性提升 13%、推理速度提升 50%。与信通院共建 L0-L1-L2 金融大模型评测标准。

* **部署**：支持私有化 / 云部署 / 灵活 API。

* **链接**：


  * 官方产品页：https://www.hundsun.com/lightgpt

  * 背景报道（上海证券报）：[https://company.cnstock.com/company/scp\_gsxw/202310/5137056.htm](https://company.cnstock.com/company/scp_gsxw/202310/5137056.htm)



***

### 2. 金证股份 — K-GPT / K-CODE / KOCA-AI



* **公司类型**：金融 IT 服务商

* **AI 产品**：


  * **K-GPT**：金融领域特定场景大语言模型（联合子公司金证优智发布）。

  * **K-CODE**：代码大模型。

  * **KOCA-AI 大模型应用平台**：支持快速开发 AI Agent，融合 RAG、K-GPT、K-CODE、Agent 技术；2025 年已全面对接 DeepSeek 主流模型。

  * 应用场景：投行、投研、投顾、风控、运营、客服、数智员工（与中信建投证券合作落地）。

* **技术路线**：自研垂直模型 + 拥抱开源生态（DeepSeek），RAG + Agent 工程化落地。

* **链接**：


  * 官网：[https://www.szkingdom.com/](https://www.szkingdom.com/)

  * KOCA-AI 平台介绍：[https://www.szkingdom.com/news/765](https://www.szkingdom.com/news/765)

  * 报道（证券时报）：[https://www.stcn.com/article/detail/1677849.html](https://www.stcn.com/article/detail/1677849.html)




***

### 3. 顶点软件 — 智能体工场 / C6 AI / IM3



* **公司类型**：金融 IT 服务商（券商新交易、财富管理、资管、信托）

* **AI 产品**：


  * **智能体工场**：自研智能体开发能力，已落地客户标签、客户服务、AUM 分析、合规管理、知识库等场景，累计落地 20+ 智能体应用。

  * **C6 平台 AI 增强**：财富管理平台智能化升级。

  * **IM3 系列**：AI 时代投资管理体系产品（资管），数字底座 IBLive。

  * 2025 年全面接入 DeepSeek，五大技术平台升级。

* **技术路线**：**不自研通用底座**，走 "接入 DeepSeek 等开源模型 + 自研智能体工场 + 业务场景嵌入" 路线，强调产品 AI 增强版本带来订单增量。

* **链接**：


  * 官网：[https://www.apexsoft.com.cn/](https://www.apexsoft.com.cn/)

  * 接入 DeepSeek 公告：[https://www.apexsoft.com.cn/news/show/id/421.html](https://www.apexsoft.com.cn/news/show/id/421.html)

  * A5 Max / 智能体落地报道：[http://www.cnstock.com/commonDetail/670617](http://www.cnstock.com/commonDetail/670617)




***

### 4. Wind 万得 — 万得 AI（Wind Alice）/ WindClaw / AIFin Market



* **公司类型**：金融数据终端（机构数据壁垒最强）

* **AI 产品**：


  * **万得 AI 个人版 / Wind Alice**：面向专业金融个人的 AI 原生工作平台，基于火山引擎豆包大模型 2.0 + 万得本地精调模型，主 Agent + 子 Agent + 金融 MCP 工具调用。https://alice.wind.com.cn/#/zh

  * **WindClaw**：一个入口同时调用 DeepSeek、智谱、豆包、Kimi、通义千问 5 大模型，直连 Wind 金融数据。投研专属 AI Agent 工作台。基于 OpenClaw 框架推出的投研专属 AI Agent 工作台。与通用版 OpenClaw 的核心差异在于数据底座：WindClaw 深度耦合了 Wind 专业金融数据库，可自动读取实时行情、财务数据、行业信息及合规公告，让 AI 在真实、权威的金融数据环境中完成投研任务，而非依赖公开互联网信息。

  * **AIFin Market**：金融 AI 生态平台，把 Wind 26 年数据封装为 MCP 与官方 Skills，供第三方 AI Agent 调用（按积分计费）。

* **技术路线**：**不拼自研基座，拼数据 + Agent 工具链**—— 把数据资产做成 MCP/Skills 生态，让 "你的 AI" 直接用 Wind 数据。

* **链接**：


  * 万得新闻中心：[https://www.wind.com.cn/mobile/News/zh.html?id=687](https://www.wind.com.cn/mobile/News/zh.html?id=687)

  * AIFin Market 介绍：[https://www.wind.com.cn/mobile/News/NewsDetail/zh.html?id=5ACF685BA1D584ED3C6966961A60F201](https://www.wind.com.cn/mobile/News/NewsDetail/zh.html?id=5ACF685BA1D584ED3C6966961A60F201)

  * Wind Client API：[https://www.wind.com.cn/mobile/ClientApi/en.html](https://www.wind.com.cn/mobile/ClientApi/en.html)

* **开源情况**：闭源；走 "数据 API + MCP 生态" 路线。



***

### 5. 同花顺 — 问财 HithinkGPT



* **公司类型**：金融信息 + AI（"互联网 + 金融 + AI" 第一股）

* **AI 产品**：


  * **问财 HithinkGPT**：金融大模型，提供 7B / 13B / 30B / 70B / 130B 五种版本，最大 32k 上下文；业内首家通过网信办备案的金融对话大模型。https://www.iwencai.com/screener

  * **问财智能体（2025 升级）**：从单一问答升级为 "边想、边查、边搜" 的自主规划推理 Financial Agent，主动拆解复杂投资任务。

  * **HiThinkGPT-Indicator-Instruct**：金融指标代码大模型，3000 万行真实策略代码预训练，支持自然语言画指标 / 写策略。

  * **AI PC 版**：与英特尔合作的端侧方案。

  * **同花顺 AI 开放平台**：面向机构输出 OEM、智能硬件、泛金融百科等能力。

* **技术路线**：从零自研，预训练金融语料达万亿级 tokens，覆盖股 / 债 / 期货 / 外汇 / 商品 / 宏观 / 行业数据。

* **链接**：


  * 问财百科（产品知识库）：[https://m.iwencai.com/yike/detail/auid/cbbafb47e7685c1d](https://m.iwencai.com/yike/detail/auid/cbbafb47e7685c1d)

  * 同花顺 AI 开放平台：[https://open.10jqka.com.cn/](https://open.10jqka.com.cn/)

  * 内测公告（上海证券报）：[https://company.cnstock.com/company/scp\_gsxw/202401/5171764.htm](https://company.cnstock.com/company/scp_gsxw/202401/5171764.htm)

  * 同花顺智能科技（机构输出）：[http://www.thsyun.com/](http://www.thsyun.com/)

* **开源情况**：闭源，权重未公开，通过 API / 私有化 / OEM 输出。



***

### 6. 东方财富 — 妙想金融大模型



* **公司类型**：金融信息 / 零售券商

* **AI 产品**：


  * **妙想金融大模型**：东方财富自研金融行业大模型，备案号 Shanghai-Miaoxiang-20231207。

  * **妙想 AI Agent**：从数据获取、信息整合、图表生成到解读分析的一站式投研助手。

  * 覆盖数百万金融指标、全品类数据流。

* **技术路线**：自研模型 + 自有零售流量与数据闭环，偏 C 端财富场景。

* **链接**：


  * 妙想产品官网：[https://ai.eastmoney.com/miaoxiang/](https://ai.eastmoney.com/miaoxiang/)

  * AI Agent 介绍：[http://ai.eastmoney.com/nlink/](http://ai.eastmoney.com/nlink/)

* **开源情况**：闭源。



***

### 7. 蚂蚁集团 — 百灵 Ant Ling / 支小宝 / 支小助



* **公司类型**：互联网金融 / 大厂

* **AI 产品**：


  * **百灵大模型（Ling 系列）**：自研全栈大模型家族，含 Ling（通用 MoE）、Ring（推理）、全模态系列；金融增强版 **Ling-3.0-flash-Fin** 已发布并开源，首次把 AI 推进真实投研工作流。

  * **支小宝 2.0**：面向 C 端的智能金融助理（后演进为支付宝 AI 生活管家）。

  * **支小助**：面向金融机构专家的智能业务助手，与合作机构内测共建。

* **技术路线**：自研全栈 + **完全开源路线**（inclusionAI 社区），从轻量到万亿参数（Ling-1T）全规模覆盖。

* **链接（开源）**：


  * 官网：[https://www.ant-ling.com/zh/](https://www.ant-ling.com/zh/)

  * 开发者文档：[https://developer.ant-ling.com/zh-CN/docs](https://developer.ant-ling.com/zh-CN/docs)

  * GitHub：[https://github.com/inclusionAI/Ling-V2](https://github.com/inclusionAI/Ling-V2)

  * HuggingFace：[https://huggingface.co/inclusionAI/Ling-1T](https://huggingface.co/inclusionAI/Ling-1T) （及同组织 Ling-2.6-flash / Ling-3.0 系列）

  * ModelScope：[https://modelscope.cn/models/inclusionAI/Ling-1T](https://modelscope.cn/models/inclusionAI/Ling-1T)

* **开源情况**：**已开源**（基座、Instruct、推理、多模态均在 HF / ModelScope 发布）。



***

### 8. 京东科技 — 言犀大模型 / 言犀百晓



* **公司类型**：大厂金融科技

* **AI 产品**：


  * **言犀大模型**：融合 70% 通用数据 + 30% 京东数智供应链原生数据，面向知识密集型任务型产业场景。有文字语音交互！！

  * **言犀百晓（金融大模型）**：财富管理场景，含 AI 理财顾问（C 端）、AI 驾驶舱（运营）、言犀解读 AI（机构投资者），覆盖投前 / 投中 / 投后。

  * **言犀 AI 开发计算平台 / 智能体平台**：集成 DeepSeek 等 20+ 开源模型，预置 1000+ 智能插件与 100+ 行业方案。

  * 金融领域还含 AI 增长营销平台、智能选基、金融增长云。

* **技术路线**：自研产业大模型 + 接入开源模型，营销 / 客服 / 数字人见长。

* **链接**：


  * 言犀平台：[https://yanxi.jd.com/](https://yanxi.jd.com/)


* **开源情况**：闭源。



***

### 9. 度小满 — 轩辕 XuanYuan 大模型



* **公司类型**：大厂金融 AI（百度系，独立运营）

* **AI 产品**：


  * **轩辕（XuanYuan）**：**国内首个开源千亿级中文金融大模型**，基于 BLOOM-176B / Llama2-70B 做中文与金融领域预训练 + 微调。

  * **轩辕 70B**：C-Eval、CMMLU 双榜开源第一，同时开源 50G 高质量金融语料。

  * **轩辕 - FinX1**：面向金融分析 / 决策 / 数据处理，带透明思维链（CoT）。

  * 内部应用：营销、客服、风控、办公、研发代码助手。

* **技术路线**：开源路线，降低金融机构部署门槛；上百家金融机构申请试用。

* **链接（开源）**：


  * GitHub：[https://github.com/Duxiaoman-DI/XuanYuan](https://github.com/Duxiaoman-DI/XuanYuan)

  * HuggingFace：[https://huggingface.co/Duxiaoman-DI](https://huggingface.co/Duxiaoman-DI)

  * 度小满官网：[https://www.duxiaoman.com/](https://www.duxiaoman.com/)

* **开源情况**：**已开源**（基座 + Chat + 量化版本 + 金融语料）。



***

### 10. 百度智能云 — 千帆慧金金融大模型



* **公司类型**：云 / 平台型金融科技

* **AI 产品**：


  * **千帆慧金金融大模型**：含知识增强版与推理增强版，8B / 70B 两档，32K 上下文；基于文心大模型 + 金融专用数据生成体系。

  * **千帆大模型平台**：从数据管理、训练、评估到部署的一站式工具链，支持金融机构用私域数据微调。

  * **开元智慧金融解决方案 2.0**：信贷审批、智能风控（百信银行 AIphaMo）、营销、客服等场景。

* **技术路线**：文心通用底座 + 金融行业 Know-How + 千帆平台工程化；百度智能云宣称金融行业中标量领跑。

* **链接**：


  * 千帆产品页：[https://cloud.baidu.com/product/qianfan.html](https://cloud.baidu.com/product/qianfan.html)

  * 千帆慧金发布（新华网）：[https://www.news.cn/tech/20250606/840da419e2104d6d901dfb525ee4660e/c.html](https://www.news.cn/tech/20250606/840da419e2104d6d901dfb525ee4660e/c.html)

  * 人民日报报道：[http://paper.people.com.cn/rmrb/pc/content/202609/09/content\_30180000.html](http://paper.people.com.cn/rmrb/pc/content/202609/09/content_30180000.html)

* **开源情况**：闭源（文心为商业模型，通过 API / 一体机输出）。



***

### 11. 腾讯金融云 — 混元大模型 / 金融行业方案



* **公司类型**：云 / 平台型金融科技

* **AI 产品**：


  * **腾讯混元大模型（Tencent HY）**：全链路自研，文本 / 多模态 / 代码；Hy4 preview 等基座已开源。

  * **混元大模型信贷助手**：基于 30+ 金融机构调研研发，多模态文档解析 + 智能提取 + 关联推理，对公尽调效率提升 10 倍，报告从 10 工作日压缩至 1 工作日，支持私有化部署。

  * **金融五维 AI 矩阵**：乐享 AI 知识库、信贷尽调助手、保险助手、舆情分析、智能风控（混元 + DeepSeek 双模驱动）。

* **技术路线**：自研混元 + 接入 DeepSeek，主打金融行业解决方案与私有化交付。

* **链接**：


  * 混元产品页：[https://cloud.tencent.com/product/tclm](https://cloud.tencent.com/product/tclm)

  * 金融场景方案：[https://cloud.tencent.com/developer/information/](https://cloud.tencent.com/developer/information/)腾讯云 ai 金融场景 - article

  * 信贷助手介绍：[https://developer.cloud.tencent.cn/article/2659775](https://developer.cloud.tencent.cn/article/2659775)

* **开源情况**：混元基座部分开源（GitHub 搜 Tencent/Hi 系列），金融行业解决方案闭源。



***

## 三、开源仓库汇总（可直接拉取）



| 厂商          | 仓库 / 模型地址                                                                            | 说明                                                                    |
| ----------- | ------------------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| 蚂蚁百灵        | [https://github.com/inclusionAI/Ling-V2](https://github.com/inclusionAI/Ling-V2)     | Ling 系列基座 + Instruct，HuggingFace `inclusionAI/Ling-*`                 |
| 度小满轩辕       | [https://github.com/Duxiaoman-DI/XuanYuan](https://github.com/Duxiaoman-DI/XuanYuan) | 千亿级中文金融大模型 + 50G 金融语料，HF



1. **底座路线已经分化为三派**：

* 自研垂直模型派：恒生 LightGPT、同花顺 HithinkGPT、蚂蚁百灵、度小满轩辕；

* 接入开源 + 场景派：顶点（DeepSeek）、金证（DeepSeek）、京东言犀；

* 数据 / 平台派：Wind（数据 MCP 生态）、百度千帆、腾讯金融云（行业解决方案）。


##三家直接同业深度拆解

### 一、恒生电子 — LightGPT / 光子系列

#### 1. 产品架构（三层）

| 层 | 产品 | 定位 |
|---|---|---|
| 模型层 | **LightGPT** | 自研金融大语言模型，超 4000 亿 tokens 金融数据训练；宣称效果 +15%、安全合规 +13%、推理速度 +50% |
| 中枢层 | **光子**（金融智能助手） | 金融应用对接大模型的"中控"，串联"通用工具链 + 金融插件 + 金融数据 + 业务场景"，解决大模型与实际应用之间的连接 |
| 应用层 | **光子·文曲 / 方圆 / 善策 / 慧营** | 面向具体业务场景的应用产品 |
| 投研平台 | **WarrenQ**（恒生聚源） | 面向投研投资场景的专业一体化投研工具平台 |

#### 2. 光子系列应用推测对应场景
- **文曲**：智能投研/投顾内容生成
- **方圆**：智能投顾/财富陪伴
- **善策**：合规风控
- **慧营**：智能营销运营
（具体命名对应以官方产品手册为准）

#### 3. 技术与交付
- **部署**：支持私有化 / 云部署 / 灵活 API；**LightGPT 推理一体机**基于昇腾 AI 软硬件，软硬一体开箱即用；**LightGPTs** 是"大模型 + 插件"一体化方案。
- **评测标准**：与中国信通院共建 L0-L1-L2 三层金融大模型评测体系。
- **技术平台归属**：LIGHT 技术平台（含 Light-JRES 微服务、Light-Atom 低码、Light-Bdata 大数据、LightDB 数据库、LightGPT、Light-DevOps）。

#### 4. 客户与商业化
- 已发布 **20+ 人工智能产品**，服务银行/证券/基金/期货，**超 500 个客户案例**，与 **20+ 家金融机构开展共建**。
- 与 O45 投资交易系统、UF3.0 新经纪系统等核心产品绑定销售，走"核心系统 + AI 增值"路线。
- 首席科学家白硕主导，技术声量大。

#### 5. 入口
- 官网：https://www.hundsun.com/light
- 背景：https://company.cnstock.com/company/scp_gsxw/202310/5137056.htm

---

### 二、金证股份 — K-GPT / KOCA-AI / KingClaw

#### 1. 产品架构

| 组件 | 说明 |
|---|---|
| **K-GPT** | 金融领域特定场景大语言模型（联合子公司金证优智/优智科技） |
| **K-CODE** | 代码大模型，配套编程助手 Copilot |
| **KOCA-AI 平台** | 大模型应用开发中枢，RAG + K-GPT/K-CODE + Agent 技术；已入围**深圳市人工智能行业应用示范标杆项目** |
| **KingClaw 智能体平台** | 企业级智能体平台，NL2SQL、NL2API、意图路由、文档解析等核心工具 |

#### 2. 业务场景落地（按产品线）
- **财富管理**：基于 **FS2.5 新一代核心交易系统**，打造"业务百事通""智能领航员"等智能体，检索专业知识库提升业务办理速度。
- **资管/投资**：基于 **A8 新一代投资交易系统**，构建智能交易、智能风控应用。
- **投行**：引入 **DeepSeek-R1**，实现招股说明书拆分、说明书与底稿关联、投行问答、说明书辅助撰写；技术方案是"规则+小模型预处理拆分 + R1 推理生成"。
- **机构运营**：开户、审核、数据分析等智能体矩阵，任务规划引擎 + 多模态识别。
- **客服/营销/风控/运营**：全覆盖。
- **标杆案例**：与中信建投证券合作"证券全场景数智员工体系"，入选大模型与智能体创新优秀案例。

#### 3. 技术路线特点
- **不自研全量基座**：自研 K-GPT 垂直模型 + **全面对接 DeepSeek 主流模型**（2025 年春节后），走"自研垂直 + 开源基座混合"路线。
- 强调从"云原生"迈向"AI 原生"架构，构建可衡量的业务价值闭环。

#### 4. 入口
- 官网：https://www.szkingdom.com/
- KOCA-AI：https://www.szkingdom.com/news/765
- 2025 年报（PDF）：https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-04-18/600446_20260418_26E0.pdf
- 投行 DeepSeek-R1：https://www.szkingdom.com/news/687

---

### 三、顶点软件 — LiveAgent 智能体工场 / C6 / IM3

#### 1. 产品架构

| 产品 | 说明 |
|---|---|
| **LiveAgent 智能体工场** | 自研智能体开发平台，"AI in ALL"全链路 AI 能力核心 |
| **C6 财富管理平台** | 新一代财富管理平台，逐步替代传统 CRM；AI 嵌入客户标签、客户服务、AUM 分析、合规管理、知识库 |
| **A5 Max / A5** | 新一代交易核心系统（业内率先实现全面国产替代上线） |
| **IM3 系列** | AI 时代投资管理体系（资管），数字底座 IBLive |

#### 2. 技术路线
- **完全不自研通用基座**：2025 年 2 月宣布**全面接入 DeepSeek**，走"开源基座 + 自研智能体工场 + 业务产品嵌入"路线。
- 已落地 **20+ 智能体应用**：客户探查、拜访计划自动生成、访谈记录/会议纪要自动整理、财富流程自动化。
- 生态：与海量数据合作向量数据库（CRM 系统中落地）；腾讯云金融科技核心合作伙伴。

#### 3. 客户与商业化
- **C6**：2026 年落地推广突破性进展，中标多家**信托机构**财富项目；客户群从券商拓展到公募基金、券商资管、银行理财子。
- 账户全景分析功能在**头部券商**落地，支撑买方投顾转型。
- AI 增强版产品已带来订单增量（2026 半年报明确）。
- 优势领域：新交易体系、数字财富、智慧运营、机构业务、服务信托。

#### 4. 入口
- 官网：https://www.apexsoft.com.cn/
- 接入 DeepSeek：https://www.apexsoft.com.cn/news/show/id/421.html
- A5 Max / 智能体落地：http://www.cnstock.com/commonDetail/670617

---

### 四、三家横向对比

| 维度 | 恒生 LightGPT | 金证 KOCA-AI | 顶点 LiveAgent |
|---|---|---|---|
| 基座策略 | **自研垂直模型**（LightGPT） | 自研 K-GPT + **对接 DeepSeek** | **纯接入 DeepSeek**，不自研基座 |
| 产品核心 | 光子"中控" + 光子系列应用 | KOCA-AI 平台 + KingClaw 智能体 | LiveAgent 工场 + C6/A5/IM3 产品嵌入 |
| 最强场景 | 投研（WarrenQ）、投顾、客服、风控 | 财富（FS2.5）、投行（招股书）、资管（A8） | 财富管理（C6）、运营自动化、资管（IM3） |
| 差异化 | 500+ 客户、20+ 共建、一体机软硬一体 | 投行场景深、数智员工标杆（中信建投） | 信托/资管客户拓展快、20+ 智能体已落地 |
| 交付方式 | 私有化/云/API/一体机 | 私有化 + 开源生态 | 私有化 + 产品 AI 增强版 |

