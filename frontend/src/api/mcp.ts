import { request } from '@/api/workbench'

export type McpTool = { name: string; description: string; read_only: boolean }
export type FeishuMcpConnection = {
  id: 'feishu'
  connected: boolean
  last_sync: string | null
  account: { user_id: string | null; tenant_key: string | null } | null
  tools: McpTool[]
}

export function getFeishuMcpConnection() {
  return request<FeishuMcpConnection>('/sapi/mcp/feishu')
}

export function beginFeishuAuthorization() {
  return request<{ authorization_url: string }>('/sapi/mcp/feishu/authorize', { method: 'POST' })
}

export function disconnectFeishu() {
  return request<{ disconnected: boolean }>('/sapi/mcp/feishu', { method: 'DELETE' })
}
