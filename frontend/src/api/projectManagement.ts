import { storage } from '@/utils/helpers'

export type ProjectRole = 'owner' | 'editor' | 'viewer'
export type MemoryCategory = 'background' | 'goal' | 'constraint' | 'preference' | 'conclusion' | 'other'

export type Project = {
  id: string
  owner_username: string
  name: string
  description: string | null
  visibility: 'private' | 'shared'
  role: ProjectRole
  created_at: string
  updated_at: string
}

export type Conversation = {
  id: string
  project_id: string | null
  title: string
  status: 'active' | 'archived'
  last_message_at: string | null
  created_at: string
  updated_at: string
}

export type ProjectMemory = {
  id: string
  project_id: string
  category: MemoryCategory
  title: string
  content: string
  is_active: boolean
  created_by: string
  updated_by: string
  created_at: string
  updated_at: string
}

export type ProjectMember = {
  project_id: string
  username: string
  display_name: string
  role: ProjectRole
  is_active: boolean
  created_at: string
  updated_at: string
}

type ListData<T> = { items: T[]; next_cursor?: string | null }

function authorizationHeader(): Record<string, string> {
  const token = storage.get<string>('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: { ...authorizationHeader(), ...options.headers },
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const error = new Error(payload?.detail || payload?.message || '请求项目服务失败') as Error & { status?: number }
    error.status = response.status
    throw error
  }
  return payload.data as T
}

function jsonOptions(method: string, input: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }
}

export type InitialProjectMemory = {
  category: MemoryCategory
  title: string
  content: string
}

export type InitialProjectMember = {
  username: string
  role: 'editor' | 'viewer'
}

export const createProject = (input: {
  name: string
  description?: string
  client_request_id?: string
  initial_memories?: InitialProjectMemory[]
  initial_members?: InitialProjectMember[]
}) => request<Project>('/sapi/workbench/projects', jsonOptions('POST', input))

export const getProject = (projectId: string) => request<Project>(`/sapi/workbench/projects/${projectId}`)

export const updateProject = (projectId: string, input: { name?: string; description?: string | null }) =>
  request<Project>(`/sapi/workbench/projects/${projectId}`, jsonOptions('PATCH', input))

export const deleteProject = (projectId: string) =>
  request<{ deleted: boolean }>(`/sapi/workbench/projects/${projectId}`, { method: 'DELETE' })

export const getProjectConversations = (projectId: string, archived = false) =>
  request<ListData<Conversation>>(`/sapi/workbench/projects/${projectId}/conversations?limit=50&archived=${archived}`)

export const updateConversation = (conversationId: string, input: { archived: boolean }) =>
  request<Conversation>(`/sapi/workbench/conversations/${conversationId}`, jsonOptions('PATCH', input))

export const deleteConversation = (conversationId: string) =>
  request<{ deleted: boolean }>(`/sapi/workbench/conversations/${conversationId}`, { method: 'DELETE' })

export const listProjectMemories = (projectId: string) =>
  request<ProjectMemory[]>(`/sapi/workbench/projects/${projectId}/memories?include_inactive=true`)

export const createProjectMemory = (
  projectId: string,
  input: Omit<ProjectMemory, 'id' | 'project_id' | 'created_by' | 'updated_by' | 'created_at' | 'updated_at'>
) => request<ProjectMemory>(`/sapi/workbench/projects/${projectId}/memories`, jsonOptions('POST', input))

export const updateProjectMemory = (
  projectId: string,
  memoryId: string,
  input: Partial<Pick<ProjectMemory, 'category' | 'title' | 'content' | 'is_active'>>
) => request<ProjectMemory>(`/sapi/workbench/projects/${projectId}/memories/${memoryId}`, jsonOptions('PATCH', input))

export const deleteProjectMemory = (projectId: string, memoryId: string) =>
  request<{ deleted: boolean }>(`/sapi/workbench/projects/${projectId}/memories/${memoryId}`, { method: 'DELETE' })

export const listProjectMembers = (projectId: string) =>
  request<ProjectMember[]>(`/sapi/workbench/projects/${projectId}/members`)

export const upsertProjectMember = (projectId: string, username: string, role: 'editor' | 'viewer') =>
  request<ProjectMember>(
    `/sapi/workbench/projects/${projectId}/members/${encodeURIComponent(username)}`,
    jsonOptions('PUT', { role })
  )

export const removeProjectMember = (projectId: string, username: string) =>
  request<{ deleted: boolean }>(`/sapi/workbench/projects/${projectId}/members/${encodeURIComponent(username)}`, {
    method: 'DELETE',
  })
