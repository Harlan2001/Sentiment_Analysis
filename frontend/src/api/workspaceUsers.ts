import { request } from '@/api/client'

export type WorkspaceUser = {
  id: string
  username: string
  display_name: string
  role: 'admin' | 'member'
  is_active: boolean
}

export const getWorkspaceUsers = () => request<{ data: { items: WorkspaceUser[] } }>('/sapi/workbench/users')

export const createWorkspaceUser = (input: { username: string; display_name: string; password: string; role: 'admin' | 'member' }) =>
  request<{ data: WorkspaceUser }>('/sapi/workbench/users', { method: 'POST', body: JSON.stringify(input) })

export const updateWorkspaceUser = (id: string, input: Partial<Pick<WorkspaceUser, 'display_name' | 'role' | 'is_active'>>) =>
  request<{ data: WorkspaceUser }>(`/sapi/workbench/users/${id}`, { method: 'PATCH', body: JSON.stringify(input) })
