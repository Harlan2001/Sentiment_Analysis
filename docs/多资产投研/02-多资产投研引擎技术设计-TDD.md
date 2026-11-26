# 多资产投研引擎技术设计（TDD）

> 状态：Draft  
> 版本：v0.1  
> 日期：2026-11-25  
> 目标：以统一引擎承载中国国债、信用债、国债期货和美债投研链路

## 1. 设计背景

当前系统的中国国债能力分散在多个相关但未完全编排的模块：

- \`backend/analysis\` 将新闻按中国国债口径写入 \`analysis/news_factor\`，并独立生成10Y收益率预测；
- \`backend/evaluation\` 的离线脚本以 \`news_factor + yield_data\` 计算T+1/T+5/T+20事件研究，当前存在混合模型、非交易日跳过和缺少可用时间的问题；
- 账号级研究组合、组合配置约束建议、政策、研报和新闻总结是并列工作流；
- \`backend/strategy\` 读取新闻、因子、事件研究先验和中债曲线构建情报包，经用户确认后调用外部 DreamStrategy；它不自动读取预测报告或账号级组合；
- \`frontend/src/features/market\` 已有市场、因子、收益、预测、组合和事件研究页面，但总首页部分行情和信号仍是静态演示。

数据与工具现状：

- 仓库内未发现商业金融数据供应商适配器；信用曲线、中金所会员排名和美债收益率分别由中债、中金所、美国财政部公开接口直接同步，供应商采购及新闻入库链路不在本仓库中；
- 三个同步接口由HTTP请求或回填脚本触发，未发现纳入统一调度器的定时数据同步；现有持久化按业务键幂等更新，但信用曲线和美债收益率会覆盖同键旧值，不具备修订链；
- 当前Agent工具查询库内新闻、因子、预测、宏观等数据及用户授权的飞书内容，没有通用互联网搜索工具；联网搜索尚未进入当前新闻分析、预测、政策或研报主链路；
- 新闻分析的大模型输入是库内新闻标题、正文、发布日期和因子字典；10Y预测另读取新闻分析、收益率和市场摘要；政策与研报分析分别读取用户上传的PDF解析结果；
- 已有上传包括：文本型政策PDF（20MB、按用户去重）、研报PDF解析与AI分析、固定格式研究组合CSV（1MB、1000行）及个人Skill附件。它们不等于通用结构化行情导入；研报现有浏览与隔离规则也不能直接视为目标组织级数据隔离；
- 现有因子表主要保存`code/name/category/factor_type`，类别为POLICY、MACRO、LIQUIDITY、RISK、SENTIMENT、INDUSTRY；新因子发现按0.7相似度阈值直接加入标准库或丢弃，虽保存发现历史，但没有独立AI审核、应用级资格或完整生命周期；
- 当前因子活跃度直接聚合`news_factor`记录，新闻重要性则将方向、模型一致性、期限、类别、事件研究先验等九类信号合成为既有0—100分。两者继续服务中国国债旧页面，但不作为新增资产评价契约。
- 当前关注列表按账号保存`news/factor/macro_signal`三类对象及标题、来源URL和自由元数据，只提供增删查与页面聚合，没有版本化监测规则、调度、去重或提醒记录；
- 当前综合研报生成按账号保存来源快照、`version_no/parent_task_id`，支持再生成、失败重试、软删除、恢复和永久删除，但没有研究案例绑定、动态/正式报告分层、许可过滤或PDF/Word/Excel/CSV/Markdown统一导出链路；
- 当前项目权限的有效语义是`manager/editor`：创建者写入`manager`，新增成员接口只接受`editor`；旧`owner/viewer`在读取时分别兼容映射为`manager/editor`。当前没有项目或研究案例所有权转移接口，不能把目标转移能力描述为已实现。

因此本设计不把现状描述为完整流水线，也不复制三套资产代码。目标是在不改变现有中国国债逻辑的前提下，先建立最小公共契约，再按资产增加适配器和专业能力。

## 2. 设计目标

1. 为行情、事件、因子、统计验证、预测和策略建立最小公共契约，不强行统一资产算法。
2. 首个可交付版本优先打通市场研究、事件/证据、因子或定性判断、研究案例和正式报告；AI预测与统计验证不是完成研究闭环的技术前置，统计验证和可交易策略继续按能力门控开放。
3. 资产专属逻辑通过配置、适配器和专属服务实现。
4. 保持现有中国国债 API、页面和 DreamStrategy 链路兼容。
5. 所有时间、方向、目标指标、数据状态和能力状态具有显式语义。
6. 新增或改造的离线任务幂等、可补跑、可观测；现有任务基础设施按阶段扩展。
7. 支持旁路读取、双轨运行和逐步迁移，不要求一次性改造全部旧表。
8. 以来源授权和用途为边界管理供应商、官方、搜索、上传与内部数据；大模型知识不作为实时金融事实源。
9. 建立兼容旧因子ID的公共/资产命名空间、自动审核、生命周期、分项评价、冲突和轻量传导关系契约。
10. 建立兼容现有账号级研究组合的目标配置/模拟持仓、多币种风险结果、资产计算器、覆盖率和情景分析契约，不把研究配置升级为真实账户系统。

## 3. 非目标

- 不在本设计中实现真实交易和订单管理。
- 不统一所有行情供应商协议，仅定义适配器接口。
- 不把不同资产强制映射到同一种收益算法。
- 不在第一阶段迁移全部历史数据。
- 不在供应商盘点前指定厂商、接口或新增采购方案。
- 不在本轮锁定联网搜索供应商、接口、触发阈值或预算，也不锁定上传格式全集、SLA数值、质量阈值、物理存储或统计样本数。
- 不在MVP建设复杂审批平台、知识图谱、图数据库或自动因果推断引擎，也不锁定因子清单、评分公式、状态阈值和传导模板。
- 不在MVP建设真实持仓接入、成交与订单管理、实时账户级保证金/强平监控、大型实时风控引擎，也不强制实现VaR、ES、蒙特卡洛、完整现金流重估或关键期限风险模型。

## 4. 总体架构与闭环边界

三类闭环分别建模和验收：

| 闭环 | 核心产物 | 开放条件 | 不得混用 |
|---|---|---|---|
| 研究闭环 | 异常、解释、传导、风险、后续关注 | 新增资产MVP必须具备 | 不宣称统计有效或可交易 |
| 统计验证闭环 | 固定目标指标、样本、窗口、基准和稳定性 | 历史数据、时间对齐和目标指标可靠 | 不称为策略PnL |
| 可交易策略闭环 | 可交易标的、执行规则、成本、成交、回测和验收 | 行情、标的和DreamStrategy均确认支持 | 不以收益率或利差代理替代真实成交 |

首个可交付研究闭环不要求每个事件都产生AI预测或统计结果。证据足以支持定性分析时，可直接形成版本化判断、案例引用和正式报告；缺少的预测/验证状态和适用限制必须显式保存。组合风险、持续监测和新增资产策略回测采用可插拔接口分期接入，不能因此改写或削弱现有中国国债组合、预测、策略生成和回测链路。

```text
数据源
 ├─ 专业信息供应商（主要金融数据）
 ├─ 官方数据与公司内部数据
 ├─ 库内新闻、政策、研报与按需联网证据
 └─ 用户上传材料或结构化数据
        │
        ▼
来源授权门控 → 数据源适配器 → 批次/版本 → 标准化观测
        │
        ├──────────────┐
        ▼              ▼
资产事件分析      行情与收益计算
        │              │
        ▼              ▼
事件因子序列 ──→ 信号评估/事件研究
        │              │
        └──────┬───────┘
               ▼
       预测、组合风险与研究情报
               │
       ┌───────┴─────────────────┐
       ▼                         ▼
  报告/对话       能力门控 → 策略情报包 → DreamStrategy
```

该图是目标能力关系，不代表所有环节必须组成单一自动任务。预测、统计验证、报告和策略可以共享数据与快照，但保留独立触发、状态和失败边界。

## 5. 资产配置协议

建议新增：

```python
@dataclass(frozen=True)
class AssetResearchProfile:
    asset_scope: str
    display_name: str
    instruments: tuple[str, ...]
    default_instrument: str
    benchmark: str
    direction_axis: str
    timezone: str
    calendar: str
    horizons: tuple[str, ...]
    factor_namespaces: tuple[str, ...]
    forecast_targets: tuple[str, ...]
    market_adapter: str
    return_calculator: str
    event_alignment: str
    backtest_adapter: str
    strategy_adapter: str
    prompt_template: str
    supported_granularities: Mapping[str, tuple[str, ...]]
    direction_rules: Mapping[str, str]
    capability_states: Mapping[str, str]  # unavailable/partial/research_ready/validation_ready/tradable_ready
