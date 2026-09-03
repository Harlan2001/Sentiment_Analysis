import { request } from './client'

export type WatchlistObjectType = 'news' | 'factor' | 'macro_signal'

export type WatchlistItem = {
  id: string
  object_type: WatchlistObjectType
  object_id: string
  title: string
  source_url: string | null
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export function getWatchlistItems() {
  return request<{ items: WatchlistItem[] }>('/sapi/watchlist')
}

export function addWatchlistItem(input: {
  object_type: WatchlistObjectType
  object_id: string
  title: string
  source_url?: string
  metadata?: Record<string, unknown>
}) {
  return request<WatchlistItem>('/sapi/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function removeWatchlistItem(itemId: string) {
  return request<{ deleted: boolean }>(`/sapi/watchlist/${itemId}`, { method: 'DELETE' })
}