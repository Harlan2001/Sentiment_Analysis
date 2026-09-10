import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import Modal from '@/components/ui/Modal'
import { activateSkill, archiveSkill, createSkill, deleteSkill, deleteSkillAttachment, disableSystemSkill, enableSystemSkill, getSkill, getSkills, Skill, SkillAttachment, SkillPayload, updateSkill, uploadSkillAttachment } from '@/api/skills'
import './skills-interactions.css'

const EMPTY: SkillPayload = { name: '', description: '', instructions: '', input_schema: [], output_format: 'markdown', status: 'draft' }
const PAGE_SIZE = 9
const MINE_PAGE_SIZE = PAGE_SIZE - 1
const MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
const ALLOWED_ATTACHMENT_EXTENSIONS = ['.pdf', '.docx', '.xlsx', '.csv', '.txt', '.md', '.py', '.js', '.sql', '.sh']
export function SkillsPage() {
  const navigate = useNavigate()
  const attachmentInputRef = useRef<HTMLInputElement>(null)
  const [tab, setTab] = useState<'system' | 'mine'>('system')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [skills, setSkills] = useState<Skill[]>([])
  const [systemSkills, setSystemSkills] = useState<Skill[]>([])
  const [systemDetail, setSystemDetail] = useState<Skill | null>(null)
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
      const [mine, system] = await Promise.all([getSkills('', 'mine'), getSkills('', 'system')])
      setSkills(mine.items)
      setSystemSkills(system.items)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '无法加载我的 Skills')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { void load() }, [tab])
  useEffect(() => { setPage(1) }, [tab, query])

  const systemVisible = useMemo(() => systemSkills.filter(skill => `${skill.name}${skill.description}`.toLowerCase().includes(query.toLowerCase())), [query, systemSkills])
  const mineVisible = useMemo(() => skills.filter(skill => `${skill.name}${skill.description}`.toLowerCase().includes(query.toLowerCase())), [skills, query])
  const pageSize = tab === 'system' ? PAGE_SIZE : MINE_PAGE_SIZE
  const currentItems = tab === 'system' ? systemVisible : mineVisible
  const pageCount = Math.max(1, Math.ceil(currentItems.length / pageSize))
  const safePage = Math.min(page, pageCount)
  const pageStart = (safePage - 1) * pageSize
  const systemPageItems = systemVisible.slice(pageStart, pageStart + PAGE_SIZE)
  const minePageItems = mineVisible.slice(pageStart, pageStart + MINE_PAGE_SIZE)
  async function openEditor(skill?: Skill) {
    if (!skill) {
      setEditing(null)
      setForm(EMPTY)
      setAttachments([])
      setFiles([])
      setModal(true)
      return
    }
    setBusy(true)
    try {
      const detail = await getSkill(skill.id)
      setEditing(detail)
      setForm({ name: detail.name, description: detail.description, instructions: detail.instructions, input_schema: detail.input_schema_json, output_format: detail.output_format, status: detail.status === 'archived' ? 'draft' : detail.status })
      setAttachments(detail.attachments ?? [])
      setFiles([])
      setModal(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : '无法加载 Skill 详情')
    } finally {
      setBusy(false)
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      const item = editing ? await updateSkill(editing.id, form) : await createSkill(form)
      if (!editing) setEditing(item)
      for (const file of files) {
        try {
          const uploaded = await uploadSkillAttachment(item.id, file)
          setAttachments(old => [...old, uploaded])
          setFiles(old => old.filter(candidate => candidate !== file))
        } catch (uploadError) {
          throw new Error(`Skill 已保存，但附件「${file.name}」上传失败：${uploadError instanceof Error ? uploadError.message : '未知错误'}`)
        }
      }
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
    const selected = Array.from(event.target.files ?? [])
    const invalidType = selected.find(file => !ALLOWED_ATTACHMENT_EXTENSIONS.some(extension => file.name.toLowerCase().endsWith(extension)))
    const invalidSize = selected.find(file => file.size < 1 || file.size > MAX_ATTACHMENT_SIZE)
    if (invalidType) {
      setError(`附件「${invalidType.name}」类型不支持。`)
      event.target.value = ''
      return
    }
    if (invalidSize) {
      setError(`附件「${invalidSize.name}」必须在 1 字节至 10 MB 之间。`)
      event.target.value = ''
      return
    }
    const remaining = Math.max(0, 8 - attachments.length - files.length)
    if (selected.length > remaining) setError(`每个 Skill 最多 8 个附件，当前还可以添加 ${remaining} 个。`)
    else setError(null)
    setFiles(old => [...old, ...selected.slice(0, remaining)])
    event.target.value = ''
  }

  async function openSystemDetail(skill: Skill) {
    setBusy(true)
    try {
      const detail = await getSkill(skill.id)
      setSystemDetail({ ...detail, is_enabled: skill.is_enabled })
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '无法加载系统 Skill 详情')
    } finally {
      setBusy(false)
    }
  }

  async function toggleSystemSkill(skill: Skill) {
    setBusy(true)
    try {
      if (skill.is_enabled) await disableSystemSkill(skill.id)
      else await enableSystemSkill(skill.id)
      await load()
      setSystemDetail(current => current?.id === skill.id ? { ...current, is_enabled: !skill.is_enabled } : current)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '系统 Skill 状态更新失败')
    } finally {
      setBusy(false)
    }
  }

  async function removeAttachment(id: string) {
    if (!editing) return
    setBusy(true)
    try {
      await deleteSkillAttachment(editing.id, id)
      setAttachments(old => old.filter(item => item.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除附件失败')
    } finally {
      setBusy(false)
    }
  }

  function attachmentStatus(attachment: SkillAttachment) {
    if (attachment.parse_status === 'ready') return attachment.page_count ? `已解析 · ${attachment.page_count} 页` : '已解析'
    if (attachment.parse_status === 'failed') return `解析失败：${attachment.parse_error || '未提取到可用内容'}`
    if (attachment.parse_status === 'parsing') return '解析中'
    if (attachment.parse_status === 'pending') return '等待解析'
    return '仅已保存'
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
        return card(item.name, item.description, '平台维护 · 可按账号启用', item.is_enabled ? '● 已启用' : '○ 未启用', Boolean(item.is_enabled), <><span>系统 Skill</span><span><button disabled={busy} onClick={() => void openSystemDetail(item)}>查看详情</button><button disabled={busy} onClick={() => void toggleSystemSkill(item)}>{item.is_enabled ? '停用' : '启用'}</button></span></>)
      })}
    </div> : <div className="skills-grid compact-grid">
      <button className="skill-create-card" onClick={() => void openEditor()}><span>＋</span><strong>新建我的 Skill</strong><small>添加指令、附件与示例文件</small></button>
      {minePageItems.map(item => card(item.name, item.description, `${item.status === 'published' ? '已启用' : item.status === 'archived' ? '已停用' : '未启用'} · v${item.version_no}`, item.status === 'published' ? '● 已启用' : item.status === 'archived' ? '○ 已停用' : '○ 未启用', item.status === 'published', <><span>我的 Skill</span><span><button onClick={() => void openEditor(item)}>编辑</button>{item.status === 'published' ? <button onClick={() => void action(item, 'archive')}>停用</button> : <><button onClick={() => void action(item, 'activate')}>启用</button>{item.status === 'archived' && <button className="danger" onClick={() => void action(item, 'delete')}>删除</button>}</>}</span></>))}
    </div>}
    {pageCount > 1 && <nav className="skills-pagination" aria-label="Skills 分页"><button disabled={safePage === 1} onClick={() => setPage(safePage - 1)}>上一页</button>{Array.from({ length: pageCount }, (_, index) => <button key={index + 1} className={safePage === index + 1 ? 'active' : ''} onClick={() => setPage(index + 1)}>{index + 1}</button>)}<button disabled={safePage === pageCount} onClick={() => setPage(safePage + 1)}>下一页</button></nav>}
    <Modal isOpen={Boolean(systemDetail)} onClose={() => setSystemDetail(null)} title={systemDetail ? `系统 Skill：${systemDetail.name}` : '系统 Skill 详情'} size="lg" panelClassName="skill-editor-modal" contentClassName="skill-editor-content">
      {systemDetail && <article className="skill-system-detail">
        <div className="skill-system-detail-meta"><span>{systemDetail.is_enabled ? '● 当前账号已启用' : '○ 当前账号未启用'}</span><span>系统维护 · 内容只读</span><span>v{systemDetail.version_no}</span></div>
        <section><h3>使用场景</h3><p>{systemDetail.description}</p></section>
        <section><h3>完整指令</h3><pre>{systemDetail.instructions}</pre></section>
        <section><h3>输出格式</h3><p>{systemDetail.output_format === 'markdown' ? 'Markdown' : '纯文本'}</p></section>
        <div className="skills-form-actions"><button className="computer-button" type="button" disabled={busy} onClick={() => void toggleSystemSkill(systemDetail)}>{systemDetail.is_enabled ? '停用' : '启用'}</button><button className="computer-button" type="button" onClick={() => setSystemDetail(null)}>关闭</button></div>
      </article>}
    </Modal>
    <Modal isOpen={modal} onClose={() => setModal(false)} title={editing ? '编辑我的 Skill' : '新建我的 Skill'} size="lg" panelClassName="skill-editor-modal" contentClassName="skill-editor-content">
      <form className="skill-modal-form" onSubmit={save}>
        <p>支持的附件会解析为受控摘录，并在选择该 Skill 时参与回答；上传的脚本只读取文本，绝不会在服务器执行。</p>
        <label>名称<input required value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} placeholder="例如：信用债风险快筛" /></label>
        <label>使用场景<textarea required rows={3} value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} placeholder="何时使用、需要什么输入、期待什么结果" /></label>
        <label>分析指令<textarea required rows={6} maxLength={4000} value={form.instructions} onChange={event => setForm({ ...form, instructions: event.target.value })} placeholder="分析步骤、约束和输出结构" /><small>{form.instructions.length} / 4000 字符</small></label>
        <label>输出格式<select value={form.output_format} onChange={event => setForm({ ...form, output_format: event.target.value as 'markdown' | 'text' })}><option value="markdown">Markdown</option><option value="text">纯文本</option></select></label>
        <div className="skill-upload"><span>Skill 附件</span><input ref={attachmentInputRef} type="file" multiple accept=".pdf,.docx,.xlsx,.csv,.txt,.md,.py,.js,.sql,.sh" onChange={selectFiles} /><button type="button" onClick={() => attachmentInputRef.current?.click()}><b>＋</b><strong>添加附件</strong><small>文档、模板、示例数据或脚本</small></button></div>
        <small className="skill-file-help">支持 PDF、DOCX、XLSX、CSV、TXT、MD、PY、JS、SQL、SH；单个文件最大 10 MB。不含 OCR、PPTX 和复杂图表解析。</small>
        <ul className="skill-attachments">{attachments.map(attachment => <li key={attachment.id}><span>{attachment.original_filename}<small>{attachmentStatus(attachment)}</small></span><button type="button" onClick={() => void removeAttachment(attachment.id)}>移除</button></li>)}{files.map((file, index) => <li key={file.name + index}><span>{file.name}<small>保存后解析</small></span><button type="button" onClick={() => setFiles(old => old.filter((_, itemIndex) => itemIndex !== index))}>移除</button></li>)}</ul>
        <label>使用状态<select value={form.status} onChange={event => setForm({ ...form, status: event.target.value as 'draft' | 'published' })}><option value="draft">仅保存，暂不启用</option><option value="published">保存并启用</option></select></label>
        <div className="skills-form-actions"><button className="computer-button" type="button" onClick={() => setModal(false)}>取消</button><button className="computer-button primary" disabled={busy} type="submit">{busy ? '保存中…' : '保存 Skill'}</button></div>
      </form>
    </Modal>
  </section>
}