```

首批配置：

| `asset_scope` | 当前可用研究对象 | MVP目标指标 | 条件开放指标 |
|---|---|---|---|
| `cn_gov_bond` | `CN_GB_10Y`及现有本地国债数据 | 现有`yield_change_bp` | 价格回报、总回报及现有DreamStrategy支持范围 |
| `credit_bond` | 整体中短期票据曲线，期限按现有数据选择 | `credit_yield_change_bp` | 口径匹配后的整体/分层`credit_spread_change_bp`、`excess_return`和总回报 |
| `cn_treasury_futures` | `TS/TF/T/TL`会员持仓排名及来源提供的具体合约 | `position_structure`；事件方向以`futures_price`定义但不做行情验证 | `futures_return`/`basis`/`CTD`/`IRR` |
| `us_treasury` | `UST_2Y/10Y/30Y`及同日中美利差 | 2Y/10Y/30Y`yield_change_bp`及曲线变化 | 其他期限、价格/总回报及可交易ETF/期货收益 |

粒度按“资产×功能×数据能力”配置：同一资产可以允许主体级事实提取，但定量分析仅到曲线或品种级。方向使用第7节双轴契约；旧中国国债 `positive/negative` 通过只读适配器映射，原字段和业务逻辑不变。

## 6. 时间模型

所有数据和结果统一保留以下时间：

| 字段 | 含义 |
|---|---|
| event_time | 事实发生时间或已确认安排的计划时间 |
| published_at | 来源首次公开发布时间 |
| source_timezone | 原始时间所属时区 |
| time_precision | 时间精度：日期、分钟或更精细级别 |
| observed_at | 行情对应的市场时间 |
| available_at | 数据在现实世界中可被策略使用的最早时间 |
| ingested_at | 系统采集时间 |
| processed_at | 模型或任务处理时间 |
| decision_time | 研究、验证或回测作出决策的时间 |
| execution_time | 策略允许模拟成交的时间；非交易研究可空 |
| aligned_at | 按市场日历、时段和观测频率映射后的基准时点 |
| as_of | 研究结果使用的数据截止时间 |

规则：

1. 回测只允许使用`available_at <= decision_time <= execution_time`的数据；事件研究的观察时点不等于策略可成交时点。
2. 来源发布时间不等于事件发生时间；信号只能从现实可用时间起使用，不得以分析或入库时间回填。
3. 精确时间已知时，由资产交易时段和行情观测频率映射盘前、盘中或盘后；只有日期时默认进入信息已可用后的下一有效交易时点，周末和节假日顺延而非丢弃。
4. `available_at`无法可靠确定时，允许保留案例和定性研究，但阻断正式事件研究、预测评估和策略回测；只有日频数据时不得输出盘中反应结论。
5. 每个事件研究定义`T`为映射后的市场观察基准，`T+N`为该资产日历上自T之后第N个有效观察时点；是否包含T、使用开盘/收盘/结算价及起算方式由版本化规则声明。
6. 跨市场事件分别维护源市场和目标市场的日历、时段、时区、时间精度、反应窗口与先后顺序；两地同名T+N不要求对应同一自然日期。
7. 美债保存原始美东时区并统一转换为UTC和展示时区，夏令时由市场日历规则处理；MVP只实现可靠日频中美对齐。
8. 期货换月信息、信用历史评级、宏观预期和数据修订的可用时间不得晚于决策时间。
9. 市场预期、研究预测和已发生事实分别保存；只有符合事实状态和可用时间要求的事件进入事实事件统计样本。
10. 现有中国国债日期对齐逻辑保持不变，由兼容层标注其时间精度、适用范围和局限。

## 7. 方向与目标指标

通用影响结果采用双轴方向模型，至少表达：

```text
asset_scope
instrument_id
target_metric
target_direction  # up/down/flat/unknown
market_effect      # bullish/bearish/neutral/mixed/unknown
position_view      # 可空，仅在持仓方向或组合暴露明确时使用
horizon
analysis_state     # not_analyzed/no_significant_impact/insufficient_evidence/impact_identified/analysis_failed
strength
confidence
reason
```

规则：

1. `target_direction`只描述指标变化；`market_effect`描述明确参考视角下的市场效果，不等同于用户持仓盈亏。
2. 证据不足使用`analysis_state=insufficient_evidence`，不得写成`neutral`或`flat`；没有影响记录只表示未形成该条判断。
3. 收益率与债券价格、期货价格与隐含收益率等确定关系优先由规则映射；规则结果与模型输出冲突时，不发布矛盾结论并记录校验失败。
4. 基差、期限利差等无统一利好利空定义的指标可只输出`target_direction`和专业解释，`market_effect`为`unknown`或按明确策略视角填写。
5. 中国国债旧结果由`CnGovBondLegacyAdapter`映射到双轴读取模型，不修改旧表、旧字段或旧写入逻辑。

## 8. 数据模型

### 8.1 数据源、适配与授权

| 来源层 | 目标定位 | 当前代码事实 | 接入约束 |
|---|---|---|---|
| 专业信息供应商 | 主要金融信息及市场数据 | 未发现商业供应商适配器；供应商、接口、覆盖和授权待公司盘点 | 已有资源优先；不足时再评估官方补充或采购，不预设厂商 |
| 官方数据 | 权威事实、正式政策和基础行情补充 | 已直连中债网整体信用曲线、中金所会员持仓、美国财政部2Y/10Y/30Y收益率 | 遵守发布日历、使用条款和修订规则 |
| 联网搜索 | 最新信息、原始来源与证据核实 | 未发现通用互联网搜索工具进入现有分析主链路；Agent检索的是内部API和授权飞书内容 | 按任务可选触发；记录链接、发布时间和获取时间，未核实不得作为权威数值或正式验证样本 |
| 用户上传 | 用户或组织授权范围内的研究材料与数据 | 已支持政策PDF、研报PDF、固定格式组合CSV及个人Skill附件；未发现通用市场数据导入 | 非结构化材料与结构化数据分流；默认隔离，不覆盖供应商数据 |
| 公司内部数据 | 授权范围内补充研究和业务数据 | 具体数据集与权限待盘点 | 经权限、用途和对外传输校验后接入 |
| 大模型自身知识 | 解释、理解、推理和生成 | 当前分析输入来自库内新闻、因子字典、行情摘要或上传文本 | 不作为独立实时事实源，不得补造行情、公布值、评级或交易价格 |

新数据源经适配器输出统一语义：资产、标的、指标、值、单位、观测时间、发布时间、可用时间、获取时间、来源、批次/版本、质量状态和授权用途。字段及物理表在数据盘点后确定，不在本轮锁定。

同一指标的来源优先级必须按用途、口径和授权配置；发生冲突时保留原值与来源，执行可解释的选源或阻断，禁止无条件平均、拼接或覆盖。授权不足是硬阻断，不能用警告、降级或用户上传绕过。

### 8.2 逻辑模型与MVP取舍

以下实体是逻辑边界，不是已锁定的数据库DDL。具体表名、字段类型、唯一键和任务执行方式在后续技术讨论及代码验证后确定。MVP只实现用例需要的最小持久化，禁止为了“统一”复制现有表的全部数据。

每张新表落地前必须说明：解决的查询或复现问题、旧表不能满足的原因、写入责任方、保留周期、授权边界、迁移与回滚方案。

#### research_asset

资产定义与启用状态：

```text
asset_scope PK
display_name
timezone
calendar_code
enabled
profile_version
created_at
updated_at
```

#### research_instrument

```text
instrument_id PK
asset_scope
symbol
name
instrument_type
currency
tenor
rating
sector
metadata_json
valid_from
valid_to
```

#### research_market_observation

```text
id PK
asset_scope
instrument_id
metric
observed_at
published_at
available_at
ingested_at
value
unit
source
batch_id
source_version
quality_flags_json
UNIQUE(instrument_id, metric, observed_at, source)
```

#### research_market_performance

统一市场表现逻辑契约，不代表指标可直接比较，物理表和公式后续确定：

```text
id PK
asset_scope
instrument_id
target_metric
start_value
end_value
change_value
unit
start_at
end_at
horizon
calculation_method
benchmark_id NULL
source_references
data_snapshot_id
quality_status
calculator_version
```

资产计算器负责金融语义：收益率和利差输出bp变化；期货分别输出持仓变化、合约价格/结算价收益和策略PnL；债券总回报必须包含价格变化、票息及已声明口径。跨资产汇总只能比较经过明确定义的标准化结果，不得直接排序不同指标的原始`change_value`。

#### 公共事件、证据与影响判断

| 逻辑实体 | 最小语义 | 约束 |
|---|---|---|
| public_event | 规范化事件事实、事实状态、事件时间 | 事件只保存一次；候选事件须核查和去重 |
| event_family | 同一主题或过程下的事件族、主事件与独立子事件 | 子事件只有包含独立新增信息时才形成独立样本 |
| evidence_item | 稳定证据ID、来源引用、来源类型、内容性质、发布时间、可用时间、入库时间及内容版本 | 新闻、政策、研报、行情、统计结果均可作为证据；事实、观点、预测、预期和未来安排分离，各类型使用专业详情渲染器 |
| evidence_reference | 证据类型/ID/版本、被引用对象、支持/反驳/补充关系、引用片段或定位、引用时点 | 统一引用和返回契约，不复制全文；版本缺失时不得自动改指最新内容 |
| event_evidence_link | 事件与证据引用的关联及支持/反驳/补充关系 | 同一事件可关联多个来源，正反证据并列 |
| event_impact_assessment | 事件对资产、标的、目标指标和周期的独立影响判断 | 使用双轴方向和分析状态；不强制覆盖四类资产 |
| event_observation_window | 事件、目标指标、T与结束时点、市场日历、重叠及干扰事件 | 映射规则和窗口定义带版本 |
| research_sample_eligibility | 研究类型、样本资格、排除原因和规则版本 | 规则预先定义，不得按事后结果筛选 |

影响记录缺失不能推导为“无显著影响”。若资产被纳入分析范围，任务或影响判断必须显式记录未分析、无显著影响、证据不足、存在影响或分析失败，并保留依据、传导路径、置信度、模型和快照。完全重复报道只关联为证据；后续更新、独立子事件和其他市场事件分别保存时间与新增信息，不因同属事件族而无条件合并。

#### 因子字典、映射与生命周期

| 逻辑实体 | 最小语义 | 约束 |
|---|---|---|
| factor_definition | 稳定因子ID、公共或资产命名空间、标准名称、分类、版本、状态和有效期 | 定义不绑定固定资产方向；具体表名与字段待定 |
| factor_alias_mapping | 原始模型标签、别名、标准因子、映射依据、模型和提示词版本 | 保留历史映射；相似名称不能替代金融语义判断 |
| factor_review_run | 独立AI审核输入、结论、证据、冲突和程序校验结果 | 与提取任务及提示词隔离；同一模型可独立调用 |
| factor_lifecycle_event | 状态前后值、原因、证据、生效时间、影响范围和版本 | 只追加历史，不物理删除退休因子 |
| factor_application_state | 资产、标的、目标指标、周期下的统计、预测和策略使用资格 | 单一应用失效不改变公共因子全局状态 |

现有中国国债因子ID和表不迁移、不回写；兼容适配器把旧类别与ID映射到公共读取模型。新资产先复用六个既有公共类别，再通过`credit.*`、`futures.*`、`ust.*`等逻辑命名空间表达评级、期现、拍卖等专业差异；具体因子清单和物理编码后续确定。

#### research_factor_event

```text
id PK
event_id
impact_assessment_id NULL
factor_id
raw_factor_label
factor_mapping_version
asset_scope
instrument_id NULL
target_metric
target_direction
market_effect NULL
strength
confidence
driver
model
event_time
available_at
```

#### 结构化传导关系

| 逻辑实体 | 最小语义 | 约束 |
|---|---|---|
| transmission_template | 可复用候选机制、适用资产/指标、条件和不适用条件 | 不保存无条件固定方向，不代表因果成立 |
| event_transmission_relation | 来源事件或源指标、目标资产/指标、方向、直接/间接/共同因素、机制、周期、条件、证据、不确定性、推断类型和验证状态 | `mechanism/ai_inference/case_association/statistical_association`分开；同一事件允许多路径及相反结果，MVP使用关系型存储 |

验证状态至少区分`hypothesis`、`case_supported`、`statistically_supported`、`insufficient_evidence`和`not_supported`。统计支持只表示在定义样本与方法下存在支持，不升级为因果证明。

#### research_signal_evaluation

```text
id PK
asset_scope
instrument_id
factor_id
target_metric
horizon
sample_start
sample_end
sample_count
avg_move
hit_rate
majority_base
volatility
uncertainty_json
market_regime
eligibility_state
calculation_version
metadata_json
computed_at
UNIQUE(asset_scope, instrument_id, factor_id, target_metric, horizon, sample_end)
```

#### research_forecast

```text
id PK
forecast_run_id
asset_scope
instrument_id
target_metric
forecast_type
forecast_horizon
observation_count
calendar_id
as_of
forecast_start_at
forecast_end_at
generated_at
data_cutoff_at
result_state
target_direction
probability_json nullable
expected_move nullable
prediction_interval_json nullable
model_confidence_level nullable
evidence_quality
calibration_state
statistical_uncertainty_json
assumptions_json
invalidations_json
reverse_risks_json
degrade_or_refusal_reason nullable
recovery_conditions_json
evidence_snapshot_id
context_snapshot_json
model
model_version
prompt_version
parent_forecast_id nullable
```

`result_state`至少区分`normal/degraded/insufficient_evidence/signal_conflict/target_not_enabled/system_failed/expired`。前六类中，除`system_failed`外均是可审计业务结果；拒绝类不得写成`neutral`。概率、幅度和区间字段按预测类型与能力白名单可空，不能以默认值补齐。该结构是逻辑契约，具体物理拆表待实现设计确定。

#### forecast_capability_registry

按`asset_scope + instrument_id + target_metric + forecast_horizon + forecast_type`登记能力状态、所需数据级别、评估状态、生效版本和开放条件。中国国债旧10Y日/周/月链路经兼容适配器登记为既有能力，不改变旧表、提示词或生成逻辑；新增资产只有注册项通过对应门控后才能生成正式预测。

#### forecast_model_output与forecast_evaluation

多模型调用按运行和模型分别保存输入快照、输出、模型/提示词版本、生成时间及执行状态；共识结果仅引用这些不可变子结果。评估记录保存实际结果版本、目标判定规则、样本资格、市场阶段、基准、指标及计算版本，并区分真实时点预测与事后模拟预测。

#### strategy_instrument_capability_registry

可交易策略能力按具体标的登记，不用资产类别、研究指标或白名单成员身份替代验证证据：

```text
id PK
instrument_id
external_instrument_mapping
asset_scope
instrument_type
symbol_role                 specific / main / continuous / research_only
frequency_set_json
history_coverage_json
direction_set_json
order_type_set_json
cost_model_capability
execution_limits_json
capability_state            not_enabled / configured / basic_validated / formal_research_backtest
evidence_type
evidence_reference
validated_at nullable
limitations_json
registry_version
effective_from
```

状态只能随证据升级：本地白名单、外部API接受、单个代码样例或单次成功运行最多证明`configured`；`basic_validated`至少需要受控的预期成交测试及可复核结果；`formal_research_backtest`还需历史数据、真实标的映射、成本、成交、结算、核算、复现及安全契约共同通过。能力登记可先由轻量配置实现，不要求MVP立即新建物理表。

当前代码事实的保守初始映射为：`FCT_T_MAIN`依据代码注释所称既有成交记录暂列`basic_validated`，但仍需补可复核运行记录；`100040`只是该符号的兼容别名且没有独立证据，列`configured`；`FCT_TS_MAIN`、`FCT_TL_MAIN`、`IBK_G10Y_ACTV`、`IBK_CDB10_ACTV`列`configured`。其他信用债、美债及未登记标的默认`not_enabled`。这些状态不等于正式研究回测资格。`FCT_*_MAIN`的外部定义、真实合约映射、连续序列构造、换月与PnL必须分别验证；信号序列不能直接当作可执行合约。

#### research_strategy_business_version与strategy_execution_attempt

```text
research_strategy_business_version
  id PK
  parent_version_id nullable
  asset_scope
  instrument_id
  capability_registry_version
  strategy_mode
  requirement_snapshot_json
  context_id
  capital_spec_json
  period_spec_json
  rule_spec_json
  position_spec_json
  cost_fill_spec_json
  confirmation_state
  confirmed_by nullable
  confirmed_at nullable
  requirement_hash
  created_at

strategy_execution_attempt
  id PK
  business_version_id
  idempotency_key
  external_request_id nullable
  attempt_no
  lifecycle_status
  code_version nullable
  started_at nullable
  finished_at nullable
  failure_category nullable
  error_message nullable
