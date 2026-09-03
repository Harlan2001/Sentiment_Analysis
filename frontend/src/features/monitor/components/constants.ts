/**
 * 看板常量定义
 */

// 新闻源名称映射（脱敏）
export const NEWS_SOURCES: Record<string, string> = {
  wallstreetcn: '数据源1',
  yicai: '数据源2',
}

// 告警阈值
export const ALERT = {
  PENDING_NEWS_YELLOW: 100,
  PENDING_NEWS_RED: 500,
  COVERAGE_YELLOW: 80,
  COVERAGE_RED: 50,
  VECTOR_PENDING_YELLOW: 200,
  VECTOR_PENDING_RED: 1000,
  VECTOR_COVERAGE_YELLOW: 90,
  VALID_ANALYSIS_YELLOW: 90,
  FACTOR_ASSOC_COVERAGE_YELLOW: 80,
  TIMELINESS_ANALYSIS_YELLOW: 2, // 小时
  TIMELINESS_FACTOR_YELLOW: 2, // 小时
  TIMELINESS_REPORT_YELLOW: 1, // 天
}

// 因子类别颜色
export const CATEGORY_COLORS: Record<string, string> = {
  POLICY: '#3b82f6',
  MACRO: '#f59e0b',
  LIQUIDITY: '#10b981',
  RISK: '#ef4444',
  SENTIMENT: '#8b5cf6',
  INDUSTRY: '#06b6d4',
}

// 因子类别中文映射（与后端 config.py FACTOR_CATEGORY_MAP 保持一致）
export const CATEGORY_NAME_MAP: Record<string, string> = {
  POLICY: '政策',
  MACRO: '宏观',
  LIQUIDITY: '流动性',
  RISK: '风险',
  SENTIMENT: '情绪',
  INDUSTRY: '行业',
}

// 期限色阶（用于收益率sparkline）
export const PERIOD_COLORS = [
  '#60a5fa',
  '#818cf8',
  '#a78bfa',
  '#c084fc',
  '#e879f9',
  '#fb923c',
  '#fbbf24',
  '#34d399',
  '#f87171',
]
