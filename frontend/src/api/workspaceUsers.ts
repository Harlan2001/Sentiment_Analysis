import { request } from '@/api/workbench'

export type WorkspaceUser = {
  id: string
  username: string
  display_name: string
  role: 'admin' | 'member'
  is_active: boolean
}

export const getWorkspaceUsers = () => request<{ items: WorkspaceUser[] }>('/sapi/workbench/users')

export const createWorkspaceUser = (input: { username: string; display_name: string; password: string; role: 'admin' | 'member' }) =>
  request<WorkspaceUser>('/sapi/workbench/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })

export const updateWorkspaceUser = (id: string, input: Partial<Pick<WorkspaceUser, 'display_name' | 'role' | 'is_active'>>) =>
  request<WorkspaceUser>(`/sapi/workbench/users/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
