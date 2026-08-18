/**
 * 中央路由配置 — 唯一权威来源
 *
 * 纯数据模块：不得 import 任何 React / react-router / feature 页面组件，
 * 否则会与 features 互相循环依赖。组件→元素映射只存在于 src/routes.tsx；
 * features / shell / 行为统计改从此处读取标题、导航、白名单等派生值。
 */

export type PageGroupId = '市场板块' | '首页' | '工作台' | '自定义' | '项目与对话' | '设置'

export interface RouteMeta {
  path: string
  title: string                                  // 权威标题（行为统计 + 顶栏回退）
  shellTitle?: string                            // 顶栏覆盖（如 'Computer · 研报生成'）
  dynamicTitle?: (ctx: { conversationTopic?: string }) => string // 仅 /chat/:conversationId
  brandTitle?: boolean                           // market tab + /home → 品牌标题
  group?: PageGroupId                            // 行为统计分组（track 行才有）
  tabLabel?: string                              // 工作台 tab 标签
  navLabel?: string                              // 侧边栏产品入口标签
  navIcon?: string
  redirect?: string
  track?: boolean                                // 是否计入 NEW_PAGE_ROUTES 白名单
  inShell?: boolean                              // 默认 true；false 表示 /login
}

export const BRAND_TITLE = '债券市场智能分析'

/** 路由表（静态路由必须声明在其同路径的动态路由之前，findRoute 取首个匹配） */
export const ROUTES: RouteMeta[] = [
  { path: '/', title: '市场', redirect: '/market' },

  // ── 工作台 7 个板块 tab ──
  { path: '/market', title: '市场', tabLabel: '市场', brandTitle: true, group: '市场板块', track: true },
  { path: '/factors', title: '因子', tabLabel: '因子', brandTitle: true, group: '市场板块', track: true },
  { path: '/returns', title: '收益', tabLabel: '收益', brandTitle: true, group: '市场板块', track: true },
  { path: '/forecast', title: '预测', tabLabel: '预测', brandTitle: true, group: '市场板块', track: true },
  { path: '/watchlist', title: '关注列表', tabLabel: '关注列表', brandTitle: true, group: '市场板块', track: true },
  { path: '/portfolio', title: '投资组合', tabLabel: '投资组合', brandTitle: true, group: '市场板块', track: true },
  { path: '/workflow', title: '工作流', tabLabel: '工作流', brandTitle: true, group: '市场板块', track: true },

  // ── 首页 ──
  { path: '/home', title: '首页', brandTitle: true, group: '首页', track: true },

  // ── 对话 ──
  { path: '/chat', title: '对话', group: '项目与对话', track: true },
  {
    path: '/chat/:conversationId',
    title: '对话',
    dynamicTitle: ({ conversationTopic }) => (conversationTopic ? `对话 · ${conversationTopic}` : '对话'),
  },
  { path: '/chat/new', title: '对话', redirect: '/chat' },

  // ── Computer ——
  { path: '/computer', title: 'Computer', shellTitle: 'Computer', navLabel: 'Computer', navIcon: '◉', group: '工作台', track: true },
  { path: '/computer/reports', title: '研报分析', shellTitle: 'Computer · 研报分析', group: '工作台', track: true },
  { path: '/computer/reports/library', title: '研报库', shellTitle: 'Computer · 研报库' },
  { path: '/computer/reports/:taskId', title: '研报分析', shellTitle: 'Computer · 研报分析' },
  { path: '/computer/strategies', title: '策略开发', shellTitle: 'Computer · 策略开发', group: '工作台', track: true },
  { path: '/computer/strategies/prompt', title: '策略开发', shellTitle: 'Computer · 策略开发' },
  { path: '/computer/news', title: '每日新闻总结', shellTitle: 'Computer · 每日新闻总结', group: '工作台', track: true },
  { path: '/computer/news/:taskId', title: '新闻总结详情', shellTitle: 'Computer · 新闻总结详情' },

  // ── 自定义 ──
  { path: '/custom', title: '自定义', shellTitle: '自定义', navLabel: '自定义', navIcon: '◌', group: '自定义', redirect: '/custom/mcp' },
  { path: '/custom/mcp', title: 'MCP连接', shellTitle: '自定义 · MCP 连接', group: '自定义', track: true },
  { path: '/custom/skills', title: 'Skills', shellTitle: '自定义 · Skills', group: '自定义', track: true },

  // ── 项目 ──
  { path: '/projects', title: '项目', shellTitle: '项目空间', group: '项目与对话', track: true },
  { path: '/projects/new', title: '项目 · 新建', shellTitle: '项目 · 新建', redirect: undefined },
  { path: '/projects/:projectId', title: '项目', shellTitle: '项目空间' },

  // ── 设置 ──
  { path: '/settings', title: '设置', shellTitle: '设置', group: '设置', track: true },

  // ── 登录（壳外） ──
  { path: '/login', title: '登录', inShell: false },
]

