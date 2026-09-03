import { request } from './client'

export type SkillStatus = 'draft' | 'published' | 'archived'
export type SkillAttachment = { id: string; original_filename: string; content_type: string | null; size_bytes: number; created_at?: string }
export type Skill = { id: string; owner_type: 'system' | 'user'; owner_username: string | null; name: string; description: string; instructions: string; input_schema_json: Array<Record<string, unknown>>; attachments?: SkillAttachment[]; output_format: 'markdown' | 'text'; status: SkillStatus; version_no: number; created_at: string; updated_at: string }
export type SkillPayload = Pick<Skill, 'name' | 'description' | 'instructions' | 'output_format' | 'status'> & { input_schema: Array<Record<string, unknown>> }

export function getSkills(query = '', scope: 'all' | 'mine' | 'system' = 'all') {
  const params = new URLSearchParams({ scope }); if (query) params.set('query', query)
  return request<{ items: Skill[] }>(`/sapi/skills?${params}`)
}
export function createSkill(input: SkillPayload) { return request<Skill>('/sapi/skills', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) }) }
export function updateSkill(id: string, input: SkillPayload) { return request<Skill>(`/sapi/skills/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) }) }
export function archiveSkill(id: string) { return request<Skill>(`/sapi/skills/${id}/archive`, { method: 'POST' }) }
export function activateSkill(id: string) { return request<Skill>(`/sapi/skills/${id}/activate`, { method: 'POST' }) }
export function deleteSkill(id: string) { return request<{ deleted: boolean }>(`/sapi/skills/${id}`, { method: 'DELETE' }) }
export function uploadSkillAttachment(skillId: string, file: File) { const body = new FormData(); body.append('file', file); return request<SkillAttachment>(`/sapi/skills/${skillId}/attachments`, { method: 'POST', body }) }
export function deleteSkillAttachment(skillId: string, attachmentId: string) { return request<{ deleted: boolean }>(`/sapi/skills/${skillId}/attachments/${attachmentId}`, { method: 'DELETE' }) }
