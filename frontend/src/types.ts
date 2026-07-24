export interface YieldPoint {
  date: string;
  value: number;
}

export interface Factor {
  code: string;
  name?: string;
  category?: string;
  direction?: string; // positive | negative | neutral
  driver?: string;
}

export interface NewsAnalysisItem {
  direction: string;
  horizon: string;
  reason: string;
  model: string;
  factors?: Factor[];
}

export interface Prediction {
  up_probability: number;
  down_probability: number;
  neutral_probability: number;
  expected_bp_range: string;
}

export interface NewsContentBlock {
  id: number;
  news_id: number;
  block_type: 'text' | 'quote' | 'image' | 'heading' | 'table';
  block_order: number;
  content?: string;
  heading_level?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  image_url?: string;
  image_alt?: string;
  image_width?: string;
  table_caption?: string;
  table_unit?: string;
  table_headers?: any[];
  table_rows?: any[][];
  created_at?: string;
}

export interface NewsItem {
  id: number;
  title: string;
  content?: string;
  content_blocks?: NewsContentBlock[];
  summary?: string;
  publish_time?: string;
  publisher?: string;
  source?: string; // 新闻源：cls, wechat 等
  direction?: string; // 分析方向：看涨、看跌、中性
  horizon?: string; // 分析期限：短期、中期、长期
  reason?: string; // 分析原因
  model?: string; // 分析模型
  selected_model?: string; // 当前选择模型
  factors?: Factor[]; // 相关因子列表
  analyses?: NewsAnalysisItem[]; // 多模型结果
}

export interface NewsSource {
  key: string;
  name: string;
  enabled: boolean;
}

export interface SimilarNews {
  news_id: number;
  title: string;
  score: number;
}

export interface SimilarPeriod {
  date_range: {
    start: string;
    end: string;
  };
  period: string;
  similarity_score: number;
  news_ids: number[];
}

export interface MultiSimilarityResult {
  news_id: number;
  text_similarity: number;
  yield_similarity: number;
  combined_similarity: number;
  period: string;
  title?: string;
  publish_date?: string;
}

export interface RelativeChange {
  date: string;
  change: number;
}

export interface NewsYieldData {
  news_id: number;
  period: string;
  publish_date: string;
  data: YieldPoint[];
  relative_changes: RelativeChange[];
  window_before: number;
  window_after: number;
  window_start: string;
  window_end: string;
}

export interface ForecastPrediction {
  上涨概率: number;
  下跌概率: number;
  上涨基点: number;
  下跌基点: number;
  分析理由: string;
  置信度?: number;
  假设条件?: string[];
}

export interface ScenarioItem {
  描述: string;
  概率: number;
  触发条件?: string;
}

export interface ScenarioAnalysis {
  bullish: ScenarioItem;
  bearish: ScenarioItem;
  baseline?: ScenarioItem;
  black_swan?: ScenarioItem;
}

export interface FullForecastReport {
  // 全部使用中文键名，扁平文本字段
  市场概览?: string;
  技术分析?: string;
  因子分析?: string;
  预测结果?: {
    日?: ForecastPrediction;
    周?: ForecastPrediction;
    月?: ForecastPrediction;
  };
  情景分析?: {
    基准?: ScenarioItem;
    牛市?: ScenarioItem;
    熊市?: ScenarioItem;
    黑天鹅?: ScenarioItem;
  };
  策略建议?: string;
  风险提示?: string;
  生成时间?: string;
  报告摘要?: string;
}

export interface ForecastReport {
  trade_date: string;
  model_name: string;
  prompt_version: string;
  forecast_type: string; // 'full_report', 'day', 'week', 'month'
  prediction: ForecastPrediction | FullForecastReport;
  created_at: string;
}

export interface ForecastResponse {
  reports: ForecastReport[];
  count: number;
}

export interface ForecastHistoryItem {
  date: string;
  reports: {
    day?: ForecastPrediction;
    week?: ForecastPrediction;
    month?: ForecastPrediction;
    full_report?: FullForecastReport;
  };
}

export interface ForecastHistoryResponse {
  history: ForecastHistoryItem[];
}

// Tool-related types
export interface NewsCard {
  id: number;
  title: string;
  summary: string;
  date: string;
  source: string;
  url: string;
  direction?: string;
  horizon?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  content: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  error?: string;
  tool_result?: ToolResultPayload;
}

export interface ToolResultPayload {
  news?: NewsCard[];
}

export interface ChatResponseWithTools extends ChatResponse {
  tool_result?: ToolResultPayload;
}

// ========== Agent / Skill System Types ==========

