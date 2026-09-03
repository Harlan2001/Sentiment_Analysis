import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import Modal from '@/components/ui/Modal'
import { activateSkill, archiveSkill, createSkill, deleteSkill, deleteSkillAttachment, getSkills, Skill, SkillAttachment, SkillPayload, updateSkill, uploadSkillAttachment } from '@/api/skills'
import './skills-interactions.css'

const EMPTY: SkillPayload = { name: '', description: '', instructions: '', input_schema: [], output_format: 'markdown', status: 'draft' }
const PAGE_SIZE = 9
const MINE_PAGE_SIZE = PAGE_SIZE - 1
const SYSTEM = [
  { name: '我的关注债池晨报', description: '围绕我的关注主体整理隔夜要闻、估值变化和风险信号。', tag: '每日投研' },
  { name: '我的持仓风险复盘', description: '归纳持仓风险暴露、归因与下一步核查清单。', tag: '持仓管理' },
  { name: '宏观政策速读', description: '提炼政策表述、传导路径与可能受影响的资产。', tag: '宏观研究' },
  { name: '行业景气跟踪', description: '整理高频数据、供需变化与行业景气拐点。', tag: '行业研究' },
  { name: '公司公告解读', description: '快速识别公告中的业绩、治理与经营变化。', tag: '公司研究' },
  { name: '财报要点提炼', description: '从财报中提炼核心指标、指引和超预期因素。', tag: '基本面' },
  { name: '估值分位比较', description: '对比标的历史估值区间与同业估值差异。', tag: '估值分析' },
  { name: '资金面日报', description: '汇总利率、流动性和机构资金行为的关键信号。', tag: '市场跟踪' },
  { name: '事件驱动扫描', description: '从新闻与公告中筛选可跟踪的催化事件。', tag: '事件研究' },
  { name: '产业链映射', description: '梳理上下游关系、关键环节和受益标的。', tag: '主题研究' },
  { name: '竞争格局分析', description: '评估行业集中度、竞争优势与潜在进入者。', tag: '行业研究' },
  { name: '盈利预测校验', description: '核对一致预期、盈利假设和业绩修正风险。', tag: '基本面' },
  { name: '风险事件预警', description: '按影响范围和紧急程度整理待处理风险事项。', tag: '风险管理' },
  { name: '组合归因分析', description: '拆解组合收益来源、风格暴露与个券贡献。', tag: '组合管理' },
  { name: '仓位调整建议', description: '结合风险预算和市场信号形成仓位调整依据。', tag: '组合管理' },
  { name: '信用债风险快筛', description: '从经营、偿债和舆情维度快速识别信用风险。', tag: '信用研究' },
  { name: '利率债久期判断', description: '综合政策、资金和期限利差给出久期观察框架。', tag: '固收研究' },
  { name: '海外市场晨报', description: '汇总海外股债汇、大宗商品与重要宏观事件。', tag: '全球市场' },
  { name: '商品供需追踪', description: '提炼库存、产量、需求和价格的边际变化。', tag: '商品研究' },
  { name: '技术信号复核', description: '复核趋势、成交与关键价位的技术面信号。', tag: '量化辅助' },
  { name: '主题研报摘要', description: '将多篇研报归纳为投资逻辑、分歧与风险。', tag: '研报分析' },
  { name: '会议纪要整理', description: '将调研与会议记录整理为结论、行动项和待验证问题。', tag: '研究协作' },
  { name: '投资备忘录', description: '按统一模板沉淀观点、依据、风险和后续跟踪项。', tag: '研究协作' },
  { name: '工作流复盘', description: '复盘研究任务的完成情况、阻塞环节与改进建议。', tag: '效率提升' },
]

