import { FormEvent, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  InitialProjectMember,
  InitialProjectMemory,
  MemoryCategory,
  createProject,
  listProjectMembers,
  listProjectMemories,
} from '@/api/projects'
import { uuid } from '@/utils/helpers'
import './project-create.css'

const CATEGORY_LABELS: Record<MemoryCategory, string> = {
  background: '研究背景',
  goal: '项目目标',
  constraint: '约束边界',
  preference: '研究偏好',
  conclusion: '关键结论',
  other: '其他',
}

type MemoryDraft = InitialProjectMemory & { localId: string }
type MemberDraft = InitialProjectMember & { localId: string }

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '创建项目失败'
}

export function ProjectCreatePage() {
  const navigate = useNavigate()
  const [requestId] = useState(() => uuid())
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [memories, setMemories] = useState<MemoryDraft[]>([])
  const [members, setMembers] = useState<MemberDraft[]>([])
  const [memoryCategory, setMemoryCategory] = useState<MemoryCategory>('background')
  const [memoryTitle, setMemoryTitle] = useState('')
  const [memoryContent, setMemoryContent] = useState('')
  const [memberUsername, setMemberUsername] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const pendingMemoryReady = Boolean(memoryTitle.trim() && memoryContent.trim())
  const pendingMemberReady = Boolean(memberUsername.trim())
  const finalMemoryCount = memories.length + (pendingMemoryReady ? 1 : 0)
  const finalMemberCount = members.length + (pendingMemberReady ? 1 : 0)

  const completedSections = useMemo(() => {
    return [Boolean(name.trim()), finalMemoryCount > 0, finalMemberCount > 0].filter(Boolean).length
  }, [finalMemberCount, finalMemoryCount, name])

  function addMemory() {
    if (!memoryTitle.trim() || !memoryContent.trim()) {
      setError('请填写记忆标题和内容后再添加。')
      return
    }
    setMemories((items) => [
      ...items,
      {
        localId: uuid(),
        category: memoryCategory,
        title: memoryTitle.trim(),
        content: memoryContent.trim(),
      },
    ])
    setMemoryTitle('')
    setMemoryContent('')
    setError('')
  }

  function addMember() {
    const username = memberUsername.trim()
    if (!username) {
      setError('请输入系统内已有用户名。')
      return
    }
    if (members.some((member) => member.username === username)) {
      setError('该成员已经在初始成员列表中。')
      return
    }
    setMembers((items) => [
      ...items,
      {
        localId: uuid(),
        username,
        role: 'editor',
      },
    ])
    setMemberUsername('')
    setError('')
  }

  async function submitProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!name.trim() || saving) return
    const pendingMemoryStarted = Boolean(memoryTitle.trim() || memoryContent.trim())
    if (pendingMemoryStarted && !pendingMemoryReady) {
      setError('当前记忆尚未填写完整，请补全标题和内容后再创建项目。')
      return
    }
    const pendingUsername = memberUsername.trim()
    if (pendingUsername && members.some((member) => member.username === pendingUsername)) {
      setError('当前输入的成员已经在初始成员列表中。')
      return
    }
    const finalMemories = pendingMemoryReady
      ? [...memories, { localId: uuid(), category: memoryCategory, title: memoryTitle.trim(), content: memoryContent.trim() }]
      : memories
    const finalMembers = pendingUsername
      ? [...members, { localId: uuid(), username: pendingUsername, role: 'editor' as const }]
      : members
    setSaving(true)
    setError('')
    try {
      const project = await createProject({
        name: name.trim(),
        description: description.trim() || undefined,
        client_request_id: requestId,
        initial_memories: finalMemories.map(({ category, title, content }) => ({ category, title, content })),
        initial_members: finalMembers.map(({ username, role }) => ({ username, role })),
      })
      const [savedMemories, savedMembers] = await Promise.all([
        listProjectMemories(project.id),
        listProjectMembers(project.id),
      ])
      const memoriesPersisted = finalMemories.every((expected) =>
        savedMemories.some(
          (saved) =>
            saved.category === expected.category &&
            saved.title === expected.title &&
            saved.content === expected.content
        )
      )
      const membersPersisted = finalMembers.every((expected) =>
        savedMembers.some((saved) => saved.username === expected.username && saved.role === 'editor')
      )
      if (!memoriesPersisted || !membersPersisted) {
        throw new Error('项目已经创建，但初始记忆或成员未完整写入，请重试或进入项目检查。')
      }
      window.dispatchEvent(new Event('bondsense-sidebar-refresh'))
      navigate(`/projects/${project.id}`, { replace: true })
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="pc-page">
      <header className="pc-header">
        <div>
          <button className="pc-back" onClick={() => navigate(-1)}>
            ← 返回
          </button>
          <span className="pc-kicker">新建项目空间</span>
          <h1>为一项长期研究建立清晰上下文</h1>
          <p>一次设置项目基本信息、初始记忆和协作权限，创建后可随时继续调整。</p>
        </div>
        <span className="pc-progress">已配置 {completedSections}/3</span>
      </header>

      <form className="pc-layout" onSubmit={submitProject}>
        <div className="pc-sections">
          <section className="pc-section">
            <header>
              <span>01</span>
              <div>
                <h2>项目基本信息</h2>
                <p>名称用于 Sidebar 和项目标题，说明帮助成员快速理解研究范围。</p>
              </div>
              <em>必填</em>
            </header>
            <div className="pc-fields">
              <label className="wide">
                <strong>项目名称</strong>
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  maxLength={80}
                  required
                  autoFocus
                  placeholder="例如：2026 年利率债配置研究"
                />
                <small>{name.length}/80</small>
              </label>
              <label className="wide">
                <strong>项目说明（可选）</strong>
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  maxLength={1000}
                  rows={4}
                  placeholder="说明研究目标、覆盖范围以及希望解决的问题"
                />
                <small>{description.length}/1000</small>
              </label>
            </div>
          </section>

          <section className="pc-section">
            <header>
              <span>02</span>
              <div>
                <h2>初始项目记忆</h2>
                <p>为后续项目会话提供稳定背景。只有明确添加的内容才会进入 AI 上下文。</p>
              </div>
              <em>可选</em>
            </header>
            <div className="pc-composer">
              <label>
                <strong>记忆类型</strong>
                <select
                  value={memoryCategory}
                  onChange={(event) => setMemoryCategory(event.target.value as MemoryCategory)}
                >
                  {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                    <option value={value} key={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <strong>标题</strong>
                <input
                  value={memoryTitle}
                  maxLength={120}
                  onChange={(event) => setMemoryTitle(event.target.value)}
                  placeholder="例如：核心研究目标"
                />
              </label>
              <label className="wide">
                <strong>内容</strong>
                <textarea
                  value={memoryContent}
                  maxLength={10000}
                  rows={4}
                  onChange={(event) => setMemoryContent(event.target.value)}
                  placeholder="记录需要长期保留的背景、目标、约束或偏好"
                />
              </label>
              <button className="pc-secondary wide" type="button" onClick={addMemory}>
                ＋ 添加到初始记忆
              </button>
            </div>
            {memories.length === 0 ? (
              <div className="pc-empty">尚未添加初始记忆，创建后也可以在项目详情中维护。</div>
            ) : (
              <div className="pc-draft-list">
                {memories.map((memory) => (
                  <article key={memory.localId}>
                    <span>{CATEGORY_LABELS[memory.category]}</span>
                    <div>
                      <strong>{memory.title}</strong>
                      <p>{memory.content}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setMemories((items) => items.filter((item) => item.localId !== memory.localId))}
                    >
                      移除
                    </button>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="pc-section">
            <header>
              <span>03</span>
              <div>
                <h2>初始成员与权限</h2>
                <p>当前仅能添加系统内已有用户；当前账户会自动成为项目管理者，其他成员均为编辑者。</p>
              </div>
              <em>可选</em>
            </header>
            <div className="pc-member-composer">
              <label>
                <strong>用户名</strong>
                <input
                  value={memberUsername}
                  maxLength={191}
                  onChange={(event) => setMemberUsername(event.target.value)}
                  placeholder="输入系统内已有用户名"
                />
              </label>
              <button className="pc-secondary" type="button" onClick={addMember}>
                添加成员
              </button>
            </div>
            <div className="pc-owner">
              <i>你</i>
              <div>
                <strong>当前账户</strong>
                <p>创建后自动成为项目唯一管理者</p>
              </div>
              <span>管理者</span>
            </div>
            {members.map((member) => (
              <div className="pc-member" key={member.localId}>
                <i>{member.username.slice(0, 1).toUpperCase()}</i>
                <div>
                  <strong>{member.username}</strong>
                  <p>系统内已有用户</p>
                </div>
                <span>编辑者</span>
                <button
                  type="button"
                  onClick={() => setMembers((items) => items.filter((item) => item.localId !== member.localId))}
                >
                  移除
                </button>
              </div>
            ))}
          </section>
        </div>

        <aside className="pc-summary">
          <span className="pc-kicker">创建摘要</span>
          <h2>{name.trim() || '未命名项目'}</h2>
          <p>{description.trim() || '尚未填写项目说明。'}</p>
          <dl>
            <div>
              <dt>初始记忆</dt>
              <dd>{finalMemoryCount} 条</dd>
            </div>
            <div>
              <dt>项目成员</dt>
              <dd>{finalMemberCount + 1} 人</dd>
            </div>
            <div>
              <dt>可见范围</dt>
              <dd>{finalMemberCount ? '共享' : '私有'}</dd>
            </div>
          </dl>
          <div className="pc-boundary">
            <strong>项目边界</strong>
            <p>项目会话独立归类；未发送消息的空会话不会进入历史；聊天内容不会自动写入项目记忆。</p>
            <p>输入框中填写完整但尚未点击添加的记忆或成员，也会在创建项目时自动加入。</p>
          </div>
          {error && (
            <p className="pc-error" role="alert">
              {error}
            </p>
          )}
          <button className="pc-create" disabled={!name.trim() || saving}>
            {saving ? '正在创建项目…' : '创建项目'}
          </button>
          <button className="pc-cancel" type="button" onClick={() => navigate(-1)} disabled={saving}>
            取消
          </button>
        </aside>
      </form>
    </section>
  )
}