```

标的、模式、交易逻辑、期间、参数、仓位、成本、资本或关键数据变化时创建新业务版本并重新确认；只改展示名称不新建业务语义。网络重试、同请求幂等重放或不改变语义的有限技术修复只增加执行尝试，任何金融或执行语义变化必须升版。

#### research_backtest_run

```text
id PK
business_version_id
execution_attempt_id
asset_scope
instrument_id
capability_registry_version
strategy_type
lifecycle_status
research_quality_status
performance_status
data_snapshot_id
historical_feature_snapshot_id
parameter_json
initial_capital
capital_denominator_definition
cost_model_version
fill_model_version
settlement_model_version
accounting_model_version
benchmark
metrics_json
trades_json_or_uri
zero_trade_reason nullable
code_version
selection_history_json
started_at
finished_at
error_message nullable
```

生命周期至少区分`draft/pending_confirmation/confirmed/generating/executing/completed/failed/cancelled`；研究质量区分`unevaluated/insufficient/experimental/formal_research_usable`；表现评价区分`good/not_outperforming/unstable/insufficient_evidence`。三组状态不得互相推导：`formal_research_usable`只说明方法、数据、成本、执行和复现通过，不表示盈利或未来可用。

#### research_strategy_context

保存按需构建、版本化且不可变的策略情报包：

```text
id PK
asset_scope
instrument_id
as_of
data_cutoff_at
profile_version
capability_registry_version
instrument_capability_json
market_history_references_json
requirement_cost_execution_json
event_factor_evidence_json nullable
forecast_reference_json nullable
portfolio_risk_constraint_json nullable
quality_source_missing_json
historical_feature_snapshot_id nullable
model
prompt_version
context_version
token_budget
created_at
```

构建器按令牌预算、证据质量和需求相关性筛选，执行去重与冲突保留，不将全部原始新闻或指标直接塞入提示词。设计时上下文用于形成业务版本；历史特征快照只包含每个历史决策时点已经可用的信息。当前新闻、当前预测、当前组合风险和事后统计不得回填历史运行。真实历史预测必须具有当时生成时间与版本；当前模型的历史回放另标`back_simulated`，数据截止时间不能消除模型训练期或世界知识带来的前视风险。

#### research_portfolio与research_position

当前`research_portfolios/research_portfolio_holdings`是账号级人民币债券研究配置：组合保存人民币研究规模、指标日期和可选目标久期，持仓保存债券代码、类别、权重以及用户录入收益率/久期；支持手工维护和固定CSV，不支持组合模式、多币种、数量/面值、真实市值、成本、方向、期货手数、组织共享或真实持仓导入。现有表和API保持兼容，以下是多资产目标逻辑契约，不表示已经确定物理拆表：

```text
research_portfolio
  id PK
  owner_scope_type             user / organization
  owner_scope_id
  portfolio_mode              target_allocation / simulated_position / real_position_reserved
  name
  base_currency
  hypothetical_capital nullable
  as_of
  input_source
  status
  version

research_position
  id PK
  portfolio_id
  asset_scope
  instrument_id
  position_direction          long / short / neutral_or_not_applicable
  original_currency
  target_weight nullable
  quantity nullable
  face_value nullable
  market_value nullable
  cost_basis nullable
  contract_count nullable
  notional_exposure nullable
  margin_amount nullable
  data_as_of
  input_source
  input_parameter_json
  data_quality
  version
```

`target_allocation`至少要求目标权重，可带假设资金；`simulated_position`按资产要求数量、面值、具体合约手数或其他持仓基准。目标权重、假设资金、数量、面值、市值、成本、名义敞口和保证金不得收敛到一个通用金额字段。国债期货必须使用具体合约、手数和多空方向，名义敞口不进入普通资产市值或配置权重汇总。`real_position_reserved`只用于接口和权限边界预留，MVP不得创建可用的真实账户模式。

#### research_risk_result

```text
id PK
portfolio_id
portfolio_version
position_id nullable
asset_scope
instrument_id nullable
risk_type
risk_factor
risk_direction
value nullable
unit
original_currency
base_currency nullable
market
data_as_of
parameter_source
parameter_version
calculation_method
calculation_version
result_state
data_quality
coverage_numerator nullable
coverage_denominator nullable
coverage_basis nullable
covered_instrument_count
missing_reason nullable
assumptions_json
limitations_json
created_at
```

公共`risk_type`至少支持`interest_rate/credit_spread/credit_concentration/futures_exposure/basis/margin/liquidity/fx/event`；资产专属风险因子使用命名空间扩展，不把所有风险压成单一总分。风险等级与数据质量分别保存，结果状态至少区分`normal/partial/degraded/not_calculable/not_enabled/failed`。

#### research_scenario_definition、research_scenario_run与research_scenario_result

```text
research_scenario_definition
  id PK
  scenario_type               predefined / user_defined / historical / ai_candidate
  name
  version
  shock_set_json
  parameter_source
  validation_state
  effective_from

research_scenario_run
  id PK
  portfolio_id
  portfolio_version
  valuation_as_of
  scenario_definition_id
  scenario_version
  risk_parameter_snapshot_id
  calculation_version
  status
  created_at

research_scenario_result
  run_id
  asset_scope
  position_id nullable
  risk_factor
  shock_value
  shock_unit
  calculation_method
  estimated_pnl nullable
  currency
  result_state
  coverage_numerator nullable
  coverage_denominator nullable
  coverage_basis nullable
  assumptions_json
  limitations_json
  missing_reason nullable
```

AI生成的定义只能保持`ai_candidate`，必须经用户确认或预设规则校验转为可执行版本；正式金融数值由确定性计算器产生，AI不得写入或修改`estimated_pnl`。

#### research_case、research_case_version与research_case_reference

轻量研究案例只编排不可变引用，不复制事件、预测、组合或回测等底层业务数据：

```text
research_case
  id PK
  owner_username
  project_id nullable
  access_mode                  personal / project
  title
  status                       active / archived
  latest_version
  permission_version
  created_by
  created_at
  updated_at

research_case_version
  case_id
  version
  summary nullable
  context_asset_scope nullable
  context_instrument_id nullable
  context_as_of nullable
  created_by
  created_at

research_case_reference
  id PK
  case_id
  case_version
  reference_type               event / evidence / forecast / portfolio / risk / scenario / strategy / backtest / report
  reference_id
  reference_version_or_snapshot_id
  relation_role                evidence / counter_evidence / input / output / decision / follow_up
  display_order
  access_state                 accessible / unauthorized / source_deleted / retention_expired / superseded
  replacement_reference_id nullable
  added_at
```

引用在加入案例时固定业务版本或快照；底层生成新版本不改写旧案例。个人案例只允许所有者访问；关联项目后复用现有项目`manager/editor`语义，但案例权限和引用对象权限逐条求交集。项目成员移除或权限变化在下一次请求即时生效，不依赖复制的ACL缓存。

案例所有权转移是目标能力，不是当前项目接口的既有能力。转移事务至少校验接收者为有效本地用户、关联项目关系、关键引用可访问性和未完成写任务，锁定案例当前`permission_version`，原子更新所有者并追加`case_ownership_event`。历史作者、原所有者、接收者、时间、原因和失败结果不改写；关联项目管理者不因角色本身自动取得个人案例所有权。

查询案例时重新校验案例和被引用对象权限；`unauthorized/source_deleted/retention_expired`只返回引用类型、状态和获准元数据，不泄露原内容。被替代版本保留原引用及显式替代关系，替换只进入新案例版本。

#### research_monitor_rule、research_monitor_evaluation与research_alert

现有关注项通过兼容适配保留普通收藏；目标监测契约如下：

```text
research_monitor_rule
  id PK
  owner_username
  watchlist_item_id nullable
  target_type                  asset / instrument / metric / event / factor
  target_id
  condition_type               threshold / change / trend / important_event
  condition_json
  source_frequency
  evaluation_frequency
  user_timezone
  cooldown_spec_json
  dedup_policy_version
  enabled
  version
  effective_from

research_monitor_evaluation
  id PK
  rule_id
  rule_version
  source_batch_or_snapshot_id
  observed_at
  evaluated_at
  result_state                 not_triggered / triggered / insufficient_data / failed
  observed_value_json
  reason_json

research_alert
  id PK
  rule_id
  rule_version
  evaluation_id
  dedup_key
  alert_type                   research_prompt / todo / case_candidate
  status                       new / read / dismissed / resolved
  created_at
```

`evaluation_frequency`不得高于可靠`source_frequency`；日频或按发布时点评估的规则不能标为实时。去重键至少纳入规则版本、目标、来源批次/事件族和触发区间；冷却期内的持续越界、数据修订和恢复事件按版本化策略决定更新原提醒还是产生新提醒。提醒服务不得直接调用预测、策略、回测或交易接口。

#### research_report、research_report_version与research_report_export

```text
research_report
  id PK
  owner_username
  project_id nullable
  case_id
  status                       active / archived / soft_deleted
  latest_version

research_report_version
  report_id
  version
  case_version
  data_snapshot_set_json
  evidence_reference_set_json
  model_prompt_versions_json
  calculation_parameter_set_json
  content_uri
  evidence_support_state       supported / partially_supported / unsupported
  parent_version nullable
  created_by
  created_at

research_report_export
  id PK
  report_id
  report_version
  format                       pdf / docx / xlsx / csv / markdown
  permission_snapshot_id
  license_decision_json
  filtered_reference_set_json
  redaction_manifest_json
  support_state_after_filter
  artifact_uri nullable
  status                       requested / generated / rejected / expired / deleted
  created_by
  created_at
```

正式报告版本冻结案例、数据、证据、模型/提示词和计算参数；重新生成创建新版本并保存差异，不覆盖正文。动态研究视图按当前权限读取最新数据，只返回临时视图模型，不写回正式报告。导出权限拆分为`view/research_use/export/redistribute`，并与每条来源许可取交集；过滤、脱敏或替代后若核心结论变为`unsupported`，导出任务必须拒绝或要求从剩余证据生成新报告版本。

#### retention_deletion_record

删除编排覆盖原始数据、标准化版本、研究快照、报告正文、导出物、缓存和搜索索引。记录对象类型/ID/版本、删除类型、授权或制度依据、执行范围、保留墓碑字段、缓存失效结果、执行者和时间。软删除不改变历史引用；永久删除或许可到期只在合法范围保留最小墓碑及复现影响。具体期限和永久删除权限通过按数据类型配置的策略决定，不在逻辑设计中写死。

### 8.3 四级数据质量与功能门控

门控按资产、标的、指标、功能和时间范围独立计算，局部异常不得无条件关闭整个资产页面。

| 等级 | 最低要求 | 不满足时的行为 |
|---|---|---|
| 展示级 | 来源、日期、展示授权和基本可读性明确 | 标注缺失、过期、冲突或异常；无展示授权则阻断 |
| 分析级 | 证据与目标语义足以支持结论 | 定量不足时仅保留有依据的定性分析；证据不足显式标识 |
| 验证级 | 历史行情、有效样本、可用时间、历史属性和对齐质量满足该验证定义 | 阻断受影响的正式统计验证，可降为案例或探索性结果 |
| 交易级 | 可交易标的、行情、规则、成本、成交模拟及DreamStrategy支持均已确认 | 阻断策略生成或回测，不以代理指标冒充PnL |

质量原因至少区分缺失、过期、重复、异常值、来源冲突、证据不足、权限不足和外部服务故障；功能状态至少区分正常、部分可用、降级、阻断和执行失败。数据质量状态与模型分析置信度独立保存和展示。历史有效数据可以使用，但必须显示所属时间，不得冒充最新数据；任何门控均不得以AI生成值填补关键金融数据。

### 8.4 原始批次、修订与研究快照

在来源授权允许的范围内保留原始文件或响应、来源批次、内容哈希、标准化版本和修订关系。内容哈希用于校验和去重，不能替代原始数据或单独证明可复现。修订值不得覆盖历史决策时点实际使用的旧版本。

研究任务通过版本与引用复现，不要求复制完整数据库：

- 联网证据保存来源链接、发布时间、获取时间及获准保存的必要内容；限制缓存的来源只保留获准元数据，并显示复现限制；
- 用户上传保存文件版本、上传时间、所有者或组织、解析结果和授权范围；
- 预测、事件研究和策略回测保存数据版本/快照引用、模型、提示词、代码及计算配置；
- 明确区分当前最新数据与历史决策时点可用数据；保留周期按来源授权、用户数据管理、存储成本和业务需求配置。

MVP先实现必要的批次/版本引用、`available_at`和研究输入记录，不提前建设完整数据仓库。现有信用曲线和美债收益率按业务键覆盖、期货持仓按业务键幂等更新的实现保留为现状；新增资产研究若需要修订追踪，必须旁路记录版本，不改写中国国债旧链路。

### 8.5 兼容策略

第一阶段不直接迁移现有 \`analysis\`、\`news_factor\`、\`yield_data\` 和 \`factor_event_study\`，也不向旧表增加会改变现有中国国债语义的强制字段。

实现：

- \`CnGovBondLegacyAdapter\`：把旧表转换为通用读取模型；
- 适配器在已知目标指标后映射旧 `positive/negative`，不回写旧表，也不改变现有中国国债分析结果；
- 新增资产优先写入资产化结果表；已有局部行情表通过适配器只读，不要求立即复制；
- 现有板块内的新增资产子模块调用通用查询契约，现有页面继续调用旧 API；
- 旧页面和 API 保持不变；
- 通用引擎稳定后再评估中国国债数据迁移。

该方案降低一次性修改大量 SQL 和历史接口的风险。

### 8.6 组合、多币种与风险兼容策略

- 现有账号级组合继续按人民币研究规模、权重和用户录入指标运行；新增字段通过旁路逻辑模型、适配器和能力开关渐进接入，不在本阶段修改现有表或业务代码。
- 研究组合分为目标配置和模拟持仓；真实持仓接入、Excel和内部持仓接口分别受格式、权限、组织隔离、授权、估值和审计门控。
- 多币种结果始终保留原始币种、原始金额和市场风险因子。换算结果另存基准币种、汇率来源、换算时点和版本；不同市场利率风险即使折为同一币种也不合并为同一风险因子。
- 美债MVP正式口径为美元本币。人民币即期价值/风险金额折算、未对冲投资回报和对冲后回报是三个独立能力；即期折算不得标记为后两者。
- 组合、风险和情景快照引用组合版本与估值时点；更新持仓或风险参数创建新结果，不覆盖旧结果。

## 9. 服务分层

建议目录：

```text
backend/research/
  profiles/
    cn_gov_bond.py
    credit_bond.py
    cn_treasury_futures.py
    us_treasury.py
  ingestion/
  market/
  events/
  factors/
  evaluation/
  forecast/
  portfolio/
  risk/
  scenario/
  backtest/
  strategy/
  reports/
  api/
