/**
 * 政策文件分析 API（工作流内）。
 *
 * 与研报分析同构：上传 PDF → 解析 → AI 解读 → 查看结果。
 * 差异：上传后后端**立即**触发解读，无需二次调用。
 */
import { API_PREFIX as BASE, request } from './client'
import type {
  PolicyDocumentDetail,
  PolicyDocumentListResponse,
} from '@/types'

export function fetchPolicyDocuments(
  page = 1,
  pageSize = 20,
): Promise<PolicyDocumentListResponse> {
  return request<PolicyDocumentListResponse>(
    `${BASE}/policy-documents?page=${page}&page_size=${pageSize}`,
  )
}

export function fetchPolicyDocument(documentId: number): Promise<PolicyDocumentDetail> {
  return request<PolicyDocumentDetail>(`${BASE}/policy-documents/${documentId}`)
}

/** 重新解读（用于失败重试或换模型复跑）。 */
export function reanalyzePolicyDocument(
  documentId: number,
): Promise<{ document_id: number; status: string }> {
  return request<{ document_id: number; status: string }>(
    `${BASE}/policy-documents/${documentId}/analyze`,
    { method: 'POST' },
  )
}

export function deletePolicyDocument(documentId: number): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`${BASE}/policy-documents/${documentId}`, {
    method: 'DELETE',
  })
}