/** SSE 事件类型 */
export type SSEEventType =
  | 'thinking'
  | 'content'
  | 'tool_call'
  | 'tool_executing'
  | 'tool_result'
  | 'done'
  | 'error';

export interface SSEContentEvent {
  type: 'content';
  content: string;
}

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface SSEToolCallEvent {
  type: 'tool_call';
  tool_calls: ToolCall[];
}

export interface SSEToolExecutingEvent {
  type: 'tool_executing';
  tool_call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
}

export interface SSEToolResultEvent {
  type: 'tool_result';
  tool_call_id: string;
  tool_name: string;
  result?: unknown;
  error?: string;
  duration_ms?: number;
}

export interface SSEDoneEvent {
  type: 'done';
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export interface SSEErrorEvent {
  type: 'error';
  message: string;
  code?: string;
}

export interface SSEThinkingEvent {
  type: 'thinking';
}

export type SSEEvent =
  | SSEThinkingEvent
  | SSEContentEvent
  | SSEToolCallEvent
  | SSEToolExecutingEvent
  | SSEToolResultEvent
  | SSEDoneEvent
  | SSEErrorEvent;

/** 工具调用结果（UI 中使用） */
export interface ToolCallResult {
  toolCallId: string;
  toolName: string;
  toolDisplayName: string;
  toolIcon: string;
  input: Record<string, unknown>;
  output?: unknown;
  error?: string;
  durationMs?: number;
  status: 'pending' | 'executing' | 'success' | 'error';
  collapsed: boolean;
}

/** Agent Skill 定义（欢迎界面展示用） */
export interface AgentSkill {
  name: string;
  description: string;
  icon: string;
  category: 'news' | 'analysis' | 'data' | 'market';
}

/** 扩展的聊天消息（Agent 专用） */
export interface AgentMessage {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCall[];
  toolResults?: ToolCallResult[];
}

// ========== Factor Candidate Types ==========

export interface FactorCandidate {
  id: number;
  code: string;
  name: string;
  category: string;
  similarity_score: number;
  ai_recommendation: string;
  status: 'pending' | 'reviewing' | 'approved' | 'rejected' | 'merged';
  reviewer_notes?: string;
  created_at: string;
  reviewed_at?: string;
  reviewed_by?: string;
  news_id: number;
  news_title: string;
}

export interface CandidatesResponse {
  candidates: FactorCandidate[];
  count: number;
  page: number;
  total_pages: number;
}

export interface CandidatesStats {
  total: number;
  pending: number;
  reviewing: number;
  approved: number;
  rejected: number;
  merged: number;
}

export interface ReviewAction {
  action: 'approve' | 'reject' | 'merge' | 'start_review';
  reviewer: string;
  notes?: string;
}

export interface ReviewResponse {
  success: boolean;
  message: string;
  candidate?: FactorCandidate;
}

// ========== Factor Library Types ==========

export interface FactorDefinition {
  code: string;
  name: string;
  category: string;
  description?: string;
  last_updated?: string;
}

export interface FactorNewsItem {
  id: number;
  title: string;
  publish_time: string;
  publish_date: string;
  direction: string;
  horizon: string;
  factor_direction: string;
}

export interface FactorNewsResponse {
  factor: {
    code: string;
    name: string;
    category: string;
  } | null;
  news: FactorNewsItem[];
  count: number;
}

export interface AllFactorsResponse {
  factors: FactorDefinition[];
  structure: Record<string, Record<string, [string, string, string][]>>;
}

export interface FactorsByCategoryResponse {
  category: string;
  subcategories: string[];
  factors: FactorDefinition[];
  count: number;
}

// ========== Graph Augmentation Types ==========

export interface GraphAugmentNode {
  id: string;
  label: string;
  direction?: 'up' | 'down';
  for_variable?: string;
}

export interface GraphAugmentRelationship {
  source: string;
  target: string;
  relation: string;
}

export interface GraphAugmentResult {
  events: GraphAugmentNode[];
  market_variables: GraphAugmentNode[];
  variable_changes: GraphAugmentNode[];
  valuation_outcomes: GraphAugmentNode[];
  relationships: GraphAugmentRelationship[];
}

export interface GraphAugmentExtractResult {
  summary: string;
  main_events: string[];
  main_variable_changes: string[];
  notes: string[];
}

export type GraphAugmentStatus = 'RUNNING' | 'WAITING_REVIEW' | 'COMPLETED' | 'FAILED' | 'REJECTED';

export interface GraphAugmentJob {
  id: number;
  news_id: number;
  run_id: string;
  status: GraphAugmentStatus;
  stage: string;
  result_json: GraphAugmentResult | null;
  extract_json: GraphAugmentExtractResult | null;
  created_at: string;
  updated_at: string;
}

export interface GraphAugmentStartResponse {
  runId: string;
}

export interface GraphAugmentStatusResponse {
  runId: string;
  status: GraphAugmentStatus;
  stage: string;
  startedAt: string;
  updatedAt: string;
}

// ========== Macro Signal Request Log Types ==========

export interface MacroSignalRequestLogItem {
  id: number;
  request_id: string;
  factor_code: string;
  signal_type: string;
  query_start_time: string | null;
  query_end_time: string | null;
  decay_lambda: number | null;
  signal_value: number | null;
  confidence: number | null;
  news_count: number;
  queried_news: number[];
  success: number; // 0 or 1
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
  latency_ms: number | null;
}

export interface MacroSignalRequestLogQuery {
  page?: number;
  page_size?: number;
  request_id?: string;
  factor_code?: string;
  success?: number;
  signal_type?: string;
  start_time?: string;
  end_time?: string;
}

export interface MacroSignalRequestLogListResponse {
  items: MacroSignalRequestLogItem[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
  filters: MacroSignalRequestLogQuery;
}


// ========== Strategy Types ==========

export interface StrategyDetails {
  // 量化策略
  factor_type?: string;
  factor_type_label?: string;
  factor_category?: string;
  factor_category_label?: string;
  research_status?: string;
  research_status_label?: string;
  frequency?: string;
  frequency_label?: string;
  data_source?: string;
  data_source_label?: string;
  variety_code?: string;
  exam_id?: string;
  exam_interval?: string;
  ic_window?: number | null;
  subject_category?: string;
  breed_code?: string;
  // 交易策略
  strategy_type?: string;
  strategy_type_label?: string;
  version?: string;
  scope?: string;
  reference?: string;
  product_type?: string;
  approval_status?: string;
}

export interface StrategyItem {
  id: string;
  name: string;
  category: string;
  category_code: string;
  sub_category: string;
  sub_category_code?: string;
  source_type: string;
  source_type_label: string;
  status: string;
  status_code?: string;
  risk_level: string;
  description: string;
  details: StrategyDetails;
  create_time: string;
  modify_time: string;
  raw?: any;
}

export interface AllStrategiesResponse {
  success: boolean;
  strategies: StrategyItem[];
  quant_strategies: StrategyItem[];
  trading_strategies: StrategyItem[];
  total: number;
  quant_total: number;
  trading_total: number;
  errors?: Array<{ source: string; error: string }>;
}

// ========== Change / Strategy Comparison Types ==========

export interface StockRecommendItem {
  code: string;
  name: string;
  rating: string;
  weight: number;
  reason: string;
  tags: string[];
  risk_level: string;
}

export interface StrategyRecommendItem {
  id: string;
  name: string;
  priority: number;
  weight: number;
  target_pool: string[];
  trigger_logic: string;
}

export interface SummaryStats {
  sentiment?: string;
  pos_ratio?: number;
  neg_ratio?: number;
  hot_tags?: string[];
  market_overview?: string;
}

export interface ChangeSnapshotItem {
  id: number;
  version_time: string;
  window_start: string;
  window_end: string;
  news_total: number;
  news_added_count: number;
  news_removed_count: number;
  stock_count: number;
  strategy_count: number;
  generate_status: number;
  create_time: string;
}

export interface ChangeSnapshotsResponse {
  success: boolean;
  items: ChangeSnapshotItem[];
  count: number;
}

export interface StockRemovedItem {
  code: string;
  name: string;
  prev_rating: string;
}

export interface StockModifiedItem {
  code: string;
  name: string;
  old_rating?: string;
  new_rating?: string;
  old_weight?: number;
  new_weight?: number;
  old_reason?: string;
  new_reason?: string;
}

export interface StrategyRemovedItem {
  id: string;
  name: string;
  prev_priority: number;
}

export interface StrategyModifiedItem {
  id: string;
  name: string;
  old_priority?: number;
  new_priority?: number;
  old_weight?: number;
  new_weight?: number;
  old_trigger_logic?: string;
  new_trigger_logic?: string;
}

export interface ChangeCompareResponse {
  success: boolean;
  old_snapshot_id: number;
  new_snapshot_id: number;
  old_summary: SummaryStats;
  new_summary: SummaryStats;
  base_info: {
    old_version: string;
    new_version: string;
    old_window: [string, string];
    new_window: [string, string];
    news_diff: {
      added_count: number;
      removed_count: number;
    };
  };
  diff_summary: {
    new_stocks: number;
    removed_stocks: number;
    rating_changes: number;
    strategy_changes: number;
  };
  stock_changes: {
    added: StockRecommendItem[];
    removed: StockRemovedItem[];
    modified: StockModifiedItem[];
  };
  strategy_changes: {
    added: StrategyRecommendItem[];
    removed: StrategyRemovedItem[];
    modified: StrategyModifiedItem[];
  };
}

export interface ChangeTriggerResponse {
  success: boolean;
  message: string;
  skipped?: boolean;
  snapshot?: Record<string, unknown>;
}

// ========== Dashboard Types ==========

export interface ServiceStatusItem {
  ok: boolean;
  latency_ms?: number;
  loaded?: boolean;
  ntotal?: number;
  model_name?: string;
  dim?: number;
  error?: string;
}

export interface ServiceStatus {
  mysql: ServiceStatusItem;
}

export interface TopCards {
  news_total: number;
  analyzed: number;
  pending: number;
  factor_total: number;
  yield_days: number;
}

// Module A: News
export interface SourceDistribution {
  source: string;
  name: string;
  count: number;
  percentage: number;
}

export interface LatestPerSource {
  source: string;
  name: string;
  latest_time: string | null;
  status: 'ok' | 'yellow' | 'red';
}

export interface Trend7dItem {
  date: string;
  [sourceName: string]: { count: number; analyzed_count: number } | string;
}

export interface NewsModuleData {
  total: number;
  trend_7d: Trend7dItem[];
  source_distribution: SourceDistribution[];
  latest_per_source: LatestPerSource[];
}

// Module B: Analysis
export interface ModelDistribution {
  model: string;
  count: number;
  percentage: number;
}

export interface Direction7dItem {
  date: string;
  [direction: string]: number | string;
}

export interface AnalysisModuleData {
  analyzed: number;
  pending: number;
  coverage_pct: number;
  model_distribution: ModelDistribution[];
  direction_7d: Direction7dItem[];
  valid_analysis_pct: number;
  timeliness_diff_hours: number | null;
}

// Module C: Factor
export interface CategoryDistribution {
  category: string;
  display_name: string;
  count: number;
}

export interface TypeDistribution {
  factor_type: string;
  count: number;
}

export interface FactorTrend {
  date: string;
  count: number;
}

export interface FactorModuleData {
  total: number;
  category_distribution: CategoryDistribution[];
  type_distribution: TypeDistribution[];
  new_factors_7d: number;
  new_factors_trend_7d: FactorTrend[];
  association_coverage_pct: number;
  update_timeliness_diff_minutes: number | null;
}

// Module D: Vector
export interface VectorModuleData {
  indexed_count: number;
  pending_count: number;
  coverage_pct: number;
}

// Module E: Yield
export interface PeriodCompleteness {
  period: string;
  display_name: string;
  count: number;
}

export interface LatestYield {
  period: string;
  display_name: string;
  latest_date: string | null;
  latest_value: number | null;
  sparkline: number[];
}

export interface YieldModuleData {
  date_min: string | null;
  date_max: string | null;
  coverage_days: number;
  period_completeness: PeriodCompleteness[];
  latest_yields: LatestYield[];
}

// Module F: Forecast
export interface CoverageDay {
  date: string;
  has_report: boolean;
}

export interface ForecastModuleData {
  total_reports: number;
  latest_date: string | null;
  coverage_30d: CoverageDay[];
}

// Dashboard Core Response
export interface DashboardCoreData {
  generated_at: string;
  service_status: ServiceStatus;
  top_cards: TopCards;
  news: NewsModuleData;
  analysis: AnalysisModuleData;
  factor: FactorModuleData;
  vector: VectorModuleData;
  yield: YieldModuleData;
  forecast: ForecastModuleData;
}

// ========== Behavior / Audit Types ==========

export interface BehaviorStats {
  active_users_today: number;
  sessions_today: number;
  avg_duration_7d: number;
  top_page: string | null;
  power_users?: number;
  churn_risk_users?: number;
  activity_trend?: ActivityTrendItem[];
  hourly_heatmap?: HeatmapItem[];
  page_distribution: { page_route: string; page_title: string; count: number }[];
  page_avg_duration: { page_route: string; avg_sec: number }[];
}

export interface ActivityTrendItem {
  date: string;
  dau: number;
  sessions: number;
}

export interface HeatmapItem {
  hour: number;
  day_of_week: number;
  count: number;
}

export interface AuditLogEntry {
  id: number;
  session_id: number;
  user_id: number;
  username: string;
  page_route: string;
  page_title: string;
  enter_time: string;
  leave_time: string | null;
  duration_sec: number | null;
  exit_type: string | null;
  action_type?: string;
  action_target?: string;
  action_detail?: Record<string, unknown> | null;
}

export interface AuditLogResponse {
  items: AuditLogEntry[];
  total: number;
  limit: number;
  offset: number;
  total_pages: number;
}

export interface PageVisitEvent {
  page_route: string;
  page_title?: string;
  enter_time: string;
  leave_time?: string;
  duration_sec?: number;
  exit_type?: string;
  action_type?: string;
  action_target?: string;
  action_detail?: Record<string, unknown>;
  client_ts?: string;
}

export interface BehaviorBatchResponse {
  received: number;
}

// ========== User Profile Types ==========

export interface RadarDimension {
  dimension: string;
  score: number;     // 0-100
  value: number;
  unit: string;
}

export interface UserPreferences {
  top_pages: { route: string; title: string; affinity: number }[];
  peak_slot: string;
  peak_hour: number | null;
  hour_distribution: Record<string, number>;
  report_focused: boolean;
  strategy_focused: boolean;
  power_user: boolean;
  churn_risk: number;
}

export interface ActiveUser {
  id: number;
  username: string;
  display_name: string;
  department: string | null;
  company: string | null;
  role: string;
}

export interface UserBehaviorProfile {
  id: number;
  user_id: number;
  username: string;
  total_sessions: number;
  total_page_views: number;
  total_active_sec: number;
  first_visit: string | null;
  last_visit: string | null;
  active_days_30d: number;
  avg_session_sec: number;
  avg_daily_pages_30d: number;
  page_affinity: Record<string, number>;
  peak_hour: number | null;
  hour_distribution: Record<string, number>;
  distinct_pages_30d: number;
  advanced_feature_used: boolean;
  is_power_user: boolean;
  is_report_focused: boolean;
  is_strategy_focused: boolean;
  churn_risk_score: number;
  computed_at: string | null;
  profile_version: string;
  updated_at: string | null;
  radar?: RadarDimension[];
  preferences?: UserPreferences;
}

export interface UserProfileListResponse {
  profiles: UserBehaviorProfile[];
  count: number;
}

export interface UserCompareDimension {
  dimension: string;
  label: string;
  values: { user_id: number; username: string; value: number }[];
}

export interface UserCompareResponse {
  profiles: UserBehaviorProfile[];
  comparison: UserCompareDimension[];
}

// ========== Token Usage Types ==========

export interface TokenOverview {
  today_tokens: number;
  month_tokens: number;
  all_tokens: number;
  today_calls: number;
  today_users: number;
  today_failed: number;
  by_source: { source: string; tokens: number; calls: number }[];
}

export interface TokenTrendItem {
  date: string;
  total: number;
  [modelName: string]: number | string;
}

export interface TokenTrendResponse {
  trend: TokenTrendItem[];
}

export interface TokenModelDist {
  model: string;
  tokens: number;
  calls: number;
  percentage: number;
}

export interface TokenByModelResponse {
  models: TokenModelDist[];
}

export interface UserTokenItem {
  user_id: number;
  username: string;
  display_name: string;
  role: string;
  department: string | null;
  employee_no: string | null;
  is_admin: boolean;
  today_tokens: number;
  month_tokens: number;
  total_tokens: number;
  total_calls: number;
  active_days_30d: number;
  last_active: string | null;
}

export interface UserTokenListResponse {
  items: UserTokenItem[];
  total: number;
  limit: number;
  offset: number;
  total_pages: number;
}

// ========== Macro Data Types ==========

/** 宏观指标元数据 */
export interface MacroIndicator {
  code: string;
  name: string;
  category: 'strong' | 'medium' | 'weak' | 'precious' | 'bond' | 'general';
  desc: string;
}

/** 指标分类 */
export interface MacroCategory {
  key: string;
  label: string;
}

/** /sapi/macro-data/indicators 响应 */
export interface MacroIndicatorsResponse {
  indicators: MacroIndicator[];
  categories: MacroCategory[];
  total: number;
}

/** 单条宏观数据点 */
export interface MacroDataPoint {
  datestr: string;
  value: number | null;
}

/** 单个指标的时序数据 */
export interface MacroDataSeries {
  zbcode: string;
  name: string;
  category: string;
  data: MacroDataPoint[];
}

/** /sapi/macro-data/data 响应 */
export interface MacroDataResponse {
  indicators: MacroDataSeries[];
  query: {
    zbcode: string;
    start: string | null;
    end: string | null;
  };
}
