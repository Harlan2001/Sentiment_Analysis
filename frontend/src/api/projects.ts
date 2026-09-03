import { request } from './client'
import type { DailyNewsSummaryTask } from './newsSummary'
import type { StrategyConversation } from './strategy'

export type ProjectRole = 'owner' | 'editor' | 'viewer'
export type MemoryCategory = 'background' | 'goal' | 'constraint' | 'preference' | 'conclusion' | 'other'

/**
 * 项目（由 projectManagement.ts 与 workbench.ts 两处类型合并而来）。
 * 部分字段仅特定接口返回（侧边栏行带 role，详情接口带 owner_username/visibility），故置为可选。
 */
export type Project = {
  id: string
  name: string
  description: string | null
  role: ProjectRole // 项目详情/成员接口必带；侧边栏行可能缺失
  owner_username?: string
  visibility?: 'private' | 'shared'
  created_at: string
  updated_at: string
}

export type Conversation = {
  id: string
  project_id: string | null
  title: string
  module_type?: string
  source?: string
  status: string
  created_at: string
  updated_at: string
  last_message_at: string | null
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

export type InitialProjectMemory = {
  category: MemoryCategory
  title: string
  content: string
}

export type InitialProjectMember = {
  username: string
  role: 'editor' | 'viewer'
}

// ── 项目 CRUD ────────────────────────────────────────────

export function createProject(input: {
  name: string
  description?: string
  client_request_id?: string
  initial_memories?: InitialProjectMemory[]
  initial_members?: InitialProjectMember[]
}) {
  return request<Project>('/sapi/workbench/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function getProject(projectId: string) {
  return request<Project>(`/sapi/workbench/projects/${projectId}`)
}

export function updateProject(projectId: string, input: { name?: string; description?: string | null }) {
  return request<Project>(`/sapi/workbench/projects/${projectId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function deleteProject(projectId: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/projects/${projectId}`, { method: 'DELETE' })
}

export function restoreProject(projectId: string) {
  return request<Project>(`/sapi/workbench/projects/${projectId}/restore`, { method: 'POST' })
}

export function permanentlyDeleteProject(projectId: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/projects/${projectId}/permanently`, { method: 'DELETE' })
}

// ── 项目会话 ─────────────────────────────────────────────

export function getProjectConversations(projectId: string, options: { limit?: number; archived?: boolean } = {}) {
  const query: string[] = [`limit=${options.limit ?? 50}`]
  if (options.archived !== undefined) query.push(`archived=${options.archived}`)
  return request<ListData<Conversation>>(`/sapi/workbench/projects/${projectId}/conversations?${query.join('&')}`)
}

export function updateConversation(conversationId: string, input: { archived: boolean }) {
  return request<Conversation>(`/sapi/workbench/conversations/${conversationId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function deleteConversation(conversationId: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/conversations/${conversationId}`, { method: 'DELETE' })
}

export function restoreConversation(conversationId: string) {
  return request<Conversation>(`/sapi/workbench/conversations/${conversationId}/restore`, { method: 'POST' })
}

export function permanentlyDeleteConversation(conversationId: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/conversations/${conversationId}/permanently`, { method: 'DELETE' })
}

// ── 最近删除 ─────────────────────────────────────────────

export type DeletedProject = Project & { deleted_at: string }
export type DeletedConversation = Conversation & { deleted_at: string }
export type DeletedStrategyConversation = StrategyConversation & { deleted_at: string }
export type DeletedReportTask = {
  id: string
  title: string
  requirement: string
  date_start: string | null
  date_end: string | null
  status: string
  created_at: string
  updated_at: string
  deleted_at: string
}
export type DeletedNewsSummaryTask = Pick<
  DailyNewsSummaryTask,
  'id' | 'start_date' | 'end_date' | 'focus' | 'status' | 'news_count' | 'created_at' | 'updated_at'
> & { deleted_at: string }

export type DeletedItemsData = {
  deleted_projects: DeletedProject[]
  deleted_conversations: DeletedConversation[]
  deleted_strategies: DeletedStrategyConversation[]
  deleted_reports: DeletedReportTask[]
  deleted_news_summaries: DeletedNewsSummaryTask[]
}

export function getDeletedItems() {
  return request<DeletedItemsData>('/sapi/workbench/deleted-items')
}

export function emptyDeletedItems() {
  return request<Record<string, number>>('/sapi/workbench/deleted-items', { method: 'DELETE' })
}

// ── 项目记忆 ─────────────────────────────────────────────

export function listProjectMemories(projectId: string) {
  return request<ProjectMemory[]>(`/sapi/workbench/projects/${projectId}/memories?include_inactive=true`)
}

export function createProjectMemory(
  projectId: string,
  input: Omit<ProjectMemory, 'id' | 'project_id' | 'created_by' | 'updated_by' | 'created_at' | 'updated_at'>,
) {
  return request<ProjectMemory>(`/sapi/workbench/projects/${projectId}/memories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updateProjectMemory(
  projectId: string,
  memoryId: string,
  input: Partial<Pick<ProjectMemory, 'category' | 'title' | 'content' | 'is_active'>>,
) {
  return request<ProjectMemory>(`/sapi/workbench/projects/${projectId}/memories/${memoryId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function deleteProjectMemory(projectId: string, memoryId: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/projects/${projectId}/memories/${memoryId}`, {
    method: 'DELETE',
  })
}

// ── 项目成员 ─────────────────────────────────────────────

export function listProjectMembers(projectId: string) {
  return request<ProjectMember[]>(`/sapi/workbench/projects/${projectId}/members`)
}

export function upsertProjectMember(projectId: string, username: string, role: 'editor' | 'viewer') {
  return request<ProjectMember>(
    `/sapi/workbench/projects/${projectId}/members/${encodeURIComponent(username)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    },
  )
}

export function removeProjectMember(projectId: string, username: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/projects/${projectId}/members/${encodeURIComponent(username)}`, {
    method: 'DELETE',
  })
}