```

核心接口：

```python
class MarketDataAdapter(Protocol):
    def sync(self, request: SyncRequest) -> SyncResult: ...
    def query(self, query: MarketQuery) -> MarketSnapshot: ...

class EventAnalyzer(Protocol):
    async def normalize(self, evidence: EvidenceInput) -> CandidateEvent: ...
    async def assess_impact(self, event: PublicEvent, profile: AssetResearchProfile) -> ImpactAssessment: ...

class MarketPerformanceCalculator(Protocol):
    def calculate(self, target: PerformanceTarget, market: MarketWindow) -> MarketPerformance: ...

class ForecastCapabilityRegistry(Protocol):
    def resolve(self, target: ForecastTarget) -> ForecastCapability: ...

class ForecastEngine(Protocol):
    async def generate(self, request: ForecastRequest) -> ForecastResult: ...

class ForecastEvaluator(Protocol):
    def evaluate(self, forecast: ForecastResult, actual: MarketObservation) -> ForecastEvaluation: ...

class PositionAdapter(Protocol):
    def normalize(self, position: PositionInput, profile: AssetResearchProfile) -> ResearchPosition: ...

class RiskCalculator(Protocol):
    def calculate(self, request: RiskCalculationRequest) -> list[RiskResult]: ...

class ScenarioCalculator(Protocol):
    def calculate(self, request: ScenarioRunRequest) -> list[ScenarioResult]: ...

class StrategyCapabilityRegistry(Protocol):
    def resolve(self, instrument_id: str) -> StrategyInstrumentCapability: ...

class BacktestAdapter(Protocol):
    def validate(self, request: BacktestRequest) -> None: ...
    def run(self, request: BacktestRequest) -> BacktestResult: ...

class StrategyAdapter(Protocol):
    def build_context(self, request: StrategyContextRequest) -> StrategyContext: ...
    def validate_requirement_match(self, version: StrategyBusinessVersion, code: GeneratedCode) -> ValidationResult: ...
    async def generate(self, request: StrategyRequest) -> StrategyResult: ...

class ResearchCaseService(Protocol):
    def add_reference(self, case_id: str, reference: VersionedReference) -> ResearchCaseVersion: ...
    def resolve(self, case_id: str, version: int, principal: Principal) -> ResearchCaseView: ...

class ResearchMonitorService(Protocol):
    def evaluate(self, rule: MonitorRule, source_snapshot: SourceSnapshot) -> MonitorEvaluation: ...
    def emit_research_alert(self, evaluation: MonitorEvaluation) -> ResearchAlert | None: ...

class ResearchReportService(Protocol):
    def generate_version(self, request: ReportVersionRequest) -> ResearchReportVersion: ...
    def build_dynamic_view(self, report_id: str, principal: Principal) -> DynamicReportView: ...
    def export(self, request: ReportExportRequest, principal: Principal) -> ReportExportResult: ...
