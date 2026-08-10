/**
 * 全局常量 — 前端统一配置中心
 *
 * 与后端 backend/config/config.py 中的 API_PREFIX 保持一致。
 */

/** API 路由前缀 */
export const API_PREFIX = '/sapi'

/** 工具中文名映射（与后端 backend/agent/tools.py 一致） */
export const TOOL_DISPLAY_NAMES: Record<string, string> = {
  search_news: '新闻搜索',
  get_news_by_date: '按日期获取新闻',
  get_news_detail: '新闻详情',
  find_similar_news: '相似新闻搜索',
  list_factors: '因子列表',
  get_news_by_factor: '因子关联新闻',
  compute_macro_signal: '宏观信号计算',
  get_yield_curve: '收益率曲线',
}

/** 工具图标映射 */
export const TOOL_ICONS: Record<string, string> = {
  search_news: '📰',
  get_news_by_date: '📅',
  get_news_detail: '🔍',
  find_similar_news: '🔗',
  list_factors: '📊',
  get_news_by_factor: '🏷️',
  compute_macro_signal: '⚡',
  get_yield_curve: '📈',
}
