/**
 * 全局用户行为追踪 Hook
 * - 路由变化 → page_enter / page_leave
 * - data-track 点击 → 对应的操作行为（news_click, report_view 等）
 * - 空闲超时检测
 */
import { useEffect, useRef, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { logPageVisit, logAction, initBehaviorLogger } from '@/utils/behaviorLogger'
import { pageTitle as getPageTitle } from '@/utils/pageTitle'

const IDLE_TIMEOUT_MS = 5 * 60 * 1000

/** JS Date → MySQL DATETIME(3) 格式 */
function mysqlTime(d: Date): string {
  const pad = (n: number, len = 2) => String(n).padStart(len, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`
}

/**
 * 从元素及其祖先中查找 data-track 属性
 * 返回 { actionType, actionTarget, actionDetail } 或 null
 */
function resolveTrackData(el: HTMLElement | null): {
  actionType: string
  actionTarget?: string
  actionDetail?: Record<string, unknown>
} | null {
  let current: HTMLElement | null = el
  while (current) {
    const track = current.getAttribute('data-track')
    if (track) {
      const target = current.getAttribute('data-target') || undefined
      let detail: Record<string, unknown> | undefined
      const detailStr = current.getAttribute('data-detail')
      if (detailStr) {
        try {
          detail = JSON.parse(detailStr)
        } catch {
          detail = { raw: detailStr }
        }
      }
      // 自动采集元素文本作为补充信息
      if (!detail) {
        const text = (current.textContent || '').trim().slice(0, 80)
        if (text) detail = { label: text }
      }
      return { actionType: track, actionTarget: target, actionDetail: detail }
    }
    current = current.parentElement
  }
  return null
}

export function useBehaviorTracker() {
  const location = useLocation()
  const currentPageRef = useRef<{ route: string; enterTime: string } | null>(null)
  const idleTimerRef = useRef<number | null>(null)
  const initializedRef = useRef(false)

  useEffect(() => {
    if (!initializedRef.current) {
      initBehaviorLogger()
      initializedRef.current = true
    }
  }, [])

  // 空闲检测
  const resetIdleTimer = useCallback(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
    idleTimerRef.current = window.setTimeout(() => {
      if (currentPageRef.current) {
        const leave = new Date()
        const enterMs = new Date(currentPageRef.current.enterTime).getTime()
        logPageVisit({
          page_route: currentPageRef.current.route,
          page_title: getPageTitle(currentPageRef.current.route),
          enter_time: currentPageRef.current.enterTime,
          leave_time: mysqlTime(leave),
          duration_sec: Math.round((leave.getTime() - enterMs) / 1000),
          exit_type: 'idle_timeout',
          action_type: 'page_leave',
        })
        currentPageRef.current = null
      }
    }, IDLE_TIMEOUT_MS)
  }, [])

  useEffect(() => {
    const events = ['mousemove', 'keydown', 'scroll', 'click', 'touchstart']
    const handler = () => resetIdleTimer()
    events.forEach((e) => window.addEventListener(e, handler, { passive: true }))
    resetIdleTimer()
    return () => {
      events.forEach((e) => window.removeEventListener(e, handler))
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
    }
  }, [resetIdleTimer])

  // data-track 点击委托 — 捕获所有点击，自动上报操作行为
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      const track = resolveTrackData(target)
      if (track) {
        logAction(track.actionType, location.pathname, track.actionTarget, track.actionDetail)
      }
    }
    document.addEventListener('click', handleClick, { passive: true })
    return () => document.removeEventListener('click', handleClick)
  }, [location.pathname])

  // data-track change 委托 — 捕获 select/input 变化事件
  useEffect(() => {
    const handleChange = (e: Event) => {
      const target = e.target as HTMLElement
      const track = resolveTrackData(target)
      if (!track) return
      // 对 select/input 获取当前值作为 target
      let targetValue = track.actionTarget
      if (!targetValue && (target instanceof HTMLSelectElement || target instanceof HTMLInputElement)) {
        targetValue = target.value || undefined
      }
      logAction(track.actionType, location.pathname, targetValue, track.actionDetail)
    }
    document.addEventListener('change', handleChange, { passive: true })
    return () => document.removeEventListener('change', handleChange)
  }, [location.pathname])

  // 路由变化
  useEffect(() => {
    const newRoute = location.pathname
    const now = new Date()

    if (currentPageRef.current && currentPageRef.current.route !== newRoute) {
      const enterMs = new Date(currentPageRef.current.enterTime).getTime()
      logPageVisit({
        page_route: currentPageRef.current.route,
        page_title: getPageTitle(currentPageRef.current.route),
        enter_time: currentPageRef.current.enterTime,
        leave_time: mysqlTime(now),
        duration_sec: Math.round((now.getTime() - enterMs) / 1000),
        exit_type: 'navigation',
        action_type: 'page_leave',
      })
    }

    // 新页面 enter
    if (!currentPageRef.current || currentPageRef.current.route !== newRoute) {
      currentPageRef.current = { route: newRoute, enterTime: mysqlTime(now) }
    }
  }, [location.pathname])
}
