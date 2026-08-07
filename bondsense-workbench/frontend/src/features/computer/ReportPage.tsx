import { FormEvent, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const rows = [
  { id: 'daily', icon: '◐', tone: 'running', title: '8 月 6 日债券市场日报', description: '正在生成收益率曲线与市场观点', source: '研报生成', result: '运行中 · 68%', updated: '11:06', progress: true },
  { id: 'spread', icon: '✓', tone: 'done', title: '信用债利差跟踪周报', description: '报告及数据附件已经生成', source: '研报生成', result: '信用利差周报.pdf', updated: '08:46', progress: false },
  { id: 'macro', icon: '✓', tone: 'done', title: '7 月宏观数据与债市影响', description: '已生成报告、图表及数据引用', source: '研报生成', result: '宏观解读.pdf · +1', updated: '昨天', progress: false },
  { id: 'allocation', icon: '✓', tone: 'done', title: '二季度机构配置行为复盘', description: '已归入国债策略研究项目', source: '研报生成', result: '配置行为复盘.docx', updated: '8 月 4 日', progress: false },
]

export function ReportPage() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const [request, setRequest] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [unreadOnly, setUnreadOnly] = useState(false)

  function createReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!request.trim()) return
    setSubmitted(true)
    setRequest('')
  }

  return (
    <section className="computer-page">
      <div className="computer-tabs">
        <button onClick={() => navigate('/computer')}>全部</button>
        <button className="active">研报生成</button>
        <button onClick={() => navigate('/computer/strategies')}>策略开发</button>
        <button onClick={() => navigate('/computer/news')}>每日新闻总结</button>
        <span className="computer-spacer" />
        <button className="computer-button primary" onClick={() => inputRef.current?.focus()}>＋ 新建研报</button>
      </div>

      <div className="computer-toolbar">
        <button className="computer-chip dropdown-chip">状态：全部<i className="inline-caret" aria-hidden="true" /></button>
        <button className="computer-chip dropdown-chip">报告类型：全部<i className="inline-caret" aria-hidden="true" /></button>
        <button className={'computer-chip ' + (unreadOnly ? 'selected' : '')} onClick={() => setUnreadOnly((value) => !value)}>仅未读</button>
        <button className="computer-chip">▣ 2026-08-06</button>
        <button className="computer-chip">已归档</button>
        <span className="computer-spacer" />
        <span className="computer-count">{unreadOnly ? '1 段会话' : '4 段研报会话'}</span>
      </div>

      <section className="computer-attention">
        <div className="computer-attention-head"><strong>需要处理 · 1</strong><span>⌃</span></div>
        <div className="computer-attention-row">
          <span className="attention-dot" />
          <div><strong>8 月 6 日债券市场日报</strong><small>部分行情数据待确认，确认后继续生成</small></div>
          <span className="computer-badge warning">缺少输入</span>
          <button className="computer-button primary" onClick={() => inputRef.current?.focus()}>补充数据</button>
          <time>10:20</time>
        </div>
      </section>

      <div className="computer-list-head">
        <div><strong>2026 年 8 月 6 日</strong><span>· {unreadOnly ? 1 : 4} 段研报会话</span></div>
        <div className="computer-view-switch"><button className="active">会话与文档</button><button>仅会话</button><button>仅文档</button></div>
      </div>

      <div className="computer-table-wrap">
        <table className="computer-table">
          <thead><tr><th /><th>任务会话</th><th>来源/类型</th><th>状态或结果</th><th>更新时间</th></tr></thead>
          <tbody>{rows.filter((row) => !unreadOnly || row.id === 'daily').map((row) => (
            <tr key={row.id}>
              <td><span className={'computer-status ' + row.tone}>{row.icon}</span></td>
              <td><strong>{row.title}</strong><small>{row.description}</small>{row.progress && <span className="computer-progress"><i /></span>}</td>
              <td>{row.source}</td>
              <td><span className={'computer-badge ' + (row.progress ? 'running' : 'file')}>{row.result}</span></td>
              <td><time>{row.updated}</time></td>
            </tr>
          ))}</tbody>
        </table>
      </div>

      <form className="report-composer" ref={formRef} onSubmit={createReport}>
        <textarea ref={inputRef} value={request} onChange={(event) => { setRequest(event.target.value); setSubmitted(false) }} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); formRef.current?.requestSubmit() } }} placeholder="输入研报主题、业务日期和分析范围…" rows={2} />
        <div><button type="button" className="computer-button">＋ 添加文件</button><span className="computer-badge">▤ 研报生成</span><button className="report-send" type="submit" aria-label="创建研报">↑</button></div>
        {submitted && <p>已创建 Mock 研报任务，后续将接入真实生成流程。</p>}
      </form>
    </section>
  )
}