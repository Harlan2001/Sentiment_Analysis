# Bloomberg L.P. 金融 AI 产品速览

> 公司：**Bloomberg L.P.（彭博有限合伙公司）**，总部纽约的私人金融数据/媒体/终端公司，旗舰产品为 Bloomberg Terminal（机构订阅制）。

## 一、主推金融 AI 产品（精选 8 个）

### 1. BloombergGPT（自研金融大模型）
2023 年 3 月发布论文的 506 亿参数金融领域大模型，基于 BLOOM 架构，混合 3630 亿金融 token + 3450 亿通用 token 训练；权重未开源、无公开 API，能力内化于彭博自有产品。
- [arXiv 论文](https://arxiv.org/abs/2303.17564)
- [官方中文新闻稿](https://www.bloombergchina.com/press/bloomberggpt-50-billion-parameter-llm-tuned-finance/)

### 2. ASKB（Ask Bloomberg）<GO>（终端 Agentic 对话主入口）
2026 年 2 月 beta、2026 年 8 月扩展至移动端。用户用自然语言提问（可上传 PDF/Word），多智能体跨数亿文档、每日 5000+ 新闻、800+ 卖方研究统一检索，返回带出处引用的合成答案、可展开表格/图表，并自动生成 BQL 代码供 Excel/BQuant 复用；研究流程可存为 Workflow 模板。官方称底层为"多个商业 + 开放权重 LLM"，未点名厂商。
- [官方日文新闻稿（2026-02）](https://about.bloomberg.co.jp/blog/press-meet-askb-a-first-look-at-the-future-of-the-bloomberg-terminal-in-the-age-of-agentic-ai/)
- [官方 PR（移动端，2026-08）](https://www.prnewswire.com/news-releases/bloomberg-extends-askb-on-mobile-investment-ideas-dont-stop-when-financial-professionals-leave-the-desk-302853450.html)

### 3. Document Insights / Document Search & Analysis（文档智能）
2025 年 4 月上线单文档问答（对电话会 transcript/演示/投资者日材料自然语言提问，答案带原文锚点与音频回放）；2025 年 6 月宣布跨文档检索（跨 4 亿+ 文档做比较式问答，可一键 IB 联系作者、导入 RMS Enterprise）。
- [官方 PR（Document Insights，2025-04）](https://www.prnewswire.com/news-releases/bloomberg-accelerates-financial-analysis-with-gen-ai-document-insights-302421875.html)
- [官方 PR（Document Search & Analysis，2025-06）](https://www.prnewswire.com/news-releases/investors-to-streamline-alpha-generating-research-with-bloombergs-latest-ai-offering-302482328.html)

### 4. BQuant Enterprise Textual Analytics（自研金融 NLP 加购包）
在 BQuant 云沙盒内提供从零在金融语料预训练的 Bloomberg BERT（官方称二进制分类比开源 BERT 高约 10%）+ T5 摘要模型 + 带置信区间的实体情感分，语料回溯至 2007 年并带 point-in-time 时间戳，供量化团队做情感、违约概率、事件套利回测。
- [官方产品 PDF](https://assets.bbhub.io/professional/sites/41/BQuant-Enterprise-Textual-Analytics.pdf)

### 5. Bloomberg Law AI（BLAW）
2025 年 1 月起在 Bloomberg Law Web 端上线 grounded 于自有 1550 万+ 判例的 AI Assistant/Answers（内容不足即拒答，不接互联网）；2026 年走向 agentic Deep Research，并于 2026 年 8 月 ILTACON 推出 BLAW AI + Workspaces + AI Agents，通过 MCP 协议接入 Anthropic Claude。
- [官方 AI 产品页](https://pro.bloomberglaw.com/products/ai-and-bloomberg-law/)
- [官方新闻稿（ILTACON 2026）](https://pro.bloomberglaw.com/insights/company-news/bloomberg-law-unveils-new-ai-powered-legal-intelligence-experience-at-iltacon-2026/)

### 6. Bloomberg Tax AI
2025 年 3 月上线 grounded 于 IRC/税务机关文件/Tax Management Portfolios 的 Tax AI Assistant（搜索页直接给带引答案、一键建跨辖区对比图）；2026 年 3 月 TEI 会议推出 agentic Deep Thinking Mode（反问澄清→研究计划→多步执行→带逻辑链报告）；2026 年 8 月把 AI Research Assistant 内嵌进下一代 Tax Provision。
- [官方新闻稿（2025-03）](https://www.bloombergindustry.com/press-releases/new-ai-features-from-bloomberg-tax-accounting-simplify-complex-tax-research/)
- [官方 TEI 2026 新闻稿（Deep Thinking Mode）](https://pro.bloombergtax.com/insights/company-news/bloomberg-tax-showcases-industry-leading-ai-powered-tools-at-tei-midyear-2026/)

### 7. Bloomberg Regology（AI 监管变更管理）
2026 年 6 月 Bloomberg Industry Group 收购 Regology 后品牌化。AI agents 持续追踪美国联邦/州及 135+ 国家法规变更，把变更直接映射到内部政策、风险与控制，覆盖 horizon scanning→影响评估→合规行动全流程。
- [官方收购稿（2026-06）](https://www.bloombergindustry.com/press-releases/bloomberg-industry-group-regology/)

### 8. ESG / SFDR ML 排放估算
对约 10 万家不披露排放的公司用"瀑布式"方法估算 Scope 1/2/3：自报数据→800+ 特征的 ML 智能模型→行业隐含兜底层，附 PCAF 可靠性评分，供资管做组合碳足迹与 SFDR 合规。
- [官方新闻稿](https://www.bloomberg.com/company/press/bloomberg-increases-carbon-emissions-data-to-cover-100000-companies/)

## 二、GitHub 开源情况

- 官方 GitHub 组织：<https://github.com/bloomberg>
- 与金融数据/API 直接相关的开源 SDK：
  - <https://github.com/bloomberg/blpapi-python>（Python SDK）
  - <https://github.com/bloomberg/blpapi-java>（Java SDK）
  - <https://github.com/bloomberg/blpapi-node>（Node SDK）
  - 官方开发者文档站：<https://bloomberg.github.io/blpapi-docs/>
- **BloombergGPT 未开源**，无官方代码/权重仓库，仅以学术论文形式发布（见上方 arXiv 链接）。

## 三、说明

- 彭博为私人公司（无公开股票、无公开财报），多数 AI 产品的定价、具名客户、底层模型厂商均未披露；本速览链接均取自已核验的官方或权威来源。
- 资料截至 2026 年 9 月。

彭博是纯 B 端、且是**私人公司**（不上市）。核心产品是 Bloomberg Terminal 终端，向全球金融机构卖 "订阅席位"，年费数万美元 / 座，客户黏性极强 —— 金融从业者的桌面标配。

**AI 产品在干什么（三个层次）：**

1. **自研大模型打底**——2023 年发布 506 亿参数的 BloombergGPT（金融领域大模型），但不对外开放、不做 API，能力全部内化到自家产品里，纯粹是终端的 "内功"；
2. **终端内做 Agentic 助手**——ASKB 是主入口：用户自然语言提问，AI 跨数亿文档、每日 5000+ 新闻自动检索，答案带出处引用、可生成图表和代码（BQL），还能把研究流程存成模板复用；配套的 Document Insights 做单文档 / 跨文档问答；
3. **垂直领域逐个击破**—— 把数据优势做成行业 AI：法律（BLAW，grounded 于 1550 万 + 判例）、税务（Tax AI）、监管变更（Regology）、ESG 碳排放估算，每个领域都做 "AI + 专有数据" 的闭环产品。

**它的战略本质：** 与 LSEG 完全相反 ——**自研 + 内化**。模型不外卖、数据不出终端，AI 是用来增强终端订阅价值、锁住客户续费的武器。连底层模型也部分自研（Bloomberg BERT），最近才通过 MCP 接 Anthropic。