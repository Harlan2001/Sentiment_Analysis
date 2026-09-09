import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createProject, listProjectMembers, listProjectMemories } from '@/api/projects'
import { ProjectCreatePage } from './ProjectCreatePage'

vi.mock('@/api/projects', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/projects')>()
  return {
    ...actual,
    createProject: vi.fn(),
    listProjectMembers: vi.fn(),
    listProjectMemories: vi.fn(),
  }
})

describe('ProjectCreatePage', () => {
  beforeEach(() => {
    vi.mocked(createProject).mockResolvedValue({
      id: 'project-1',
      owner_username: 'manager-a',
      name: '利率债研究',
      description: null,
      visibility: 'shared',
      role: 'manager',
      created_at: '2026-09-07T00:00:00',
      updated_at: '2026-09-07T00:00:00',
    })
    vi.mocked(listProjectMemories).mockResolvedValue([
      {
        id: 'memory-1',
        project_id: 'project-1',
        category: 'background',
        title: '研究目标',
        content: '跟踪利率变化',
        is_active: true,
        created_by: 'manager-a',
        updated_by: 'manager-a',
        created_at: '2026-09-07T00:00:00',
        updated_at: '2026-09-07T00:00:00',
      },
    ])
    vi.mocked(listProjectMembers).mockResolvedValue([
      {
        project_id: 'project-1',
        username: 'manager-a',
        display_name: '管理者',
        role: 'manager',
        is_active: true,
        created_at: '2026-09-07T00:00:00',
        updated_at: '2026-09-07T00:00:00',
      },
      {
        project_id: 'project-1',
        username: 'editor-a',
        display_name: '编辑者',
        role: 'editor',
        is_active: true,
        created_at: '2026-09-07T00:00:00',
        updated_at: '2026-09-07T00:00:00',
      },
    ])
  })

  it('includes complete pending memory and member when the final create button is clicked', async () => {
    render(
      <MemoryRouter>
        <ProjectCreatePage />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByPlaceholderText('例如：2026 年利率债配置研究'), {
      target: { value: '利率债研究' },
    })
    fireEvent.change(screen.getByPlaceholderText('例如：核心研究目标'), {
      target: { value: '研究目标' },
    })
    fireEvent.change(screen.getByPlaceholderText('记录需要长期保留的背景、目标、约束或偏好'), {
      target: { value: '跟踪利率变化' },
    })
    fireEvent.change(screen.getByPlaceholderText('输入系统内已有用户名'), {
      target: { value: 'editor-a' },
    })
    fireEvent.click(screen.getByRole('button', { name: '创建项目' }))

    await waitFor(() =>
      expect(createProject).toHaveBeenCalledWith(
        expect.objectContaining({
          initial_memories: [
            expect.objectContaining({ title: '研究目标', content: '跟踪利率变化' }),
          ],
          initial_members: [{ username: 'editor-a', role: 'editor' }],
        })
      )
    )
    expect(listProjectMemories).toHaveBeenCalledWith('project-1')
    expect(listProjectMembers).toHaveBeenCalledWith('project-1')
  })
})
