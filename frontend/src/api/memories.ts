import { request } from './client'

export type MemoryCategory = 'response_preference' | 'user_background' | 'long_term_interest' | 'personal_constraint'
export type MemoryStatus = 'pending' | 'active' | 'disabled'
export type MemorySource = 'manual' | 'explicit_chat' | 'inferred_chat'

export type UserMemory = {
  id: string
  owner_username: string
  category: MemoryCategory
  normalized_key: string
  title: string
  content: string
  source_type: MemorySource
  source_conversation_id: string | null
  source_message_id: string | null
  status: MemoryStatus
  confidence: number | null
  is_pinned: boolean
  created_at: string
  updated_at: string
}

export type MemorySettings = {
  owner_username: string
  memory_enabled: boolean
  auto_extract_enabled: boolean
}

export function listMemories() {
  return request<{ items: UserMemory[] }>('/sapi/workbench/memories?limit=100')
}

export function createMemory(input: Pick<UserMemory, 'category' | 'title' | 'content'> & { is_pinned?: boolean }) {
  return request<UserMemory>('/sapi/workbench/memories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updateMemory(memoryId: string, input: Partial<Pick<UserMemory, 'category' | 'title' | 'content' | 'status' | 'is_pinned'>>) {
  return request<UserMemory>(`/sapi/workbench/memories/${memoryId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function deleteMemory(memoryId: string) {
  return request<{ deleted: boolean }>(`/sapi/workbench/memories/${memoryId}`, { method: 'DELETE' })
}

export function clearMemories() {
  return request<{ deleted: number }>('/sapi/workbench/memories', { method: 'DELETE' })
}

export function getMemorySettings() {
  return request<MemorySettings>('/sapi/workbench/memory-settings')
}

export function updateMemorySettings(input: Partial<Pick<MemorySettings, 'memory_enabled' | 'auto_extract_enabled'>>) {
  return request<MemorySettings>('/sapi/workbench/memory-settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}