```

## 10. API 设计

以下表示目标产品契约，不锁定最终资源拆分，也不意味着接口当前已经实现。接口和页面结构可先完整设计，物理实现按MVP优先级推进；任何尚无真实数据或计算能力的接口都不得返回占位数值或模拟金融结果。具体事件、证据和影响接口后续结合现有路由落地：

```text
/sapi/research/assets
/sapi/research/{asset_scope}/instruments
/sapi/research/{asset_scope}/overview
/sapi/research/{asset_scope}/market
/sapi/research/{asset_scope}/events
/sapi/research/evidence/{evidence_type}/{evidence_id}
/sapi/research/{asset_scope}/factors
/sapi/research/{asset_scope}/returns
/sapi/research/{asset_scope}/forecasts
/sapi/research/portfolios/{portfolio_id}/risks
/sapi/research/portfolios/{portfolio_id}/scenarios
/sapi/research/strategy-capabilities
/sapi/research/{asset_scope}/backtests
/sapi/research/{asset_scope}/strategy-context
/sapi/research/{asset_scope}/strategy-versions
/sapi/research/{asset_scope}/strategy-attempts
/sapi/research/{asset_scope}/reports
/sapi/research/research-cases
/sapi/research/research-cases/{case_id}/versions/{version}
/sapi/research/monitor-rules
/sapi/research/alerts
/sapi/research/reports/{report_id}/versions/{version}
/sapi/research/reports/{report_id}/dynamic-view
/sapi/research/reports/{report_id}/exports
```

概览响应示例：

```json
{
  "data": {
    "asset_scope": "credit_bond",
    "instrument_id": "CREDIT_CURVE_ALL_3Y",
    "as_of": "2026-11-24T15:30:00+08:00",
    "market": {},
    "news_sentiment": {},
    "factors": [],
    "forecast": null,
    "backtest_summary": null,
    "data_quality": {
      "status": "fresh",
      "latest_observation": "2026-11-24",
      "warnings": []
    }
  }
}
```

新增的重计算写操作使用任务模式：

```text
POST /sync
POST /analyze
POST /evaluate
POST /forecast
POST /portfolios/{portfolio_id}/risk-calculations
POST /portfolios/{portfolio_id}/scenario-runs
POST /backtests
POST /strategy-context
POST /strategy-versions/{version_id}/confirm
POST /strategy-versions/{version_id}/attempts
POST /research-cases
POST /research-cases/{case_id}/references
POST /research-cases/{case_id}/archive
POST /research-cases/{case_id}/transfer
POST /monitor-rules
POST /monitor-rules/{rule_id}/versions
POST /monitor-rules/{rule_id}/enable
POST /monitor-rules/{rule_id}/disable
POST /research-reports
POST /research-reports/{report_id}/versions
POST /research-reports/{report_id}/exports
POST /research-reports/{report_id}/restore
DELETE /research-reports/{report_id}
```

返回任务 ID，由扩展后的任务查询接口读取状态。现有统一 AI 任务调度器当前只执行研报、政策、综合研报和每日新闻总结；市场同步、事件分析、预测和回测接入前必须新增任务类型、领域状态、幂等、租约和重试契约，不能只写入 `task_runs/task_events` 就视为完成接入。

## 11. 事件分析、因子治理与传导

### 11.1 事件分析与提示词

事件处理按职责分为事实识别、来源核查与去重、证据关联、资产影响判断。具体表、任务拆分和执行顺序尚未锁定，但必须满足以下契约：

- 新闻和正式政策文件可生成候选事件；研报默认生成观点、预测或研究证据；
- 研报中的可核查事实只有在验证和去重后才可提升为公共事件；
- 公共事件只保存一次，同一事件可关联多个来源；
- 不强制每个事件分析四类资产；已纳入范围的资产必须显式记录分析状态；
- 市场预期、预测和已确认未来安排可参与研究，但不得混入已发生事实的统计样本。

共用系统提示词或规则负责：

- 输出 JSON 契约；
- 禁止编造数值；
- 要求引用原文依据；
- 区分事实、观点、预测、预期和未来安排；
- 区分公共事件与资产影响；
- 输出置信度和失效条件。

资产提示词负责：

- 方向语义；
- 目标指标；
- 传导机制；
- 允许的影响期限；
- 资产专属因子；
- 不适用条件。

新链路重算身份至少包含：

```text
event_id + asset_scope + instrument_id + target_metric + horizon + model + prompt_version
```

旧中国国债链路继续以现有`news_id`流程运行，由兼容适配器提供通用读取结果。

### 11.2 因子分类与标准化映射

公共核心因子描述政策、宏观、流动性、风险、情绪和行业等通用经济驱动；资产命名空间只承载该市场独有的评级、主体、持仓、基差、交割、美国宏观意外和拍卖等概念。一个公共因子可以关联多个资产，但每个资产的目标指标、方向、周期、证据和应用状态独立保存。

标准化顺序：

1. 保留AI原始标签、原始分类和证据引用；
2. 按稳定ID、标准名称和版本化别名匹配已有正式因子；
3. 对候选匹配执行金融语义、事实/预期、粒度和适用资产校验；
4. 保存标准化因子、映射依据、模型和提示词版本；
5. 无法可靠匹配时创建候选，不以字符串相似度直接发布或丢弃。

因子定义不保存固定`bullish/bearish`。市场效果只出现在具体事件影响或因子应用中，由资产、标的、目标指标和周期共同确定。

### 11.3 自动审核与生命周期

新链路采用独立提取、独立AI审核和程序校验：提取任务只产出匹配或候选；审核任务使用独立上下文和提示词检查金融合理性、证据充分性、语义重复、分类、粒度、可复用性和可验证性；程序再检查必填字段、重复、证据引用和数据契约。审核通过且规则成功后可自动发布，审核冲突、证据不足或无法判断时保留候选。MVP允许同一模型进行两次独立调用，接口预留多模型交叉审核；AI审核通过不代表统计有效或可交易。

字典级状态及主要规则：

| 状态 | 含义与使用规则 |
|---|---|
| candidate / reviewing | 候选或审核中；可用于单次解释，不进入正式统计、预测或策略 |
| active | 正式使用；具体定量用途仍受应用级状态控制 |
| dormant | 长期未出现但金融意义仍存在；可恢复，不因低活跃度退休 |
| watch | 历史表现下降或机制不稳定；限制受影响的预测/策略用途 |
| paused | 数据异常或依赖缺失；恢复条件满足后可重新开放 |
| merged | 与另一因子经济语义及统计口径一致；保留原ID、标签、版本和映射 |
| rejected | 审核未通过；保留证据与原因 |
| retired | 定义错误、制度永久终止或机制明确被替代，并经证据核查与独立复审；不再产生新正式信号但保留全部历史 |

低活跃度、低命中率、样本不足或单次AI判断均不得触发退休。退休因子恢复时重新审核，产生新版本和生效时间，不覆盖历史状态。

应用级状态按`factor_id + asset_scope + instrument_id + target_metric + horizon`管理研究、正式验证、预测和策略资格。单一资产或周期失效只调整该应用，不导致公共因子全局退休。

持续监测由定期批处理结合异常触发完成：程序监测去重活跃度、有效样本、相对基准表现、滚动稳定性、语义重复和数据可用性，异常时触发独立AI复审；不要求每日对全部因子调用模型。周期、阈值和复审次数在真实数据与模型评估后配置。

所有提取、审核和状态变更记录原始输入、证据、模型、提示词、规则版本、原因、生效时间和影响范围。旧中国国债自动发现、因子ID和使用逻辑保持不变，只由LegacyAdapter读取。

### 11.4 三维评价契约

| 维度 | 评价对象 | 最小输出 | 禁止解释 |
|---|---|---|---|
| 事件重要性 | 单个事件的潜在市场影响和研究价值 | 分值或等级、依据、版本 | 不等于预测概率或因果贡献 |
| 因子活跃度 | 因子在明确窗口内的独立事件频率及变化 | 去重事件数、窗口、标准化口径、趋势 | 不等于历史有效性 |
| 历史有效性 | 因子在特定资产、标的、指标和周期的统计表现 | 有效样本、命中率、基准、效应、不确定性、市场阶段和资格状态 | 不等于交易收益或全局因子价值 |

活跃度基于公共事件去重，重复报道不能重复计数；跨窗口或跨资产比较时须说明频率标准化口径。历史有效性数据不足时返回证据不足，不以重要性或活跃度补值。MVP分别提供筛选与排序，不计算新的综合分；现有中国国债新闻重要性分及其九类输入保持原算法与用途。

### 11.5 相反信号与研究摘要

直接冲突只在标的、目标指标、方向语义和影响周期可比时判断。不同期限、指标或周期的差异保留为并列结果，不标为直接冲突；状态明确区分`neutral`、`mixed`、`conflict`和`unknown`。

证据充分时可生成不依赖数值权重的定性摘要，说明主导因素、反向因素、适用条件和失效风险。定量综合方向必须声明计算规则、权重来源、版本和验证结果；条件不满足时保留冲突或无法判断。冲突、不确定性和反向证据原样进入预测输入、研究组合、报告与策略情报包，后续模块不得默认清除。只有持仓方向、风险暴露和必要行情均明确时才可生成`position_view`。

### 11.6 事件级跨资产传导

传导分析先应用规则模板产生候选机制，再对具体事件逐条判断适用性、方向、周期、证据和条件；模板不得无条件复制方向。关系类型区分直接影响、间接影响和共同因素驱动，相关性不得直接标为因果。

MVP优先覆盖：中国国债现券与国债期货的期现传导；无风险利率、信用风险和流动性对信用债的分解；美债、中美利差与国内债市的跨市场利率传导。自然语言说明与结构化关系同时输出，结构化关系使用现有关系型数据库可实现的轻量模型，不引入图数据库或自动因果推断。

## 12. 市场表现、历史相关性与事件研究

### 12.1 市场表现计算

`MarketPerformanceCalculator`按资产profile生成第8节统一结果：

- 中国国债保留旧收益率变化逻辑；价格回报和总回报按数据条件开放；
- 信用债MVP计算整体曲线收益率bp变化；信用利差必须匹配基准曲线、期限、估值时点和口径，利率对冲后超额收益还需可靠价格与风险暴露；
- 国债期货当前只有会员持仓变化；合约价格、结算价收益、基差和策略PnL在对应行情与交易能力具备后分别计算；
- 美债MVP计算2Y/10Y/30Y收益率bp变化；价格和总回报按期限数据、价格、票息和回报口径开放。

指标缺失时按四级门控降级，不插值或生成代理收益。统一结构只提供一致语义，不授权对异质指标原始值进行排名或相加。

### 12.2 三类研究结果

| 结果类型 | 最小契约 | 能力边界 |
|---|---|---|
| historical_correlation | 指标对、观察区间、对齐规则、频率、方法、样本、系数/统计量、版本和局限 | 描述历史联动，不证明直接因果 |
| event_study | 事件集合、事件族、目标指标、T与窗口、基准、样本资格、效应、命中率、不确定性和市场阶段 | 研究事件后市场反应，不等于可成交收益或盈利概率 |
| strategy_backtest | 可交易标的、决策/执行时点、信号、仓位、行情、成交、成本、风险、基准和代码/数据版本 | 仅交易级门控及DreamStrategy支持通过后开放 |

三个结果使用独立类型、状态和验收。相关性或事件研究可以成为策略研究输入，但不得改名为策略回测；三者的统计支持均不自动证明因果。

### 12.3 事件样本与窗口

1. 按`available_at`及时间精度映射T，保存原始时间、资产日历、规则版本和对齐结果。
2. 将完全重复报道关联到同一公共事件；识别事件后续更新、主事件、含独立新增信息的子事件和事件族。
3. 为每个事件×目标指标×窗口记录重叠状态、相关干扰事件、样本资格及排除原因。
4. 观察窗口重叠时不默认独立；按预先定义的方法选择剔除、缩短窗口、分组或稳健性分析，不根据事后涨跌筛选。
5. 检查独立有效事件、时间跨度、行情覆盖、缺失、对齐质量、样本相关性和市场阶段。
6. 由资产计算器生成市场表现，汇总效应、分位、命中率、基准和统计不确定性，并保存数据、事件、模型、提示词、代码和配置版本。

能力状态仍区分`case_study`、`exploratory`、`formal_validation`和`strategy_candidate`。现有`min_samples=20`仅是中国国债当前实现参数，不成为新增资产统一门槛。用户上传数据只有通过授权、质量、时间和样本门控后才能用于其权限范围内的验证。

禁止使用分析时间替代信息可用时间、使用期末才知道的主力合约、用当前评级回填历史评级、重复计算同一市场变化作为多个因子的独立贡献，或忽略连续合约规则、停牌、无成交和缺失数据。

## 13. 回测框架

本节只定义可交易策略回测。收益率/利差bp、持仓变化、历史相关性和事件命中率属于研究结果，不得写入策略PnL字段。具体请求只有在标的能力、交易级数据、确认版本、金融模型和执行安全门控通过后运行；未通过时可以保留诊断或实验记录，但不能标为正式研究回测。

### 13.1 标的能力与门控

`StrategyCapabilityRegistry`先区分资产类别、研究指标、可交易标的、主力序列和连续序列，再按具体标的解析能力状态。升级状态必须附独立证据、验证时间和限制；别名继承接口兼容性，不继承独立验证结论。用户指定不符合策略执行门控的标的时返回业务拒绝，禁止静默替换为白名单内其他标的。

受控预期成交测试用于验证代码到订单、成交和结果解析的基础链路，应使用可预期产生交易的固定策略与固定窗口；普通策略零成交则按无信号、数据缺失、订单拒绝、资金不足、代码错误、标的不支持分别归因。零成交不必然令运行状态失败，但无法提供盈利表现证据，也不能单独升级标的能力。

### 13.2 结构化情报包与历史特征

`StrategyContextBuilder`按以下层次按需构建情报包：标的/能力；市场、历史与数据引用；需求、成本、成交和执行约束；可选事件、因子与历史证据；可选预测；可选组合风险；以及全包的质量、来源、时点、版本和缺失信息。筛选使用需求相关性、证据质量、令牌预算、去重和冲突保留规则，不采用未经验证的简单平均。

预测默认是可选研究证据。未经历史统计验证的AI预测不得直接触发交易；后续经验证的历史预测信号只有在确认版本中明确选择后才可成为定量输入。组合风险仅形成风险预算、仓位上限及不新增/加仓/减仓/平仓/套保约束，不在未经确认时决定方向。新闻、预测或风险变化不得自动创建并执行新策略版本。

历史运行读取`historical_feature_snapshot_id`，逐时点执行`available_at <= decision_time`检查。真实历史预测与当前模型事后回放分开保存；事后回放只能用于实验，不能伪装为当时可用信号。当前模型即使设置历史数据截止时间，也可能包含训练期或世界知识的前视信息，必须记录限制。

### 13.3 业务版本、确认与执行尝试

通用确认版本冻结标的、能力、资本、期间、规则、方向/仓位、成本、成交假设和主要风险。标的、模式、逻辑、期间、参数、仓位、成本、资本或关键数据任何一项实质改变均生成新业务版本并再次确认；展示名称变化不触发确认。提示词被确认只说明业务意图获确认，不证明生成代码满足意图，因此取得代码后还要做结构化需求一致性校验。

同一`requirement_hash + context_version + confirmation`形成业务版本；每次外部调用形成执行尝试。请求幂等键用于本系统去重，网络重试和不改变语义的技术修复可在同一版本下增加尝试；若外部服务没有幂等承诺，只能记录“已请求/状态未知/已返回”等事实，不承诺恰好执行一次。基于收益好坏自动重试或修改参数属于选择偏差，不是技术重试。

### 13.4 外部执行与不可信代码

当前集成式生成链路是在外部服务完成代码生成与回测后才返回代码，本系统的本地校验发生在外部执行之后；独立模板回测接口能够提交代码或版本，但不能据此宣称集成式生成已经具备预执行代码审核。目标设计若要标记`formal_research_backtest`，必须取得并验证外部服务的代码生成/执行边界、沙箱、文件与环境变量隔离、密钥和多租户隔离、网络权限、资源限制、超时、取消、请求去重及审计契约。无法验证时结果保持`experimental`。

返回代码仍执行本地静态和结果一致性校验：实际下单调用、允许标的、预期标的、订单方向/类型、禁止未授权I/O与网络、未来函数、成交与指标一致性、异常收益及幽灵订单。校验失败不得通过修改状态或仅依赖自然语言提示词放行。

### 13.5 版本化金融模型

正式研究回测引用四类不可变模型版本：

| 模型 | 最低语义 |
|---|---|
| 成本 | 佣金、买卖价差、滑点、市场摩擦及适用的融资成本；零值必须有证据或明确为理论假设 |
| 成交 | 订单类型、决策与最早执行时点、成交价格/时间、流动性约束和不成交；禁止无条件按估值价、收盘价或信号价成交 |
| 结算 | 资金、持仓、可用余额、保证金、盯市、资金不足、到期和交割/换月状态 |
| 核算 | 价格损益、票息、应计、到期、违约、外汇及不同现金流时点的归属规则 |

信用债必须分开估值与可成交价格，并处理买卖价差、流动性/不成交、票息、应计及违约；国债期货处理合约乘数、最小变动、费用、滑点、结算价、保证金、逐日盯市、资金不足、到期和换月，且换月价差、交易摩擦、基差变化和连续序列调整分开核算；美债必须具备具体标的、价格、票息、应计、成交和成本，人民币视角另遵循多币种能力阶梯。

假设成本或情景成交可以用于研究，但必须保存来源、适用范围和版本。外部服务不能应用或无法复核这些模型时，运行只能是诊断、理论或实验结果，不能因提示词中写入假设而升级为正式结果。

### 13.6 运行状态与评价

生命周期、研究质量和表现评价使用三个独立字段。技术完成不自动获得研究质量，正式研究可用不自动获得良好表现，亏损也不自动否定方法。表现指标按资产和策略类型配置：债券需区分价格、票息、应计和现金流；期货需考虑保证金、盯市及名义风险；套保重点报告套保前后DV01/波动、剩余风险、资金占用与成本。保证金或占用资金收益不得直接和全组合收益比较，所有收益率必须声明分母。

研究评价按时间顺序划分训练、验证和样本外窗口，并保留代码生成、参数搜索、运行失败、候选结果与最终选择历史。反复观察同一测试窗口后继续调参的结果不能再称为独立样本外验证。具体阈值在各资产数据盘点和模型验证后配置，不建立全资产统一收益或胜率门槛。

### 13.7 国债期货套保研究

套保能力分三级：定性方案；静态套保比率与合约数；完整历史套保回测。前两级由组合/风险服务提供，不强依赖DreamStrategy。静态计算在组合目标风险、组合DV01和期货每合约DV01可靠或明确标注为假设时，由确定性程序输出理论合约数、满足方向约束的整数候选、目标套保率和剩余DV01；整数选择可结合风险目标、仓位/资本/保证金约束，不执行无条件四舍五入。供应商每合约风险参数或CTD/转换因子路线均可作为经验证输入，CTD不是唯一允许路径。

套保结果保存方向、币种、市场、风险因子、参数时点及曲线、基差、CTD切换、换月、保证金和过度套保风险。跨市场风险不能仅凭汇率金额相等即视为可对冲；信用债国债期货套保只覆盖匹配的基准利率风险，不覆盖信用利差、违约和流动性风险。完整历史套保回测还要求现货/组合与期货同步历史、可靠组合风险、真实合约映射、逐日结算、成本和多资产多腿能力；缺任一条件时停留在前两级。

## 14. 预测框架

### 14.1 现状与兼容边界

现有`backend/analysis/generate_report.py`独立生成中国国债10Y日/周/月报告，输入为库内新闻分析、收益率序列和市场摘要；提示词当前要求每个周期输出上涨/下跌概率、条件BP及0—1置信度。`backend/evaluation/forecast_evaluation.py`按10Y收益率序列的T+1/T+5/T+20评估方向命中率、多数类基准、绝对BP误差、置信度分档和月度方向偏差。该链路不具备新增资产白名单、正式拒绝状态、Brier/区间评估、多模型共识或联网搜索证据链，继续按中国国债旧逻辑运行，并由只读适配器说明其概率和置信度尚未完成统计校准。

### 14.2 目标、周期与能力注册

新增资产预测先解析能力注册，再准备输入：

1. 白名单键为资产、标的、目标指标、预测周期和预测类型；定性研究、方向、概率、幅度、区间分别开放。
2. 新增资产的“日/周/月”默认对应目标市场未来1/5/20个有效观察日，保存实际起止时点、日历和观察日数；资产规格可增加有明确语义的其他周期。
3. 预测周期、生成频率和更新频率分离。定时、重大事件或上游数据变化可以创建新版本，`data_cutoff_at`和旧预测保持不变；更新、失效、正常到期使用不同状态。
4. DreamStrategy不是普通市场预测的前置条件；可交易策略仍独立执行交易级门控。

### 14.3 证据准备与按需联网

输入优先级为已授权专业供应商、库内新闻/行情/政策/研究证据，再按数据新鲜度、重大事件、来源缺口、事实冲突或用户要求决定是否搜索。搜索编排必须：

- 记录触发原因、查询目的、链接、来源发布时间、获取时间、内容/元数据版本、核查状态和授权边界；
- 优先官方来源、原始公告和可靠金融来源，关键宏观值、评级、交易价格与政策事实未经核查不得进入正式预测；
- 防止搜索结果中的外部指令改变任务、安全规则或工具权限，禁止未经授权发送私有/内部数据；
- 支持缓存、证据去重、预算、超时和失败降级；历史复现只选择`available_at <= data_cutoff_at`的证据；
- 搜索失败时由能力门控决定继续、降级或拒绝，不改写为中性或系统成功。

具体搜索供应商、接口、阈值和预算尚未确定；当前没有通用互联网搜索工具进入预测主链路。

### 14.4 生成、降级与拒绝

生成前按白名单、数据质量、证据质量、信号冲突和历史评估状态确定最高可用预测类型：条件充分时正式输出；概率或幅度条件不足时降为方向或定性研究；关键数据缺失、目标未开放、证据不足或冲突不可解释时返回业务拒绝。正常/降级结果保留目标、窗口、依据、假设、反向风险和失效条件；降级/拒绝另存原因、证据范围与恢复条件。AI不得用自报置信度绕过门控，也不得被强制填充概率、BP或区间。

模型判断置信度采用可空的高/中/低等级；证据质量由来源、完整性、及时性、一致性与质量门控计算；历史概率校准和统计不确定性由评估任务提供。四者独立存储和展示。预测区间与评估指标的置信区间使用不同字段。

### 14.5 多模型与共识

默认模型完成日常预测；重大事件、证据冲突、新目标、模型表现下降或用户要求可触发其他模型复核。每个模型独立保存并按相同目标、周期、输入和评估口径比较。只有聚合规则、权重依据、历史校准、版本和验证结果均已登记时才生成共识；禁止无条件平均概率或简单多数投票。否则保存模型冲突或拒绝共识，并将冲突传递到报告、组合与策略情报包。

### 14.6 历史评估

评估按资产、标的、目标指标、预测周期、模型版本和市场阶段分层，并使用预测类型匹配的指标：

| 类型 | 指标 | 必要对照 |
|---|---|---|
| 方向 | 方向准确率 | 与目标匹配的简单基准、上涨/下跌/基本不变判定规则 |
| 概率 | Brier Score、校准曲线 | 概率分组和未校准状态 |
| 幅度 | MAE、RMSE | 单位、实际值版本和简单基准 |
| 区间 | 覆盖率、区间宽度 | 目标覆盖水平 |
| 拒绝/降级 | 覆盖率、拒绝率、原因分布 | 防止只挑简单样本提高命中率 |

评估使用到期后的实际结果但不回写历史预测，检查样本外、未来函数、数据修订和市场阶段。真实历史时点生成与当前模型的事后历史模拟分别标识；后者可能含事后知识，不作为严格无未来信息的正式表现。具体校准、聚合、窗口、样本门槛和模型切换规则待数据盘点后确定。

## 15. 组合风险与情景框架

### 15.1 组合模式与输入门控

`target_allocation`面向目标权重和假设资金；`simulated_position`面向具体标的及假设持仓。模式与资产共同决定必填字段：普通债券至少需要标的、方向、币种及权重/面值/数量中的适用字段；国债期货必须是具体合约、手数和多空方向。输入来源区分手工、现有CSV、后续Excel、内部接口和其他授权来源，每次保存数据时点与版本。

现有CSV继续兼容其债券代码、名称、类别、权重、收益率、久期和备注字段，不把它解释为多资产完整持仓格式。新增格式必须版本化并提供字段映射、整批校验、错误定位、所有者/组织隔离和回滚；Excel与内部接口未通过这些条件前保持`not_enabled`。

### 15.2 利率风险与DV01

统一结果契约不统一金融算法。各资产计算器输出市值、久期类型、修正久期、DV01、风险因子、方向、参数来源、计算方法和状态：

- 普通固定利率债券的近似DV01要求可靠市值与修正久期；假设市值或风险参数可用于模拟研究，但必须标记`parameter_source=assumption`，不得冒充市场实值；
- 现有`duration_years`仅是类型未知的用户录入久期，在久期类型、口径和来源确认前不得映射为正式修正久期或参与正式DV01；
- 国债期货DV01由具体合约计算器处理，所需合约面值、CTD、转换因子或其他可靠风险参数按算法声明；缺少必要参数时返回`not_calculable`；
- DV01符号约定为“收益率上升1bp导致的估计价值变化”，因此普通多头固定利率债券通常为负；同时提供带符号净DV01和`sum(abs(dv01))`总绝对DV01，前端不得把两者混用；
- 按币种、市场和风险因子分别聚合。跨币种换算只改变金额计量币种，不合并中国利率、美国利率、信用利差等独立风险因子。

### 15.3 覆盖率与降级

每个覆盖率记录`numerator/denominator/basis`：债券优先采用有效风险市值/应计算风险市值；期货采用已具备风险参数的同类合约持仓或名义敞口/对应总量。配置权重、风险市值、合约手数和名义敞口是不同分母，禁止直接加总为全站覆盖率。

无法建立可靠全组合分母时，返回分资产覆盖率、有效标的数和缺失原因。缺失值保持空值；数据缺失既不生成零风险，也不自动生成高风险。部分结果使用`partial`并限制汇总范围，只有覆盖范围明确时才能展示已覆盖资产的估计损益。

### 15.4 资产专属风险

- 信用债分离基准利率风险与信用利差风险，防止同一收益率变化重复计入；评级、主体、行业、期限和违约事件集中度按可用主数据计算，CS01在市值、利差曲线/敏感度和口径满足后开放。
- 国债期货按具体合约计算方向、手数、名义敞口、保证金、杠杆、DV01、基差、到期和换月风险。保证金参数记录来源和版本；假设保证金可用于模拟，不等于交易所/账户真实保证金，更不等于最大可能亏损。
- 美债先提供美元本币利率与期限风险。当前2Y/10Y/30Y收益率曲线不能单独生成单券市值、DV01、价格/总回报或持仓损益。
- 流动性数值必须引用成交量、成交额、买卖价差、成交频率或明示代理。中金所会员排名仅为研究证据，不得进入用户持仓、保证金或流动性分母。

### 15.5 美债多币种能力阶梯

能力依次独立登记：`usd_local_risk`、`cny_spot_translation`、`cny_unhedged_return`、`cny_hedged_return`。美元本币研究是MVP基线；取得有授权且时点匹配的USD/CNY后，可优先开放人民币即期价值与风险金额折算。未对冲回报还需资产历史回报、汇率和现金流时点；对冲后回报还需远期汇率、对冲比例、期限、展期和交易成本。每层结果保存原始币种、基准币种、汇率来源、换算时点与版本。

### 15.6 规则与历史情景

MVP情景执行顺序为：解析已确认且版本化的冲击集合，检查风险因子与单位，解析组合/参数快照，调用资产计算器，按资产输出结果与覆盖率，再生成组合级可汇总部分。情景至少区分基准利率、信用利差、期货价格、期货基差和汇率：

- 信用债情景不得同时使用未分解的总收益率冲击及其基准利率/信用利差组成项；
- 期货不得在未定义映射时同时叠加直接价格冲击和利率隐含价格冲击；
- DV01、CS01等一阶结果标记`sensitivity_approximation`，不称为精确重估、完整实际PnL、预测或最大可能亏损；
- 缺少风险参数时保留已覆盖资产的部分结果、覆盖率和缺失原因，不生成全组合最终损益；
- 历史情景只有在可靠历史数据、跨市场时间对齐和风险因子口径一致时开放；
- AI可生成候选情景说明和参数，用户确认或规则校验后固化为新版本；计算服务拒绝直接接受未确认的`ai_candidate`，正式数值只能由确定性程序写入。

具体冲击参数、敏感度适用范围、覆盖率门槛和精度要求在数据盘点与模型验证后配置，不在逻辑设计中虚构固定数值。

## 16. 前端信息架构与复用

### 16.1 兼容边界与目标设计

保留现有首页和“市场、信息、因子、收益、预测、关注列表、投资组合、回测仿真、策略生成”一级板块、路由与全部当前数据展示，包括已有期货持仓、信用利差和中美利差子板块。新增能力仅在对应板块内部以子标签、分区、卡片或下钻入口增量接入；共享证据和事件详情不复制为四份。

产品交互以完整客户研究需求为目标设计，MVP只控制实现先后。尚缺数据或技术条件的功能可以预留入口、页面结构和API契约，但实现状态保存在内部能力登记、feature flag和验收记录中，不映射为面向客户的“暂未开放/尚未开发”金融状态。任何已展示页面都不得用静态占位数值或模拟结果冒充真实行情、风险、预测或PnL。

新增资产按结果类型嵌入现有板块：因子板块展示活跃度、历史有效性、事件研究和统计验证；收益板块展示统一市场表现、历史相关性和事件市场反应；回测仿真板块承载策略回测设计与真实运行结果。现有中国国债回测仿真页继续使用旧API和计算逻辑，并明确其结果类型为事件研究而非可交易PnL；任何旧页面调整须另行授权。

### 16.2 显式URL研究上下文

跨页面上下文使用显式查询参数或路径参数，不使用隐藏全局状态强制同步：

```text
asset_scope
instrument_id
as_of nullable
snapshot_id nullable
result_type nullable
result_id nullable
result_version nullable
case_id nullable
case_version nullable
return_route nullable
```

`asset_scope + instrument_id`表达当前研究对象，`as_of`只表达查询时点；历史复现必须优先使用`result_id + result_version`或`snapshot_id`。二者与日期冲突时按不可变版本解析并显示差异，不静默切换到最新结果。页面按业务需要继承参数：例如从预测到证据详情继承结果版本，从市场到组合可只继承资产；不适用参数显式忽略。旧URL不带上下文时继续使用原默认逻辑。`return_route`只能是受控站内路由标识，禁止开放跳转。

可选增强容器如下，不替换现有页面外壳：

```text
ResearchAssetShell
  AssetSelector
  InstrumentSelector
  SnapshotBadge
  DataFreshnessBadge
  ResearchStatus
  ResearchTabs
  AssetProfileProvider
