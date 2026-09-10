import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SkillsPage } from './SkillsPage'
import * as skillsApi from '@/api/skills'

vi.mock('@/api/skills', () => ({
  activateSkill: vi.fn(),
  archiveSkill: vi.fn(),
  createSkill: vi.fn(),
  deleteSkill: vi.fn(),
  deleteSkillAttachment: vi.fn(),
  disableSystemSkill: vi.fn(),
  enableSystemSkill: vi.fn(),
  getSkill: vi.fn(),
  getSkills: vi.fn(),
  updateSkill: vi.fn(),
  uploadSkillAttachment: vi.fn(),
}))

const systemSkill = {
  id: 'system-1', owner_type: 'system' as const, owner_username: null,
  name: '宏观政策速读', description: '提炼政策传导路径', instructions: '核对政策原文',
  input_schema_json: [], output_format: 'markdown' as const, status: 'published' as const,
  version_no: 1, created_at: '2026-09-08T00:00:00', updated_at: '2026-09-08T00:00:00',
  is_enabled: false,
}

const draftSkill = {
  ...systemSkill,
  id: 'draft-1', owner_type: 'user' as const, owner_username: 'alice',
  name: '一个测试skill', description: '验证 Skill 是否生效', instructions: '输出测试完成',
  status: 'draft' as const, is_enabled: undefined,
}

describe('SkillsPage', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('lets the current user enable a system Skill explicitly', async () => {
    vi.mocked(skillsApi.getSkills).mockImplementation(async (_query, scope) => (
      scope === 'system' ? { items: [systemSkill] } : { items: [] }
    ))
    vi.mocked(skillsApi.enableSystemSkill).mockResolvedValue({ ...systemSkill, is_enabled: true })
    render(<MemoryRouter><SkillsPage /></MemoryRouter>)

    expect(await screen.findByText('宏观政策速读')).toBeInTheDocument()
    expect(screen.getByText('○ 未启用')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '启用' }))
    await waitFor(() => expect(skillsApi.enableSystemSkill).toHaveBeenCalledWith('system-1'))
    expect(skillsApi.createSkill).not.toHaveBeenCalled()
  })

  it('shows a real loading error instead of treating it as an empty list', async () => {
    vi.mocked(skillsApi.getSkills).mockRejectedValue(new Error('系统 Skill 服务不可用'))

    render(<MemoryRouter><SkillsPage /></MemoryRouter>)

    expect(await screen.findByText('系统 Skill 服务不可用')).toBeInTheDocument()
  })

  it('opens a read-only system Skill detail with its full instructions', async () => {
    vi.mocked(skillsApi.getSkills).mockImplementation(async (_query, scope) => (
      scope === 'system' ? { items: [systemSkill] } : { items: [] }
    ))
    vi.mocked(skillsApi.getSkill).mockResolvedValue({
      ...systemSkill,
      instructions: '第一步核对政策原文\n第二步提炼传导路径',
      version_no: 3,
    })

    render(<MemoryRouter><SkillsPage /></MemoryRouter>)

    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }))

    expect(await screen.findByText((_content, element) => element?.tagName === 'PRE' && element.textContent === '第一步核对政策原文\n第二步提炼传导路径')).toBeInTheDocument()
    expect(screen.getByText('Markdown')).toBeInTheDocument()
    expect(screen.getByText('v3')).toBeInTheDocument()
    expect(screen.getByText('○ 当前账号未启用')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '保存 Skill' })).not.toBeInTheDocument()
  })

  it('offers an explicit enable action for a saved personal Skill', async () => {
    vi.mocked(skillsApi.getSkills).mockImplementation(async (_query, scope) => (
      scope === 'system' ? { items: [] } : { items: [draftSkill] }
    ))
    vi.mocked(skillsApi.activateSkill).mockResolvedValue({ ...draftSkill, status: 'published' })

    render(<MemoryRouter><SkillsPage /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: '我的' }))
    fireEvent.click(await screen.findByRole('button', { name: '启用' }))

    await waitFor(() => expect(skillsApi.activateSkill).toHaveBeenCalledWith('draft-1'))
  })

  it('shows attachment parsing status in the personal Skill editor', async () => {
    vi.mocked(skillsApi.getSkills).mockImplementation(async (_query, scope) => (
      scope === 'system' ? { items: [] } : { items: [{ ...draftSkill, status: 'published' }] }
    ))
    vi.mocked(skillsApi.getSkill).mockResolvedValue({
      ...draftSkill,
      status: 'published',
      attachments: [{
        id: 'attachment-1', original_filename: '策略手册.pdf', content_type: 'application/pdf',
        size_bytes: 1024, parse_status: 'ready', page_count: 12,
      }],
    })

    render(<MemoryRouter><SkillsPage /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: '我的' }))
    fireEvent.click(await screen.findByRole('button', { name: '编辑' }))

    expect(await screen.findByText('策略手册.pdf')).toBeInTheDocument()
    expect(screen.getByText('已解析 · 12 页')).toBeInTheDocument()
    expect(screen.getByText('6 / 4000 字符')).toBeInTheDocument()
  })
})
