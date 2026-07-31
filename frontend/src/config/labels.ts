/**
 * 前端标签中文映射配置
 * 集中管理所有页面标签、模型名称、操作类型等中英文映射
 */

// ========== 页面路由 → 中文标题 ==========
export const PAGE_TITLE_MAP: Record<string, string> = {
  '/news': '新闻',
  '/factors': '因子',
  '/data': '数据',
  '/prediction': '预测',
  '/agents': 'Agent',
  '/select-strategy': 'AI推荐',
  '/strategies': '策略',
  '/change': '变动对比',
  '/macro-signal-logs': '信号日志',
  '/dashboard': '看板',
  '/login': '登录',
  '/my-usage': '我的使用',
  '/research': '研报',
  '/ai-strategy-generation': 'AI策略生成',
  '/macro-data': '宏观数据',
};

// ========== 模型名称 → 中文显示名 ==========
export const MODEL_NAME_MAP: Record<string, string> = {
  'doubao': '豆包',
  'deepseek': 'DeepSeek',
  'qwen': '通义千问',
  'gpt-4': 'GPT-4',
  'gpt-4o': 'GPT-4o',
  'gpt-3.5-turbo': 'GPT-3.5',
  'claude-3-opus': 'Claude Opus',
  'claude-3-sonnet': 'Claude Sonnet',
  'claude-3-haiku': 'Claude Haiku',
  'claude-3.5-sonnet': 'Claude 3.5 Sonnet',
  'claude-opus-4': 'Claude Opus 4',
};

// ========== 操作类型 → 中文标签 ==========
export const ACTION_LABEL_MAP: Record<string, string> = {
  page_view: '页面访问',
  page_enter: '进入页面',
  page_leave: '离开页面',
  click: '点击',
  tab_switch: '切换标签',
  date_select: '选择日期',
  report_view: '查看报告',
  news_click: '点击新闻',
  news_scroll: '新闻滚动',
  factor_filter: '筛选因子',
  strategy_click: '点击策略',
  strategy_search: '搜索策略',
  strategy_filter: '策略筛选',
  snapshot_compare: '对比快照',
  chart_interact: '图表交互',
  download: '下载',
  export: '导出',
  login: '登录',
  logout: '登出',
  idle_timeout: '空闲超时',
  scroll: '滚动',
  input: '输入',
  search: '搜索',
  filter_change: '筛选变更',
};

// ========== 调用来源 → 中文标签 ==========
export const CALL_SOURCE_MAP: Record<string, string> = {
  chat: 'Agent聊天',
  analysis: '新闻分析',
  strategy: 'AI策略推荐',
  change: 'AI策略变动',
  research: '研报分析',
};

// ========== 退出类型 → 中文标签 ==========
export const EXIT_TYPE_MAP: Record<string, string> = {
  navigation: '导航切换',
  idle_timeout: '空闲超时',
  close: '关闭页面',
};

// ========== 操作目标 → 中文标签（审计日志"目标"列） ==========
export const ACTION_TARGET_MAP: Record<string, string> = {
  manual_trigger: '手动触发',
  audit_log: '审计日志导出',
  current: '当前预测',
  history: '历史预测',
  strategy_filter: '策略筛选',
  strategy_search: '策略搜索',
  all: '全部策略',
  quant: '量化策略',
  trading: '交易策略',
};

// ========== 通用 UI 标签 ==========
export const UI_LABELS = {
  loading: '加载中...',
  noData: '暂无数据',
  allPages: '全部页面',
  allActions: '全部操作',
  today: '今日',
  month: '本月',
  total: '累计',
  calls: '调用',
  tokens: 'Token',
  users: '用户',
  days: '天',
  times: '次',
  seconds: '秒',
  hours: '时',
  page: '页',
  rows: '条',
  confirm: '确定',
  cancel: '取消',
  apply: '应用',
  reset: '重置',
  search: '搜索',
  export: '导出',
  refresh: '刷新',
  close: '关闭',
  prevPage: '上一页',
  nextPage: '下一页',
  startDate: '开始日期',
  endDate: '结束日期',
  dateRange: '日期范围',
} as const;

// ========== 工具函数 ==========

/** 路由 → 中文页面标题 */
export function getPageTitle(route: string): string {
  if (route === '/' || route.startsWith('/news')) return '新闻';
  if (PAGE_TITLE_MAP[route]) return PAGE_TITLE_MAP[route];
  for (const [prefix, title] of Object.entries(PAGE_TITLE_MAP)) {
    if (route.startsWith(prefix)) return title;
  }
  return route;
}

/** 模型名称 → 中文显示名 */
export function getModelLabel(model: string): string {
  return MODEL_NAME_MAP[model] || model;
}

/** 操作类型 → 中文标签 */
export function getActionLabel(type: string): string {
  return ACTION_LABEL_MAP[type] || type;
}

/** 调用来源 → 中文标签 */
export function getCallSourceLabel(source: string): string {
  return CALL_SOURCE_MAP[source] || source;
}

/** 退出类型 → 中文标签 */
export function getExitTypeLabel(type: string): string {
  return EXIT_TYPE_MAP[type] || type;
}

/** 操作目标 → 中文标签（优先精准匹配，否则尝试前缀匹配如 strategy_code:xxx → 策略代码:xxx） */
export function getActionTargetLabel(target: string): string {
  if (!target) return '';
  if (ACTION_TARGET_MAP[target]) return ACTION_TARGET_MAP[target];
  // 处理带动态值的格式
  if (target.startsWith('strategy_code:')) return '策略代码:' + target.slice('strategy_code:'.length);
  if (target.startsWith('news_id:')) return '新闻ID:' + target.slice('news_id:'.length);
  return target;
}
