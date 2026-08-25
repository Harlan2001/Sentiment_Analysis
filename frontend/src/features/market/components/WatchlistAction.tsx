import { type MouseEvent, useEffect, useState } from 'react'
import { addWatchlistItem, getWatchlistItems, type WatchlistObjectType } from '@/api/workbench'

type Props = {
  objectType: WatchlistObjectType
  objectId: string
  title: string
  sourceUrl?: string
  className?: string
}

export function WatchlistAction({ objectType, objectId, title, sourceUrl, className = '' }: Props) {
  const [state, setState] = useState<'loading' | 'idle' | 'saved' | 'failed'>('loading')

  useEffect(() => {
    let active = true
    const refresh = async () => {
      try {
        const { items } = await getWatchlistItems()
        if (active) setState(items.some((item) => item.object_type === objectType && item.object_id === objectId) ? 'saved' : 'idle')
      } catch { if (active) setState('failed') }
    }
    void refresh()
    window.addEventListener('bondsense-watchlist-changed', refresh)
    return () => { active = false; window.removeEventListener('bondsense-watchlist-changed', refresh) }
  }, [objectId, objectType])

  const follow = async (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault()
    event.stopPropagation()
    try {
      await addWatchlistItem({ object_type: objectType, object_id: objectId, title, source_url: sourceUrl })
      setState('saved')
      window.dispatchEvent(new Event('bondsense-watchlist-changed'))
    } catch { setState('failed') }
  }

  if (state === 'saved') return <span className={`rounded border border-[#56705b] px-1.5 py-0.5 text-[10px] text-[#b9d9bf] ${className}`}>已关注</span>
  return <button type="button" onClick={follow} className={`rounded border border-[#56705b] px-1.5 py-0.5 text-[10px] text-[#b9d9bf] hover:bg-[#1c3020] ${className}`}>{state === 'failed' ? '重试关注' : '+ 关注'}</button>
}
