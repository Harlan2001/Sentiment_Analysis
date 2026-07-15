/**
 * 页面路由 → 中文标题映射（前后端共享）
 */
const PAGE_TITLE_MAP: Record<string, string> = {
  '/news': '新闻', '/factors': '因子', '/data': '数据',
  '/prediction': '预测', '/agents': 'Agent', '/select-strategy': 'AI推荐',
  '/strategies': '策略', '/change': '变动对比', '/macro-signal-logs': '信号日志',
  '/dashboard': '看板', '/login': '登录',
};

export function pageTitle(route: string): string {
  if (route === '/' || route.startsWith('/news')) return '新闻';
  if (PAGE_TITLE_MAP[route]) return PAGE_TITLE_MAP[route];
  for (const [prefix, title] of Object.entries(PAGE_TITLE_MAP)) {
    if (route.startsWith(prefix)) return title;
  }
  return route;
}
