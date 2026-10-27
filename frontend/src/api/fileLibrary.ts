import { API_PREFIX, request } from './client'

export type FileLibraryItem = {
  id: string
  name: string
  format: string
  source: string
  source_key: string
  source_ref: string
  created_at: string | null
  kind: 'upload' | 'generated'
  size_bytes: number | null
  open_url: string | null
  download_url: string | null
}

export type FileLibraryResponse = {
  items: FileLibraryItem[]
  total: number
  page: number
  page_size: number
  sources: string[]
  formats: string[]
  summary: {
    total: number
    uploaded: number
    generated: number
    formats: Array<{ format: string; count: number }>
  }
}

export type FileLibraryFilters = {
  source?: string
  format?: string
  date_start?: string
  date_end?: string
  page?: number
  page_size?: number
}

export function fetchFileLibrary(filters: FileLibraryFilters = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  return request<FileLibraryResponse>(API_PREFIX + '/file-library?' + params.toString())
}
