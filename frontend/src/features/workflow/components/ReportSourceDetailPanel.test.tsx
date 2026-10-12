import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * 单篇研报详情侧栏测试（对应 PRD 板块一）
 * - 展示深度拆解结构（观点复现、AI 解读·非作者观点分区）
 * - 不用 full_text 切前 5 段冒充「原文摘录」
 * - 原文图表区块已按产品决定移除（图片资源抽取不稳定，不再展示）
 */

vi.mock('@/api/client', () => ({
  request: vi.fn(),
  API_PREFIX: '/sapi',
}))

import { request } from '@/api/client'
import { ReportSourceDetailPanel } from './ReportSourceDetailPanel'

const deepDetail = {
  id: 1,
  title: '2026 年利率债策略',
  institution: 'XX 证券',
  analyst: '张三',
  publish_date: '2026-01-02',
  industry: '固收',
  report_type: 'macro',
  page_count: 22,
  file_size_kb: 2048,
  source: 'web_upload',
  status: 'analyzed',
  ai_model: 'glm',
  ai_analyzed_at: '2026-01-05T10:00:00',
  full_text: '第一段。\n\n第二段。',
  // 新结构字段（实现侧命名以接口为准，侧栏至少要能呈现以下章节标题）
  ai_deep_markdown: [
    '# 2026 年利率债策略 · 深度拆解',
    '## 三、观点复现',
    '### 观点 1：10Y 中枢降至 1.55%',
    '## 六、AI 分析解读（非作者观点）',
  ].join('\n'),
}

beforeEach(() => {
  vi.mocked(request).mockResolvedValue(deepDetail as never)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ReportSourceDetailPanel · 板块一', () => {
  it('按深度拆解结构渲染，且 AI 解读带非作者观点标识', async () => {
    render(<ReportSourceDetailPanel reportId={1} onClose={() => undefined} />)
    expect(await screen.findByText(/观点复现/)).toBeInTheDocument()
    expect(screen.getByText(/AI 分析解读（非作者观点）/)).toBeInTheDocument()
  })

  it('不再以全文前 5 段冒充原文摘录', async () => {
    render(<ReportSourceDetailPanel reportId={1} onClose={() => undefined} />)
    await screen.findByText(/观点复现/)
    expect(screen.queryByText('原文摘录')).toBeNull()
  })
})
