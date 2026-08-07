import { FormEvent, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const rows = [
  { id: 'today', icon: '✓', tone: 'done', title: '8 月 6 日每日债券新闻总结', description: '汇总 86 条新闻，识别 12 个重要事件', source: '自动计划', result: '新闻总结_0806.md', updated: '09:02' },
  { id: 'yesterday', icon: '✓', tone: 'done', title: '8 月 5 日每日债券新闻总结', description: '汇总 74 条新闻，识别 9 个重要事件', source: '自动计划', result: '新闻总结_0805.md', updated: '昨天' },
  { id: 'credit', icon: '✓', tone: 'done', title: '信用债风险新闻专题总结', description: '汇总 31 条新闻，识别 5 个主体风险', source: '手动生成', result: '信用风险专题.md', updated: '昨天' },
  { id: 'failed', icon: '!', tone: 'failed', title: '8 月 4 日每日债券新闻总结', description: '一个新闻源连接失败，可以单独重试', source: '自动计划', result: '执行失败 · 可重试', updated: '8 月 4 日' },
]

export function NewsPage() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const [request, setRequest] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [unreadOnly, setUnreadOnly] = useState(false)

  function createSummary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!request.trim()) return
    setSubmitted(true)
    setRequest('')
  }

  return (
    <section className="computer-page">
      <div className="computer-tabs">
        <button onClick={() => navigate('/computer')}>全部</button>
        <button onClick={() => navigate('/computer/reports')}>研报生成</button>
        <button onClick={() => navigate('/computer/strategies')}>策略开发</button>
        <button className="active">每日新闻总结</button>
        <span className="computer-spacer" />
        <button className="computer-button">计划管理</button>
        <button className="computer-button primary" onClick={() => inputRef.current?.focus()}>＋ 立即生成</button>
      </div>

      <div className="computer-toolbar">
        <button className="computer-chip dropdown-chip">状态：全部<i className="inline-caret" aria-hidden="true" /></button>
        <button className="computer-chip dropdown-chip">执行方式：全部<i className="inline-caret" aria-hidden="true" /></button>
        <button className={'computer-chip ' + (unreadOnly ? 'selected' : '')} onClick={() => setUnreadOnly((value) => !value)}>仅未读</button>
        <span className="computer-badge file">计划已启用 · 每日 08:30</span>
        <button className="computer-chip">▣ 2026-08-06</button>
        <button className="computer-chip">已归档</button>
        <span className="computer-spacer" />
        <span className="computer-count">{unreadOnly ? '1 段总结会话' : '4 段总结会话'}</span>
      </div>

      <section className="computer-attention">
        <div className="computer-attention-head"><strong>需要处理 · 1</strong><span>⌃</span></div>
        <div className="computer-attention-row">
          <span className="attention-dot" />
          <div><strong>每日新闻总结计划</strong><small>每天 08:30 自动运行，下次执行：2026-08-07</small></div>
          <span className="computer-badge file">已启用</span>
          <button className="computer-button primary">查看计划</button>
          <time>10:20</time>
        </div>
      </section>

      <div className="computer-list-head">
        <div><strong>2026 年 8 月 6 日</strong><span>· {unreadOnly ? 1 : 4} 段总结会话</span></div>
        <div className="computer-view-switch"><button className="active">会话与文档</button><button>仅会话</button><button>仅文档</button></div>
      </div>

      <div className="computer-table-wrap">
        <table className="computer-table">
          <thead><tr><th /><th>任务会话</th><th>来源/类型</th><th>状态或结果</th><th>更新时间</th></tr></thead>
          <tbody>{rows.filter((row) => !unreadOnly || row.id === 'today').map((row) => (
            <tr key={row.id}>
              <td><span className={'computer-status ' + row.tone}>{row.icon}</span></td>
              <td><strong>{row.title}</strong><small>{row.description}</small></td>
              <td>{row.source}</td>
              <td><span className={'computer-badge ' + (row.tone === 'failed' ? 'failure' : 'file')}>{row.result}</span></td>
              <td><time>{row.updated}</time></td>
            </tr>
          ))}</tbody>
        </table>
      </div>

      <form className="report-composer" ref={formRef} onSubmit={createSummary}>
        <textarea ref={inputRef} value={request} onChange={(event) => { setRequest(event.target.value); setSubmitted(false) }} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); formRef.current?.requestSubmit() } }} placeholder="补充今日新闻总结的关注主题或排除来源…" rows={2} />
        <div><button type="button" className="computer-button">＋ 添加文件</button><span className="computer-badge">◌ 每日新闻总结</span><button className="report-send" type="submit" aria-label="生成新闻总结">↑</button></div>
        {submitted && <p>已创建 Mock 新闻总结任务，后续将接入真实新闻源。</p>}
      </form>
    </section>
  )
}