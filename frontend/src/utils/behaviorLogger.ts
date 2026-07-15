/**
 * 用户行为日志缓冲队列
 */
import type { PageVisitEvent } from '../types';
import { API_PREFIX } from '../constants';

const BATCH_URL = `${API_PREFIX}/dashboard/behavior/batch`;

const MAX_BUFFER = 50;
const FLUSH_MS = 10_000;

let buffer: PageVisitEvent[] = [];
let timer: ReturnType<typeof setInterval> | null = null;

async function doFlush(): Promise<void> {
  if (buffer.length === 0) return;
  const batch = [...buffer];
  buffer = [];

  try {
    const token = readToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const r = await fetch(BATCH_URL, {
      method: 'POST',
      headers,
      body: JSON.stringify({ events: batch }),
      keepalive: true,
    });

    const resp = await r.json();
    if (!r.ok || resp.received === 0) {
      console.warn('[behavior] 上报异常', r.status, resp);
    } else {
      console.log(`[behavior] 上报 ${resp.received} 条事件`);
    }
  } catch (e) {
    console.error('[behavior] 上报失败', e);
  }
}

function readToken(): string | null {
  try {
    const raw = localStorage.getItem('auth_token');
    if (!raw) return null;
    const token = JSON.parse(raw);
    return token || null;
  } catch {
    return null;
  }
}

function ensureTimer(): void {
  if (timer !== null) return;
  console.log('[behavior] 启动 10s 定时器');
  timer = setInterval(doFlush, FLUSH_MS);
}

export function logPageVisit(event: PageVisitEvent): void {
  if (event.duration_sec !== undefined && event.duration_sec < 2) return;
  if (!event.action_type && event.page_route) event.action_type = 'page_enter';
  buffer.push(event);
  console.log(`[behavior] 记录: ${event.page_route} ${event.action_type || ''} (${event.duration_sec ?? '?'}s), 缓冲 ${buffer.length} 条`);
  if (buffer.length >= MAX_BUFFER) doFlush();
  ensureTimer();
}

/**
 * 记录用户操作行为（非页面切换）
 * 用于跟踪点击、搜索、下载等交互
 */
export function logAction(
  actionType: string,
  pageRoute: string,
  actionTarget?: string,
  actionDetail?: Record<string, unknown>,
): void {
  const now = new Date();
  const event: PageVisitEvent = {
    page_route: pageRoute,
    enter_time: mysqlTime(now),
    action_type: actionType,
    action_target: actionTarget,
    action_detail: actionDetail,
    client_ts: mysqlTime(now),
  };
  buffer.push(event);
  console.log(`[behavior] 操作: ${actionType} → ${actionTarget || ''}, 缓冲 ${buffer.length} 条`);
  if (buffer.length >= MAX_BUFFER) doFlush();
  ensureTimer();
}

/** JS Date → MySQL DATETIME(3) 格式 */
function mysqlTime(d: Date): string {
  const pad = (n: number, len = 2) => String(n).padStart(len, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`;
}

export function initBehaviorLogger(): void {
  ensureTimer();
  window.addEventListener('beforeunload', () => {
    if (buffer.length === 0) return;
    const body = JSON.stringify({ events: buffer });
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const token = readToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    try {
      fetch(BATCH_URL, { method: 'POST', headers, body, keepalive: true });
    } catch { /* ignore */ }
    buffer = [];
  });
}
