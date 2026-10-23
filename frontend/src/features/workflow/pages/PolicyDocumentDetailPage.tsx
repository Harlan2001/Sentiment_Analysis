import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { fetchPolicyDocument, reanalyzePolicyDocument } from '@/api/policyDocuments'
import type { PolicyDocumentDetail, PolicyImpactDirection } from '@/types'

/**
 * 政策文件解读详情。
 *
 * 展示纪律：影响方向**必须与原文依据同屏** —— 依据是 policy 解读可信度的来源，
 * 单独呈现结论会让用户无从判断 AI 是否在编。
 */

const DIRECTION_META: Record<PolicyImpactDirection, { label: string; className: string }> = {
  bullish: { label: '利多债券', className: 'policy-dir bullish' },
  bearish: { label: '利空债券', className: 'policy-dir bearish' },
  neutral: { label: '中性', className: 'policy-dir neutral' },
}

const STATUS_LABEL: Record<string, string> = {
  uploaded: '待解读',
  analyzing: '解读中',
  completed: '已完成',
  failed: '解读失败',
}

export default function PolicyDocumentDetailPage() {
  const { documentId = '' } = useParams()
  const navigate = useNavigate()
  const [document, setDocument] = useState<PolicyDocumentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(
    async (quiet = false) => {
      if (!quiet) setLoading(true)
      try {
        setDocument(await fetchPolicyDocument(Number(documentId)))
        setError('')
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : '读取政策文件失败')
      } finally {
        if (!quiet) setLoading(false)
      }
    },
    [documentId],
  )

  useEffect(() => {
    void load()
  }, [load])

  // 解读中时轮询（分析在服务端后台线程执行）
  useEffect(() => {
    if (!document || (document.status !== 'analyzing' && document.status !== 'uploaded')) return
    const timer = window.setInterval(() => void load(true), 4000)
    return () => window.clearInterval(timer)
  }, [document, load])

  const handleReanalyze = async () => {
    try {
      await reanalyzePolicyDocument(Number(documentId))
      void load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '重新解读失败')
    }
  }

  const analysis = document?.analysis
  const direction = analysis?.impact_direction
  const directionMeta = direction ? DIRECTION_META[direction] : null

  return (
    <section className="computer-page report-detail-page">
      <div className="computer-tabs">
        <button onClick={() => navigate('/computer/policy')}>← 返回政策文件分析</button>
        <span className="computer-spacer" />
        <button className="computer-button" onClick={() => void load()}>
          刷新状态
        </button>
      </div>

      {loading ? (
        <div className="report-detail-state">正在读取…</div>
      ) : error && !document ? (
        <div className="report-detail-state error">
          {error}
          <button className="computer-button" onClick={() => void load()}>
            重试
          </button>
        </div>
      ) : document ? (
        <>
          <header className="report-detail-header">
            <div>
              <span
                className={`computer-badge ${
                  document.status === 'completed'
                    ? 'file'
                    : document.status === 'failed'
                      ? 'warning'
                      : 'running'
                }`}
              >
                {STATUS_LABEL[document.status] ?? document.status}
              </span>
              <h1>{document.title}</h1>
              <p className="text-xs text-gray-500 mt-1">
                {document.issuer || '未识别发文机关'}
                {document.document_no ? ` · ${document.document_no}` : ''}
                {document.publish_date ? ` · ${document.publish_date}` : ''}
                {document.page_count ? ` · ${document.page_count} 页` : ''}
              </p>
            </div>
          </header>

          {document.status === 'failed' && (
            <div className="report-detail-state error">
              {document.error_message || '解读失败'}
              <button className="computer-button" onClick={handleReanalyze}>
                重新解读
              </button>
            </div>
          )}

          {analysis ? (
            <div className="space-y-4">
              {/* 影响方向 + 依据（同屏，依据不可省） */}
              <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-sm font-medium text-gray-400">对债市影响</h2>
                  {directionMeta && <span className={directionMeta.className}>{directionMeta.label}</span>}
                  {!analysis.evidence?.length && direction === 'neutral' && (
                    <span className="text-[11px] text-gray-600">
                      （未找到充分依据，按中性处理）
                    </span>
                  )}
                </div>
                {analysis.impact_reason && (
                  <p className="mt-3 text-sm leading-relaxed text-gray-300">{analysis.impact_reason}</p>
                )}
                {analysis.domains?.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {analysis.domains.map((domain) => (
                      <span
                        key={domain}
                        className="rounded border border-[#343434] px-2 py-0.5 text-[11px] text-gray-400"
                      >
                        {domain}
                      </span>
                    ))}
                  </div>
                ) : null}
              </section>

              {/* 原文依据 */}
              <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
                <h2 className="mb-3 text-sm font-medium text-gray-400">原文依据</h2>
                {analysis.evidence?.length ? (
                  <ul className="space-y-3">
                    {analysis.evidence.map((item, index) => (
                      <li key={index} className="rounded-lg border border-[#1e1e1e] bg-[#0d0d0d] p-3">
                        <p className="border-l-2 border-[#3d3d42] pl-3 text-xs leading-relaxed text-gray-300">
                          {item.text}
                        </p>
                        {item.inference && (
                          <p className="mt-2 text-xs text-gray-500">→ {item.inference}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-gray-600">本次解读未给出原文依据（影响方向已按中性处理）。</p>
                )}
              </section>

              {analysis.summary && (
                <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
                  <h2 className="mb-3 text-sm font-medium text-gray-400">文件摘要</h2>
                  <p className="text-sm leading-relaxed text-gray-300">{analysis.summary}</p>
                </section>
              )}

              {analysis.key_points?.length ? (
                <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5">
                  <h2 className="mb-3 text-sm font-medium text-gray-400">政策要点</h2>
                  <ul className="space-y-2">
                    {analysis.key_points.map((point, index) => (
                      <li key={index} className="flex gap-2 text-sm text-gray-300">
                        <span className="text-gray-600">{index + 1}.</span>
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              <p className="diag-footnote">
                AI 解读 · 模型 {analysis.model_name || document.model_name || '—'} ·{' '}
                {document.created_at?.slice(0, 16)} · 结论仅供参考，请以文件原文为准
              </p>
            </div>
          ) : document.status !== 'failed' ? (
            <div className="report-detail-state">
              <div className="mb-3 h-7 w-7 animate-spin rounded-full border-2 border-gray-600 border-t-blue-400" />
              AI 正在解读中，请稍候…
            </div>
          ) : null}

          <section className="rounded-xl border border-[#2a2a2e] bg-[#111111] p-5 mt-4">
            <h2 className="mb-3 text-sm font-medium text-gray-400">正文预览</h2>
            <pre className="max-h-[320px] overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-gray-400">
              {document.text_preview || '（无正文）'}
            </pre>
          </section>
        </>
      ) : null}
    </section>
  )
}