export function SkillsPage() {
  const navigate = useNavigate()
  const attachmentInputRef = useRef<HTMLInputElement>(null)
  const [tab, setTab] = useState<'system' | 'mine'>('system')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [skills, setSkills] = useState<Skill[]>([])
  const [editing, setEditing] = useState<Skill | null>(null)
  const [form, setForm] = useState<SkillPayload>(EMPTY)
  const [files, setFiles] = useState<File[]>([])
  const [attachments, setAttachments] = useState<SkillAttachment[]>([])
  const [modal, setModal] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setBusy(true)
    try {
      setSkills((await getSkills(query, 'mine')).items)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '无法加载我的 Skills')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { void load() }, [tab])
  useEffect(() => { setPage(1) }, [tab, query])

  const systemVisible = useMemo(() => SYSTEM.filter(skill => `${skill.name}${skill.description}${skill.tag}`.toLowerCase().includes(query.toLowerCase())), [query])
  const mineVisible = useMemo(() => skills.filter(skill => `${skill.name}${skill.description}`.toLowerCase().includes(query.toLowerCase())), [skills, query])
  const pageSize = tab === 'system' ? PAGE_SIZE : MINE_PAGE_SIZE
  const currentItems = tab === 'system' ? systemVisible : mineVisible
  const pageCount = Math.max(1, Math.ceil(currentItems.length / pageSize))
  const safePage = Math.min(page, pageCount)
  const pageStart = (safePage - 1) * pageSize
  const systemPageItems = systemVisible.slice(pageStart, pageStart + PAGE_SIZE)
  const minePageItems = mineVisible.slice(pageStart, pageStart + MINE_PAGE_SIZE)
  const addedSystemSkills = useMemo(() => new Map(skills.filter(skill => skill.status !== 'archived').map(skill => [skill.name, skill])), [skills])

  async function addSystemSkill(item: typeof SYSTEM[number]) {
    if (addedSystemSkills.has(item.name)) return
    setBusy(true)
    try {
      await createSkill({
        name: item.name,
        description: item.description,
        instructions: `使用「${item.name}」处理与“${item.tag}”相关的问题。${item.description} 输出应说明关键依据、待验证事项和主要风险。`,
        input_schema: [],
        output_format: 'markdown',
        status: 'published',
      })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加 Skill 失败')
    } finally {
      setBusy(false)
    }
  }

  async function removeSystemSkill(skill: Skill) {
    setBusy(true)
    try {
      if (skill.status !== 'archived') await archiveSkill(skill.id)
      await deleteSkill(skill.id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '移除 Skill 失败')
    } finally {
      setBusy(false)
    }
  }

  function openEditor(skill?: Skill) {
    setEditing(skill ?? null)
    setForm(skill ? { name: skill.name, description: skill.description, instructions: skill.instructions, input_schema: skill.input_schema_json, output_format: skill.output_format, status: skill.status === 'archived' ? 'draft' : skill.status } : EMPTY)
    setAttachments(skill?.attachments ?? [])
    setFiles([])
    setModal(true)
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      const item = editing ? await updateSkill(editing.id, form) : await createSkill(form)
      for (const file of files) await uploadSkillAttachment(item.id, file)
      setModal(false)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setBusy(false)
    }
  }

  async function action(skill: Skill, kind: 'archive' | 'activate' | 'delete') {
    if (kind === 'delete' && !window.confirm(`永久删除「${skill.name}」吗？`)) return
    setBusy(true)
    try {
      if (kind === 'archive') await archiveSkill(skill.id)
      if (kind === 'activate') await activateSkill(skill.id)
      if (kind === 'delete') await deleteSkill(skill.id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败')
    } finally {
      setBusy(false)
    }
  }

  function selectFiles(event: ChangeEvent<HTMLInputElement>) {
    setFiles(old => [...old, ...Array.from(event.target.files ?? [])].slice(0, 8))
    event.target.value = ''
  }

  async function removeAttachment(id: string) {
    if (!editing) return
    await deleteSkillAttachment(editing.id, id)
    setAttachments(old => old.filter(item => item.id !== id))
  }

  const card = (name: string, description: string, meta: string, stateLabel: string, active: boolean, footer: ReactNode) => (
    <article className="skill-card" key={name}>
      <span className={'skill-state ' + (active ? 'on' : '')}>{stateLabel}</span>
      <div className="skill-card-body"><small>{meta}</small><h2>{name}</h2><p>{description}</p></div>
      <footer>{footer}</footer>
    </article>
  )

  return <section className="custom-page skills-page">
    <div className="custom-tabs"><button onClick={() => navigate('/custom/mcp')}>MCP</button><button className="active">Skills</button><button onClick={() => navigate('/custom/memory')}>记忆</button></div>
    <header className="skills-head"><div><h1>Skills</h1><p>将我的投研习惯沉淀为可复用的能力。</p></div><div className="skills-actions"><label><span>⌕</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索 Skill" /></label></div></header>
    <div className="skills-filter-tabs">{([['system', '系统'], ['mine', '我的']] as const).map(([key, label]) => <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{label}</button>)}</div>
    {error && <p className="mcp-error">{error}</p>}
    {tab === 'system' ? <div className="skills-grid compact-grid">
      {systemPageItems.map(item => {
        const added = addedSystemSkills.get(item.name)
        return card(item.name, item.description, item.tag, added ? '● 已添加' : '○ 未添加', Boolean(added), <><span>系统 Skill</span><button disabled={busy} onClick={() => void (added ? removeSystemSkill(added) : addSystemSkill(item))}>{added ? '移除' : '添加'}</button></>)
      })}
    </div> : <div className="skills-grid compact-grid">
      <button className="skill-create-card" onClick={() => openEditor()}><span>＋</span><strong>新建我的 Skill</strong><small>添加指令、附件与示例文件</small></button>
      {minePageItems.map(item => card(item.name, item.description, `${item.status === 'published' ? '已发布' : item.status === 'archived' ? '已停用' : '草稿'} · v${item.version_no}`, item.status === 'published' ? '● 已发布' : item.status === 'archived' ? '○ 已停用' : '○ 草稿', item.status === 'published', <><span>我的 Skill</span><span><button onClick={() => openEditor(item)}>编辑</button>{item.status === 'archived' ? <><button onClick={() => void action(item, 'activate')}>启用</button><button className="danger" onClick={() => void action(item, 'delete')}>删除</button></> : <button onClick={() => void action(item, 'archive')}>停用</button>}</span></>))}
    </div>}
    {pageCount > 1 && <nav className="skills-pagination" aria-label="Skills 分页"><button disabled={safePage === 1} onClick={() => setPage(safePage - 1)}>上一页</button>{Array.from({ length: pageCount }, (_, index) => <button key={index + 1} className={safePage === index + 1 ? 'active' : ''} onClick={() => setPage(index + 1)}>{index + 1}</button>)}<button disabled={safePage === pageCount} onClick={() => setPage(safePage + 1)}>下一页</button></nav>}
    <Modal isOpen={modal} onClose={() => setModal(false)} title={editing ? '编辑我的 Skill' : '新建我的 Skill'} size="lg" panelClassName="skill-editor-modal" contentClassName="skill-editor-content">
      <form className="skill-modal-form" onSubmit={save}>
        <p>上传的脚本仅作为 Skill 附件保存，不会在服务器执行。</p>
        <label>名称<input required value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} placeholder="例如：信用债风险快筛" /></label>
        <label>使用场景<textarea required rows={3} value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} placeholder="何时使用、需要什么输入、期待什么结果" /></label>
        <label>分析指令<textarea required rows={6} value={form.instructions} onChange={event => setForm({ ...form, instructions: event.target.value })} placeholder="分析步骤、约束和输出结构" /></label>
        <div className="skill-upload"><span>Skill 附件</span><input ref={attachmentInputRef} type="file" multiple accept=".pdf,.docx,.xlsx,.csv,.txt,.md,.py,.js,.sql,.sh" onChange={selectFiles} /><button type="button" onClick={() => attachmentInputRef.current?.click()}><b>＋</b><strong>添加附件</strong><small>文档、模板、示例数据或脚本</small></button></div>
        <small className="skill-file-help">支持 PDF、Office、CSV、Markdown 和常见脚本；单个文件最大 10 MB。</small>
        <ul className="skill-attachments">{attachments.map(attachment => <li key={attachment.id}>{attachment.original_filename}<button type="button" onClick={() => void removeAttachment(attachment.id)}>移除</button></li>)}{files.map((file, index) => <li key={file.name + index}>{file.name}<button type="button" onClick={() => setFiles(old => old.filter((_, itemIndex) => itemIndex !== index))}>移除</button></li>)}</ul>
        <label>保存状态<select value={form.status} onChange={event => setForm({ ...form, status: event.target.value as 'draft' | 'published' })}><option value="draft">保存为草稿</option><option value="published">发布后可使用</option></select></label>
        <div className="skills-form-actions"><button className="computer-button" type="button" onClick={() => setModal(false)}>取消</button><button className="computer-button primary" disabled={busy} type="submit">{busy ? '保存中…' : '保存 Skill'}</button></div>
      </form>
    </Modal>
  </section>
}