// ========== 路径匹配 ==========

function splitPath(p: string): string[] {
  return p.split('/').filter(Boolean)
}

/** pattern 中 `:param` 段按通配匹配；静态段必须相等 */
function pathMatches(pattern: string, pathname: string): boolean {
  const a = splitPath(pattern)
  const b = splitPath(pathname)
  if (a.length !== b.length) return false
  return a.every((seg, i) => seg.startsWith(':') || seg === b[i])
}

/** 精确/模式匹配优先（静态行先声明者胜），否则最长静态前缀回退 */
export function findRoute(pathname: string): RouteMeta | null {
  for (const r of ROUTES) {
    if (r.path === pathname || pathMatches(r.path, pathname)) return r
  }
  let best: RouteMeta | null = null
  for (const r of ROUTES) {
    if (r.path.indexOf(':') === -1 && (pathname === r.path || pathname.startsWith(r.path + '/'))) {
      if (!best || r.path.length > best.path.length) best = r
    }
  }
  return best
}

// ========== 派生导出 ==========

/** 新版页面白名单（行为统计筛选用） */
export const NEW_PAGE_ROUTES: string[] = ROUTES.filter((r) => r.track).map((r) => r.path)

/** 旭日图分组（顶层分类 → 页面路由列表） */
export const NEW_PAGE_GROUPS: Record<string, string[]> = ROUTES.filter((r) => r.track && r.group).reduce<
  Record<string, string[]>
>((acc, r) => {
  const g = r.group!
  ;(acc[g] ||= []).push(r.path)
  return acc
}, {})

/** 将原始路由归并到新版页面（最长前缀匹配），非新版页面返回 null */
export function matchNewPage(route: string): string | null {
  if (!route) return null
  let best: string | null = null
  for (const r of NEW_PAGE_ROUTES) {
    if (route === r || route.startsWith(r + '/')) {
      if (!best || r.length > best.length) best = r
    }
  }
  return best
}

/** 判断路由是否属于新版页面 */
export function isNewPage(route: string): boolean {
  return matchNewPage(route) !== null
}

/** 路由 → 中文页面标题（行为统计 / 审计日志用） */
export function routeTitle(pathname: string): string {
  return findRoute(pathname)?.title ?? pathname
}

/** 顶栏标题（替代 WorkbenchShell 原 resolveTitle），保留品牌回退与 `对话 · {topic}` */
export function shellTitle(pathname: string, conversationTopic?: string): string {
  const row = findRoute(pathname)
  if (row?.dynamicTitle) return row.dynamicTitle({ conversationTopic })
  if (row?.shellTitle) return row.shellTitle
  if (row?.brandTitle) return BRAND_TITLE
  return row?.title ?? BRAND_TITLE
}

/** 工作台板块 tab（替代 WorkbenchShell 原 SECTIONS） */
export const SECTION_TABS: { name: string; to: string }[] = ROUTES.filter((r) => r.tabLabel).map((r) => ({
  name: r.tabLabel!,
  to: r.path,
}))

/** 侧边栏产品入口（替代 WorkbenchShell 原 productLinks） */
export const PRODUCT_LINKS: { to: string; label: string; icon: string }[] = ROUTES.filter((r) => r.navLabel).map(
  (r) => ({ to: r.path, label: r.navLabel!, icon: r.navIcon ?? '' })
)

/** 工作台 tabs 可见的路径集合（tabs + 首页 + 根） */
export const HOME_PATHS: Set<string> = new Set(SECTION_TABS.map((t) => t.to).concat(['/home', '/']))
