import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type {
  GraphAugmentResult,
  GraphAugmentExtractResult,
  GraphAugmentStatus,
  GraphAugmentJob,
  GraphAugmentStartResponse,
  GraphAugmentStatusResponse,
} from '../types'
import {
  startGraphAugment,
  getGraphAugmentStatus,
  getGraphAugmentResult,
  getGraphAugmentExtract,
  getGraphAugmentJobByNews,
  saveGraphAugmentResult,
  connectGraphAugmentStream,
} from '../api'

export function useGraphAugmentJob(newsId: number) {
  const { data, ...rest } = useQuery({
    queryKey: ['graphAugment', 'job', newsId],
    queryFn: () => getGraphAugmentJobByNews(newsId),
    enabled: newsId > 0,
    staleTime: 5 * 60 * 1000,
  })

  return {
    job: data?.job || null,
    ...rest,
  }
}

export interface UseGraphAugmentOptions {
  newsId: number
  newsContent: string
  onComplete?: (result: GraphAugmentResult) => void
}

export function useGraphAugment({ newsId, newsContent, onComplete }: UseGraphAugmentOptions) {
  const [runId, setRunId] = useState<string | null>(null)
  const [status, setStatus] = useState<GraphAugmentStatus | null>(null)
  const [stage, setStage] = useState<string | null>(null)
  const [progressMessages, setProgressMessages] = useState<string[]>([])
  const [result, setResult] = useState<GraphAugmentResult | null>(null)
  const [extract, setExtract] = useState<GraphAugmentExtractResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [eventSource, setEventSource] = useState<EventSource | null>(null)

  const queryClient = useQueryClient()

  // 轮询状态
  useEffect(() => {
    if (!runId || status === 'COMPLETED' || status === 'FAILED' || status === 'REJECTED') {
      return
    }

    const interval = setInterval(async () => {
      try {
        const data = await getGraphAugmentStatus(runId)
        setStatus(data.status)
        setStage(data.stage)

        if (data.status === 'COMPLETED' || data.status === 'WAITING_REVIEW') {
          // 获取结果
          const [resultData, extractData] = await Promise.all([
            getGraphAugmentResult(runId),
            getGraphAugmentExtract(runId),
          ])
          setResult(resultData)
          setExtract(extractData)

          // 保存到数据库
          await saveGraphAugmentResult(newsId, runId, data.status, data.stage, resultData, extractData)
          
          // 使缓存失效
          queryClient.invalidateQueries({ queryKey: ['graphAugment', 'job', newsId] })
          
          if (onComplete) {
            onComplete(resultData)
          }

          // 关闭 SSE
          if (eventSource) {
            eventSource.close()
            setEventSource(null)
          }

          setIsLoading(false)
        } else if (data.status === 'FAILED' || data.status === 'REJECTED') {
          setError(`任务${data.status === 'FAILED' ? '失败' : '被拒绝'}`)
          setIsLoading(false)
          if (eventSource) {
            eventSource.close()
            setEventSource(null)
          }
        }
      } catch (err) {
        console.error('轮询状态失败:', err)
      }
    }, 10000) // 每 10 秒轮询一次

    return () => clearInterval(interval)
  }, [runId, status, eventSource, newsId, onComplete, queryClient])

  // SSE 实时进度
  useEffect(() => {
    if (!runId || status === 'COMPLETED' || status === 'FAILED' || status === 'REJECTED') {
      return
    }

    const es = connectGraphAugmentStream(runId)
    setEventSource(es)

    es.addEventListener('extract_thinking_delta', (event) => {
      setProgressMessages(prev => [...prev, `[抽取] ${event.data}`])
    })

    es.addEventListener('similarity_audit_thinking_delta', (event) => {
      setProgressMessages(prev => [...prev, `[相似度复核] ${event.data}`])
    })

    es.addEventListener('augment_thinking_delta', (event) => {
      setProgressMessages(prev => [...prev, `[补全] ${event.data}`])
    })

    es.onerror = (error) => {
      console.error('SSE error:', error)
      es.close()
    }

    return () => {
      es.close()
    }
  }, [runId, status])

  const start = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      setProgressMessages([])
      setResult(null)
      setExtract(null)

      const response: GraphAugmentStartResponse = await startGraphAugment(newsContent.trim())
      setRunId(response.runId)
      setStatus('RUNNING')
      setStage('extract')
    } catch (err) {
      setError(err instanceof Error ? err.message : '启动任务失败')
      setIsLoading(false)
    }
  }, [newsContent])

  const stop = useCallback(() => {
    if (eventSource) {
      eventSource.close()
      setEventSource(null)
    }
    setIsLoading(false)
  }, [eventSource])

  // 从已有 job 加载
  const loadFromJob = useCallback((job: GraphAugmentJob) => {
    setRunId(job.run_id)
    setStatus(job.status)
    setStage(job.stage)
    setResult(job.result_json)
    setExtract(job.extract_json)
  }, [])

  return {
    start,
    stop,
    isLoading,
    runId,
    status,
    stage,
    progressMessages,
    result,
    extract,
    error,
    loadFromJob,
  }
}
