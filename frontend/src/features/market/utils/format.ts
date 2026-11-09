/**
 * market 板块共享格式化工具
 */

/**
 * 相对时间：刚刚 / N小时前 / N天前。
 * 后端时间格式为 'YYYY-MM-DD HH:mm:ss'，补 T 以兼容各浏览器 Date 解析。
 */
export function fmtTime(t: string | null | undefined): string {
  if (!t) return ''
  const ts = new Date(t.includes('T') ? t : t.replace(' ', 'T')).getTime()
  if (Number.isNaN(ts)) return ''
  const diff = Date.now() - ts
  if (diff < 0) return '刚刚'
  const days = Math.floor(diff / 864e5)
  if (days > 0) return `${days}天前`
  const hours = Math.floor(diff / 36e5)
  return hours > 0 ? `${hours}小时前` : '刚刚'
}
