import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { UserManagementPanel } from './UserManagementPanel'
import { createWorkspaceUser, getWorkspaceUsers, updateWorkspaceUser } from '@/api/workspaceUsers'

vi.mock('@/api/workspaceUsers', () => ({
  getWorkspaceUsers: vi.fn(),
  createWorkspaceUser: vi.fn(),
  updateWorkspaceUser: vi.fn(),
}))

const USERS = [
  { id: '1', username: 'admin', display_name: '系统管理员', role: 'admin' as const, is_active: true },
  { id: '2', username: 'member', display_name: '研究员', role: 'member' as const, is_active: false },
]

describe('UserManagementPanel', () => {
  afterEach(cleanup)

  beforeEach(() => {
    vi.mocked(getWorkspaceUsers).mockResolvedValue({ items: USERS })
    vi.mocked(createWorkspaceUser).mockReset()
    vi.mocked(updateWorkspaceUser).mockReset()
  })

  it('shows the real account capabilities and filters the directory', async () => {
    render(<UserManagementPanel open onClose={vi.fn()} />)

    expect(await screen.findByText('系统管理员')).toBeInTheDocument()
    expect(screen.getByText('研究员')).toBeInTheDocument()
    expect(screen.getByLabelText('账户统计')).toHaveTextContent('2 个账户')

    expect(screen.queryByText('@admin')).not.toBeInTheDocument()
    fireEvent.change(screen.getByRole('textbox', { name: '搜索用户' }), { target: { value: '系统' } })
    expect(screen.getByText('系统管理员')).toBeInTheDocument()
    expect(screen.queryByText('研究员')).not.toBeInTheDocument()

    fireEvent.change(screen.getByRole('combobox', { name: '按角色筛选' }), { target: { value: 'member' } })
    expect(screen.queryByText('系统管理员')).not.toBeInTheDocument()
    fireEvent.change(screen.getByRole('textbox', { name: '搜索用户' }), { target: { value: '' } })
    expect(screen.getByText('研究员')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('combobox', { name: '按账号状态筛选' }), { target: { value: 'active' } })
    expect(screen.queryByText('研究员')).not.toBeInTheDocument()
  })

  it('creates an account and confirms status changes inside the dialog', async () => {
    const created = { id: '3', username: 'newuser', display_name: '新用户', role: 'member' as const, is_active: true }
    vi.mocked(createWorkspaceUser).mockResolvedValue(created)
    vi.mocked(updateWorkspaceUser).mockResolvedValue({ ...USERS[0], is_active: false })
    render(<UserManagementPanel open onClose={vi.fn()} />)
    await screen.findByText('系统管理员')

    fireEvent.change(screen.getByRole('textbox', { name: /用户名/ }), { target: { value: 'newuser' } })
    fireEvent.change(screen.getByRole('textbox', { name: /显示名称/ }), { target: { value: '新用户' } })
    fireEvent.change(screen.getByLabelText('初始密码'), { target: { value: 'secret' } })
    fireEvent.click(screen.getByRole('button', { name: /创建账户/ }))

    expect(await screen.findByText('新用户')).toBeInTheDocument()
    expect(createWorkspaceUser).toHaveBeenCalledWith({ username: 'newuser', display_name: '新用户', password: 'secret', role: 'member' })

    const adminRow = screen.getByText('系统管理员').closest('article')
    expect(adminRow).not.toBeNull()
    fireEvent.click(within(adminRow!).getByRole('button', { name: '停用' }))
    expect(screen.getByRole('alertdialog', { name: '停用账户确认' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '确认停用' }))

    await waitFor(() => expect(updateWorkspaceUser).toHaveBeenCalledWith('1', { is_active: false }))
  })
})