```

### 16.3 统一证据详情与版本化返回

证据链接携带`evidence_type/evidence_id/evidence_version`和来源研究上下文。详情路由复用现有新闻、因子、事件、收益和策略详情页，并由类型渲染器保留专业结构：新闻原文与媒体来源、政策条款、研报观点/假设、行情指标/单位/时点、统计结果的样本/方法/不确定性。统一头部展示来源、内容性质、发布时间、可用时间、版本、授权范围及其与当前结论的`supports/refutes/supplements`关系。

详情页返回时恢复来源结果版本和筛选状态，不只返回同一日期的最新页面。正证据、反证据和限制并列；缺少反证不表示已验证。引用内容因删除、许可或保留期不可访问时显示获准元数据与失效原因，不回退到同ID最新版本，也不泄露内容。

### 16.4 传导链与冲突展示

跨资产传导采用自然语言传导链卡片和可筛选关系表，不建设复杂图前端。卡片和表格显示来源事件/指标、目标资产/标的/指标、方向、周期、机制、推断类型、证据、不确定性与验证状态。`mechanism`、`ai_inference`、`case_association`和`statistical_association`使用不同标签，统计关联不得渲染为因果箭头。

直接冲突判定要求资产/标的、目标指标、方向口径和研究周期均可比且结论相反。不同资产、指标、期限或周期的方向差异分别标记为`cross_asset_difference/metric_difference/horizon_difference`；不同机制可以并列，不得仅因方向不同自动归入`conflict`。

### 16.5 客户状态组件

统一`ResearchStatus`重点表达业务结果，而非研发进度：

| 客户状态 | 含义与主要动作 |
|---|---|
| `data_missing` | 必要数据不存在；显示缺失项、影响范围和可用补救动作 |
| `partial_coverage` | 仅部分资产/标的/期间有结果；显示覆盖分子、分母及未覆盖范围 |
| `quality_insufficient` | 有数据但质量、授权、时点或样本不足；显示不满足的规则 |
| `analysis_degraded` | 结果降级为较低粒度或定性结论；显示降级前后能力与限制 |
| `business_rejected` | 请求违反标的、权限、风险或金融规则；显示拒绝原因，不静默替换请求 |
| `system_error` | 服务、任务或依赖异常；显示追踪号和安全重试/反馈动作 |

加载中、任务处理中、需要登录和数据过期作为界面/时效辅助状态，不与上述结果状态混为一谈。内部`not_enabled/configured/basic_validated/formal_research_backtest`继续用于开发、服务门控和审计，但前端不以“尚未开发”提示代替金融结果。功能入口可以预留；若真实请求尚无数据，显示相应数据或业务状态，不生成伪结果。

### 16.6 专业页面与研究案例

预测摘要显示目标、方向/定性结论、数据截止时间、模型置信度等级和证据质量；校准、不确定性、反向风险、失效条件、模型分歧和证据可展开。组合页面保留列表、详情、手工录入和CSV行为，并增加组合模式、币种、风险覆盖和情景设计；风险值、风险等级、数据质量、计算状态和缺失原因分开。策略确认页展示冻结的资本、期间、规则、方向/仓位、成本、成交假设和主要风险；结果页分别显示生命周期、研究质量、表现评价、执行尝试、金融模型版本和零成交原因。

任一现有板块可把当前不可变结果加入轻量研究案例。案例以抽屉、侧栏或页面内入口访问，不新增一级导航；列表按版本展示事件、正反证据、预测、组合、风险、情景、策略、回测和报告引用。保存或更新案例只创建新案例版本，不复制底层数据、不触发自动分析/审批/策略执行。读取时逐条执行权限与引用状态检查，已失效引用保留位置、状态和替代版本提示。

研究案例创建时默认为个人；用户可显式关联已有项目。目标界面只使用当前有效的`manager/editor`语义：经理可管理项目关联、成员与案例共享设置，编辑者可在底层对象权限允许时查看并新增案例版本；旧`owner/viewer`仅作为后端兼容别名，不在新交互中形成额外角色。所有权转移使用独立确认页，展示接收者、项目、受影响引用、未完成任务和转移后的访问变化，并发更新使用`permission_version`防止覆盖。

关注列表保留收藏视图，并增加监测规则与提醒页签。规则编辑器根据目标类型提供阈值、变化、趋势或重要事件条件，显示数据频率、评估频率、用户时区、冷却期和去重规则；若来源是日频，界面明确标记“按日评估”而非实时。提醒卡片只提供查看证据、创建待办、加入案例或调整规则，不提供自动预测、自动策略或自动回测动作。

正式报告页面固定显示报告版本、案例版本、数据/证据快照、模型和计算参数，并提供版本历史与差异比较。动态研究视图使用明显不同的标题和时间标识，仅展示当前最新结果，不覆盖正式报告。导出面板可提前设计PDF、Word、Excel、CSV和Markdown选项；提交后显示权限/许可校验、过滤或脱敏清单及证据支持状态。若过滤使核心结论无支撑，只允许拒绝导出或基于剩余证据创建新报告版本。

## 17. 任务与调度

### 17.1 当前状态

- 现有统一执行器调度研报解析、政策文件、综合研报和每日新闻总结；
- 策略历史在统一任务列表中只读聚合，DreamStrategy 生成使用独立会话与后台任务；
- 新增资产的信用曲线、中金所持仓和美债收益率同步由HTTP接口或回填脚本触发，未发现统一定时同步；新闻分析、预测报告和因子事件研究仍有独立接口或脚本；
- 现有统一执行器具备持久任务、租约、心跳、重试和人工重跑基础，但尚未覆盖全部市场数据同步。

### 17.2 目标状态

数据更新按来源产生/发布频率、市场日历、授权调用限制和研究需求配置，不要求统一实时。专业供应商按接口能力同步，官方数据按发布安排同步，联网搜索按研究任务触发，用户上传在上传或主动更新时处理；衍生因子、预测和报告由上游变化或业务周期触发。分钟级或实时行情不作为MVP强制条件。

新增资产的长任务优先复用现有租约、心跳和执行日志模式，但不强制所有工作流共享同一领域表。满足接入条件的任务统一写入：

- \`task_runs\`
- \`task_events\`

任务幂等键示例：

```text
market-sync:{asset}:{instrument}:{date}:{source}
event-normalize:{evidence_id}:{model}:{prompt_version}
impact-assessment:{event_id}:{asset}:{instrument}:{target_metric}:{horizon}:{model}:{prompt_version}
factor-extract:{event_id}:{model}:{prompt_version}
factor-review:{candidate_id}:{review_model}:{review_prompt_version}:{candidate_version}
factor-monitor:{factor_id}:{application_scope}:{window_end}:{rule_version}
transmission-assessment:{event_id}:{source_metric}:{target_asset}:{target_metric}:{horizon}:{model}:{prompt_version}
market-performance:{asset}:{instrument}:{metric}:{start}:{end}:{calculator_version}:{snapshot}
historical-correlation:{metric_pair}:{start}:{end}:{alignment_version}:{method_version}
event-study:{event_set_hash}:{asset}:{instrument}:{metric}:{window}:{rule_version}:{snapshot}
signal-evaluation:{asset}:{instrument}:{factor}:{horizon}:{sample_end}
forecast:{asset}:{instrument}:{metric}:{horizon}:{type}:{data_cutoff}:{model}:{prompt_version}:{snapshot}
forecast-evaluation:{forecast_id}:{actual_version}:{rule_version}
strategy-version:{requirement_hash}:{context_version}:{confirmation_version}
strategy-attempt:{business_version_id}:{idempotency_key}:{attempt_no}
backtest:{business_version_id}:{execution_attempt_id}:{data_snapshot_hash}:{financial_model_set_version}
research-case-version:{case_id}:{parent_version}:{reference_set_hash}
monitor-evaluate:{rule_id}:{rule_version}:{source_snapshot_id}
research-alert:{rule_id}:{rule_version}:{dedup_key}
research-report:{report_id}:{report_version}:{case_version}:{snapshot_set_hash}
report-export:{report_id}:{report_version}:{format}:{permission_snapshot_id}:{license_decision_hash}
```

只有完成任务类型、领域状态、执行器、幂等键、失败恢复和权限契约后，长任务才进入统一调度器；在此之前保持独立批处理，不在 HTTP 请求线程中执行重计算。

每次同步记录数据所属交易日/统计期、来源发布时间、信息可用时间、系统获取时间和分析生成时间。新鲜度按资产时区、交易日历和来源发布安排计算；异常支持有限重试、人工补跑、数据过期提示和状态展示。具体频率、SLA和重试参数由数据源盘点后配置，未确认前不得写入承诺值。

监测规则的评估频率不得高于来源有效更新频率；规则保存用户时区，但按标的市场日历和来源发布节奏计算评价窗口。来源修订、迟到或补录时创建新的评价记录，并按规则版本决定是否产生更正提醒，不覆写旧提醒。提醒去重键至少包含规则版本、监测对象、触发条件、评价窗口和事件/数据版本；冷却期只抑制重复通知，不删除原始触发事实。监测任务只写评价、提醒或研究待办，禁止直接调用预测、策略生成、回测或交易执行。

组合风险计算使用`portfolio_id + portfolio_version + valuation_as_of + calculation_version`幂等；情景使用上述字段加`scenario_version + risk_parameter_snapshot_id`。组合、参数或情景版本变化创建新运行，不覆盖旧结果。策略幂等只约束本系统重复请求；只有外部服务明确提供幂等契约时才能将其扩展到外部执行，状态不明时不得自动无限重试。

## 18. 可观测性

### 18.1 指标

- 各资产最新数据时间；
- 同步成功率和耗时；
- 待核查候选事件与待分析资产影响数量；
- 模型失败率和 token；
- 预测正常/降级/拒绝/失败数量、覆盖率及各模型分歧率；
- 事件研究覆盖率；
- 回测生命周期、研究质量、表现状态及失败/零成交原因；
- 各策略标的能力状态、证据过期与验证覆盖；
- API 延迟和连接池使用；
- 页面空数据率。
- 研究案例引用可访问、失效、无权和已替代数量。
- 监测规则评价成功、未到评估时点、数据不足、去重抑制和失败数量，以及来源频率与规则频率不匹配数量；
- 正式报告版本生成、动态视图读取、各格式导出成功/拒绝数量，许可过滤、脱敏、内容替代及核心结论失去支撑数量；
- 案例所有权转移、项目成员权限变化、报告导出重验和删除编排的成功/拒绝/失败数量。

### 18.2 日志

日志必须携带：

\`trace_id、task_id、asset_scope、instrument_id、batch_id、model、prompt_version\`。

### 18.3 告警

- 数据超过 SLA 未更新；
- 连接池耗尽；
- 同一任务连续失败；
- 模型输出契约失败；
- 数据量异常下降；
- 受控预期成交测试零成交、普通回测异常指标或状态长期不明；普通策略因无信号零成交仅记录研究状态，不直接触发系统故障告警。

## 19. 安全与合规

- API 密钥、数据库密码和供应商凭据只通过环境变量或密钥系统注入。
- 数据供应商许可必须映射到接口权限。
- 外部策略服务只能接收允许传输的摘要和标识。
- AI生成代码、外部返回内容和用户策略输入均按不可信数据处理；正式能力必须验证执行沙箱、文件/环境变量/密钥/其他用户数据隔离、网络白名单、资源与超时限制。
- 用户上传文件必须进行类型、大小和内容检查。
- 所有策略版本确认、执行尝试、技术重试、取消和删除操作保留审计记录；外部幂等未确认时不声称恰好一次执行。

研究组合上传、风险参数和情景结果继承用户/组织隔离与授权范围。真实持仓保留接口边界但MVP不开启；任何外部AI调用不得携带未授权持仓明细。AI候选情景与确定性计算结果分权写入并保留审计记录。

研究案例不扩大权限：案例拥有者无权访问某个底层对象时，加入引用必须失败；后续权限收回时只保留不可泄密的引用状态。案例分享或组织可见性必须同时通过案例和每个引用对象的授权检查，导出报告亦然。URL上下文不得包含密钥或敏感持仓明细，`return_route`采用站内白名单并防止开放重定向。

案例默认属于个人；关联项目后复用现有项目角色，不另建一套RBAC。当前有效角色按代码事实为`manager/editor`，`owner/viewer`只作为旧值兼容映射，不扩张权限。每次读取、引用、生成正式报告及导出都分别校验案例/项目权限和底层对象权限；项目成员移除、角色变化或底层授权收回后立即按新权限决策，不复用过期缓存。所有权转移是目标新增能力，必须在同一事务中校验转出方、接收方和关联项目资格，递增`permission_version`并记录审计，不把当前不存在的接口描述为已实现。

报告权利拆分为`view/research_use/export/redistribute`，高一级权利不由低一级权利自动推导。导出任务在执行时重新计算报告权限、每条来源许可、保留期和分发范围，不能只依赖提交时或缓存中的判定；导出物携带报告版本、生成时间、来源清单、用途限制和审计标识。来源过滤、脱敏或替代后必须重新计算结论支持状态，核心结论无支撑时拒绝导出或要求生成新报告版本。删除编排覆盖原始数据、研究快照、正式报告、动态视图缓存、导出物、搜索索引及其他缓存；永久删除或许可到期只保留制度允许且不泄密的最小墓碑。

## 20. 测试策略

### 20.1 单元测试

- 每个 profile 的方向、时区和目标指标；
- 各资产`MarketPerformanceCalculator`的单位、基准和能力降级；
- 日期级、盘前/盘中/盘后、非交易日和跨市场事件对齐；
- 合约换月；
- 利率对冲；
- 汇率换算；
- 提示词输出契约；
- 双轴方向规则与旧中国国债兼容映射；
- 事实、观点、预测、预期和未来安排分类；
- 因子别名归并、事实/预期区分和资产命名空间；
- 字典级与应用级状态转换、禁止退休条件及历史有效期选择；
- 信号可比性、`neutral/mixed/conflict/unknown`状态；
- 传导关系类型和验证状态映射；
- 四级门控、质量原因与功能状态映射；
- 数据修订、可用时间与历史决策时点快照选择；
- 来源冲突和授权硬阻断。
- 预测白名单解析、1/5/20有效观察日映射、结果状态与概率/幅度/区间字段可空规则；
- 模型置信度、证据质量、历史校准和统计不确定性字段隔离；
- 目标配置/模拟持仓必填字段、独立金额语义、期货具体合约/手数/方向校验；
- DV01符号、净值/总绝对值、久期类型门控、币种/市场/风险因子隔离；
- 债券与期货覆盖率分母、缺失不补零和部分结果状态；
- 信用收益率组成冲击与期货价格/利率冲击防重复计入；
- 策略能力状态升级证据、别名不继承验证结论及未登记标的默认关闭；
- 业务版本哈希、实质变更重新确认、执行尝试与技术重试语义；
- 情报包令牌预算、去重/冲突、历史`available_at`和当前信息禁止回填；
- 成本、成交、结算、核算模型版本及资产专属现金流语义；
- 生命周期、研究质量、表现状态互不推导及零成交原因分类；
- 静态套保合约数、整数候选、剩余DV01及参数缺失降级；
- URL上下文解析、版本/快照优先级、旧URL默认行为和受控返回路由；
- 直接冲突可比性规则及跨资产/指标/周期差异分类；
- 六类客户状态到内部数据、业务和系统状态的映射；
- 研究案例版本、引用排序、失效/替代状态和逐引用权限过滤；
- 个人案例、项目关联、`manager/editor`角色映射、旧`owner/viewer`兼容、所有权转移和`permission_version`失效；
- 监测规则版本、用户时区、来源频率上限、评价窗口、冷却期与去重键；
- 正式报告冻结快照、重新生成升版、动态视图不回写及版本差异；
- 查看/研究使用/导出/再分发权利隔离、许可过滤后的结论支持状态与拒绝条件；
- 软删除、恢复、永久删除、许可到期和替换引用的版本及墓碑规则；

### 20.2 契约测试

- 通用 API 响应；
- 资产适配器输出；
- 外部策略与回测接口；
- 数据源适配器、单位和时间语义；
- 统一市场表现契约及异质指标禁止直接排名；
- 历史相关性、事件研究和策略回测的类型与字段隔离；
- 公共事件去重、证据关联及影响状态契约；
- 因子提取与独立审核输入隔离、程序校验和自动发布契约；
- 三维评价接口不得互相补值或默认合成；
- 结构化传导关系与自然语言解释的一致性；
- 用户上传所有者/组织隔离及结构化导入质量契约。
- 预测运行、模型独立输出、可选共识、拒绝/降级和评估契约；
- 组合模式、持仓输入来源、多币种换算、风险结果和情景版本契约；
- AI候选情景不能写正式损益，确定性计算结果与解释字段隔离；
- 外部策略能力、业务版本、执行尝试和回测金融模型契约；
- 生成代码与冻结结构化需求的一致性及未开放标的拒绝而非替换；
- 统一证据引用、类型渲染元数据、正反证据关系和版本化返回上下文；
- 研究案例只保存版本引用、不复制底层数据且不扩大对象权限；
- 监测提醒只输出评价/提醒/待办，不触发预测、策略、回测或交易接口；
- 报告版本、动态视图、PDF/Word/Excel/CSV/Markdown导出请求与异步状态契约；
- 导出时的案例权限、底层对象权限、来源许可、过滤/脱敏清单和核心结论支持状态契约；
- 当前项目`manager/editor`角色及旧角色兼容契约，所有权转移未落地前返回业务拒绝而非伪成功；

### 20.3 集成测试

- 研究闭环：同步/读取→异常发现→事件分析→因子→证据下钻；
- 条件开放的统计验证：固定模型和快照→时间对齐→目标变量→基准与稳定性；
- 条件开放的策略：能力解析→分层情报包→业务版本确认/冻结→外部执行尝试→代码与结果验收→金融模型及评价版本保存；
- 任务幂等和补跑；
- 多模型隔离；
- 多模型不可比或无聚合依据时保留冲突，不生成共识；
- 按需搜索触发、可靠来源核查、外部指令隔离、缓存/预算/超时与失败降级；
- 预测版本不覆盖、未到期不评估、历史模拟与真实时点预测分离；
- 方向/Brier/MAE/RMSE/区间覆盖和预测覆盖率按类型计算，拒绝样本不得从分母静默删除；
- 权限和审计；
- 数据缺失降级；
- 联网搜索不可用时的数据截止时间、证据范围和限制说明；
- 原始批次、标准化版本、修订关系和研究快照追溯；
- 重复事件、相关样本和重叠验证窗口处理；
- 事件族、主子事件、独立新增信息、样本资格和预定义排除规则；
- 中美源/目标市场独立窗口、夏令时和日频能力限制；
- 相关性与事件研究结果不能进入策略PnL字段；
- 候选因子审核冲突时保持候选，审核通过但统计不足时不得取得预测/策略资格；
- 因子休眠、观察、暂停、合并、退休及恢复的历史追溯；
- 冲突信号传递到预测、组合、报告和策略情报包；
- 模板不适用、共同因素驱动和统计支持不升级为因果证明；
- 事实提取粒度高于定量能力时的权限与能力拦截；
- 缺少影响记录、无显著影响和证据不足的展示差异。
- 现有CSV兼容、多资产新格式隔离、组合版本变化后的风险/情景幂等与历史保留；
- 美元本币、人民币即期折算、未对冲回报和对冲后回报能力门控；
- 部分风险参数缺失时仅输出已覆盖资产结果，页面不得展示为全组合损益；
- 历史策略特征不得注入当前新闻/预测/组合风险/事后统计，真实历史预测与当前模型回放分离；
- 受控预期成交测试与普通零交易策略分离，零交易原因、研究质量和表现状态分别展示；
- 外部服务隔离、资源、超时、网络和幂等能力不足时只生成实验结果；
- 国债期货静态套保与完整历史套保门控，基准利率风险与信用利差/违约/流动性风险不混淆；
- 市场→事件/因子/预测→证据详情→原结果版本的URL往返，以及旧页面无上下文时保持默认行为；
- 数据缺失、部分覆盖、质量不足、分析降级、业务拒绝和系统错误在页面/接口映射一致，不使用研发进度状态替代；
- 研究案例跨事件、预测、组合、风险、策略、回测和报告引用，底层更新、删除、许可变化和权限回收后仍可安全复盘；
- 个人案例关联项目、成员增删或角色变化、所有权转移后，案例权限与底层权限交集即时生效；
- 关注项升级为监测规则后按来源频率与用户时区评价，重复触发被抑制但保留事实，提醒不会启动下游金融任务；
- 正式报告重新生成创建新版本并可比较差异，动态视图更新不修改任一历史正式版本；
- 报告导出在执行时重验权限和许可，过滤后核心结论失去支撑会拒绝或转为新版本生成流程；
- 软删除可恢复，永久删除/许可到期跨原始数据、快照、报告、导出物和缓存执行，并保留合规最小墓碑及复现影响；

### 20.4 E2E

首个里程碑至少覆盖“市场研究→事件/证据→因子或定性判断→研究案例→正式报告”E2E，并验证没有AI预测或统计结果时仍可在明确限制下完成闭环。每类新增资产继续覆盖适用的研究闭环E2E；统计验证、组合风险、持续监测和策略E2E仅对已接入能力执行。所有测试同时验证现有一级导航、中国国债页面、组合、预测、策略生成、回测及当前数据内容不被替换或削弱。

## 21. 迁移方案

推荐顺序为“公共基础能力→美债→国债期货→信用债”，但迁移执行不采用严格串行瀑布。公共契约只在真实资产用例中渐进提炼；各资产的数据适配、页面和独立服务可并行。顺序调整必须在设计记录中保存触发原因、影响模块、数据/授权/模型依赖和新里程碑，并同步更新五份文档。

### 阶段 A：最小通用基础能力

- 建立 profile、资产/标的/目标指标/时间/能力状态契约；
- 盘点专业供应商、官方数据、内部数据和上传能力的覆盖、授权、频率与保留限制，建立最小数据源适配和四级门控；
- 建立批次/版本引用、信息可用时间和研究输入快照，不预建完整数据仓库；
- 建立统一市场表现契约、资产计算器接口、版本化时间对齐、事件族和样本资格契约；
- 建立预测白名单、证据准备、拒绝/降级、独立置信度、多模型输出和分类评估逻辑契约；当前中国国债10Y链路只读兼容；
- 建立目标配置/模拟持仓、多币种、风险结果、资产风险计算器、覆盖率与版本化情景逻辑契约；现有账号级组合通过适配器继续运行，真实持仓模式保持关闭；
- 建立策略标的能力登记、分层情报包、业务版本/执行尝试、版本化成本/成交/结算/核算及三维状态契约；现有入口、白名单和中国国债链路只做兼容，不自动升级能力状态；
- 为历史相关性、事件研究和策略回测建立独立结果类型，并以兼容说明保留中国国债旧事件研究页面；
- 建立公共/资产因子命名空间、别名映射、独立AI审核、程序校验、生命周期事件和应用级资格的最小旁路模型；
- 分开展示事件重要性、去重活跃度和历史有效性；以关系型存储实现事件级传导关系，不建设复杂图基础设施；
- 建立公共事件、证据、影响状态和双轴方向的最小逻辑契约，物理表与任务拆分后续确定；
- 建立显式URL上下文、统一证据引用/详情返回、传导链/关系表、客户状态映射和轻量研究案例逻辑契约；目标页面可完整设计，后端和存储按MVP用例分期实现；
- 通过适配器保留现有普通关注项和账号级报告任务，新增监测规则/提醒及正式报告版本/动态视图/授权导出契约，不改变旧增删查、再生成、重试和删除行为；
- 复用当前项目`manager/editor`成员角色并兼容旧`owner/viewer`值，个人案例、项目关联和双重权限校验先行；所有权转移在独立接口及审计完成后开放；
- 建立按数据类型配置的软删除、恢复、永久删除、许可到期和最小墓碑编排，不以一次性物理清理替代可审计流程；
- 以最少公共实现打通市场研究、事件/证据、因子或定性判断、研究案例和正式报告；预测与统计验证以可选节点接入，缺失时不得阻断定性报告；
- 按实际用例创建最少的新表和 API，不一次性落地全部目标模型；
- 实现中国国债只读 LegacyAdapter；
- 在现有一级板块内部增量加入资产子板块，以 feature flag 单独开关；现有页面、路由和数据展示保持不变。
- feature flag和能力登记只管理实施与服务门控，不作为客户可见“尚未开发”状态；任何预留入口均不得连接占位金融数据。

### 阶段 B：美债

- 复用2Y/10Y/30Y曲线，接入美债事件适配器，优先验证公共多资产契约、时区、跨市场日历、研究案例和正式报告闭环；5Y、预测、统计验证和策略分别按开放条件推进。
- 先开放美元本币研究；盘点USD/CNY授权后决定是否在MVP增加人民币即期金额折算，未对冲和对冲后回报继续独立门控。

### 阶段 C：国债期货

本阶段的合约数据、页面和适配器可与阶段B并行，不依赖美债全部能力完成。

- 先补合约与价格数据，再接入连续合约、换月和交易成本模型；现有持仓页继续可用，策略按具体标的能力登记开放，白名单本身不等于验证。
- 模拟持仓以具体合约、手数和方向建模，保证金、DV01、基差与换月风险按参数可用性分别开放。
- 先在组合/风险服务实现定性与静态套保；现货/期货历史、真实合约、结算、成本和多资产多腿能力通过后才开放完整历史套保回测。

### 阶段 D：信用债

本阶段可按客户需求和分层数据授权提前并行；公共能力只复用已经由实际用例验证的部分。

- 先复用整体信用曲线完成降级研究视图；取得授权后再接入评级/行业/期限曲线和超额收益模型。
- 基础集中度先行；基准利率风险、信用利差风险及CS01在主数据、市值和敏感度口径满足后开放。

### 阶段 E：收敛

- 评估将中国国债迁移到通用表；
- 下线重复 API；
- 深化跨资产报告、组合、监测和策略协同；正式报告基础闭环不延后到本阶段。

## 22. 回滚方案

- 新功能使用 feature flag 按资产启用。
- 新旧 API 并行一段时间。
- 新表写入失败不影响旧中国国债链路。
- 前端资产入口可单独关闭。
- 数据迁移使用可重复脚本，不删除旧表。

## 23. 待确认问题

1. 公司现有专业供应商、接口、数据库、资产覆盖及使用/缓存/展示/再分发/外部AI传输授权。
2. 现有资源不能覆盖时是否新增商业采购及其优先级。
3. 联网搜索工具/供应商、接口、触发阈值、来源筛选、缓存、预算及与现有分析流程的集成实现。
4. 用户上传的具体文件格式、结构化字段映射、导入限制、隔离和权限模型。
5. 各来源的具体同步频率、生产SLA、重试和人工补跑参数。
6. 分资产、标的、指标、功能和时间范围的数据质量阈值。
7. 原始数据、标准化版本、快照的物理存储、授权限制和保留周期。
8. 各资产市场指标公式、信用利差基准、总回报口径和计算器实现。
9. DreamStrategy 对各具体标的、模板、行情、真实合约映射、成本/成交/结算/核算、多资产多腿及代码执行安全的可验证支持范围；`FCT_T_MAIN`需补可复核运行证据，`100040`需确认是否存在独立验证。
10. USD/CNY授权数据对人民币即期折算的支持情况、未对冲/对冲后回报的现金流与远期数据，以及国债期货连续合约规则。
11. 公共与资产专属因子清单、别名和版本迁移规则，以及现有因子重复项盘点结果。
12. 因子审核提示词、模型选择、审核冲突策略、监测周期、休眠/观察/暂停/退休阈值和复审次数。
13. 事件重要性、活跃度和历史有效性的公式、窗口、标准化方法及排序展示。
14. 信号定量汇总规则与权重；没有验证依据前只允许定性摘要。
15. 传导模板、逻辑字段、统计验证方法，以及关系表的具体筛选、排序和默认展开规则；展示载体已确认为传导链卡片与关系表。
16. 交易日历及时区组件、盘前/盘中/盘后边界、T及各观察窗口的起点和计数规则。
17. 事件聚类、事件族、窗口重叠处理算法、样本资格阈值和稳健性方法。
18. 历史相关性的指标对齐、频率、计算方法、显著性和展示口径。
19. 各预测白名单的具体目标、类型开放阈值和数据/历史表现门槛。
20. 概率校准、区间生成、多模型聚合、评估窗口、模型复核与切换的算法和参数。
21. Excel/内部持仓接口、真实持仓模式和组织共享的字段、权限、数据安全、估值及审计开放条件。
22. 各资产DV01/CS01公式与参数来源、覆盖率分母、规则情景冲击、敏感度适用范围和计算精度阈值。
23. 外部服务沙箱、资源、超时、网络、取消、请求幂等、运行状态查询和审计契约；在未确认前正式研究回测保持关闭。
24. 各资产成本、成交、结算和收益/现金流核算模型的具体参数、数据来源、版本规则与正式研究质量门槛。
25. 静态套保整数选择目标、资本/保证金约束、供应商每合约DV01或CTD参数来源，以及完整历史套保的多腿能力。
26. 研究案例、监测规则、提醒、报告版本、导出任务和删除墓碑的物理存储选择，以及现有关注项/报告任务的兼容迁移方式。
27. 显式URL上下文各页面的继承矩阵、最大URL长度及复杂筛选状态是否使用受控短链或服务端快照。
28. 各资产监测指标的阈值/变化/趋势算法、来源频率、评价窗口、冷却期、去重键、提醒渠道和更正提醒规则。
29. 各数据类型的保留期限、恢复窗口、永久删除授权人、法务保留优先级，以及缓存/搜索索引的完成时限。
30. 查看、研究使用、导出和再分发的来源许可矩阵；核心/补充证据判定及过滤、脱敏、替代后重新生成规则。
31. PDF、Word、Excel、CSV和Markdown的实施优先级、统一内容模型、格式特有字段及大文件/异步交付限制。

