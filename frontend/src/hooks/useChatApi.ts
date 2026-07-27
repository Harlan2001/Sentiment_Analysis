import { useState, useCallback, useRef } from 'react'
import { sendChatMessage, sendChatMessageStream, sendChatMessageStreamLegacy } from '../api'
import type {
  ChatMessage,
  ChatResponse,
  AgentMessage,
  ToolCall,
  ToolCallResult,
} from '../types'
import { TOOL_DISPLAY_NAMES, TOOL_ICONS } from '../constants'

// 重新导出 API 函数
export { sendChatMessage, sendChatMessageStream }

// ========== 基础聊天 Hook（非流式） ==========
export const useChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return

    const userMessage: ChatMessage = { role: 'user', content: content.trim() }
    const newMessages = [...messages, userMessage]
    setMessages(newMessages)
    setIsLoading(true)
    setError(null)

    try {
      const response = await sendChatMessage(newMessages)

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.content || '',
      }
      setMessages(prev => [...prev, assistantMessage])
      return response
    } catch (err) {
      const errorMessage = (err as Error)?.message || '发送消息失败'
      setError(errorMessage)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [messages, isLoading])

  const clearMessages = useCallback(() => {
    setMessages([])
    setError(null)
  }, [])

  return { messages, isLoading, error, sendMessage, clearMessages }
}

// ========== 流式聊天 Hook（旧版兼容） ==========
export const useStreamingChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentMessage, setCurrentMessage] = useState('')
  const [error, setError] = useState<string | null>(null)

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isStreaming) return

    const userMessage: ChatMessage = { role: 'user', content: content.trim() }
    const newMessages = [...messages, userMessage]
    setMessages(newMessages)
    setIsStreaming(true)
    setCurrentMessage('')
    setError(null)

    try {
      let fullResponse = ''
      await sendChatMessageStreamLegacy(
        newMessages,
        (chunk) => {
          fullResponse += chunk
          setCurrentMessage(fullResponse)
        },
        () => {
          setMessages(prev => [...prev, { role: 'assistant', content: fullResponse }])
          setCurrentMessage('')
          setIsStreaming(false)
        },
        (errorMessage) => {
          setError(errorMessage)
          setIsStreaming(false)
          setCurrentMessage('')
        },
      )
      return fullResponse
    } catch (err) {
      const errorMessage = (err as Error)?.message || '发送消息失败'
      setError(errorMessage)
      setIsStreaming(false)
      setCurrentMessage('')
      throw err
    }
  }, [messages, isStreaming])

  const clearMessages = useCallback(() => {
    setMessages([])
    setCurrentMessage('')
    setError(null)
  }, [])

  const stopStreaming = useCallback(() => {
    setIsStreaming(false)
    setCurrentMessage('')
  }, [])

  return { messages, isStreaming, currentMessage, error, sendMessage, clearMessages, stopStreaming }
}

// ========== 聊天历史管理 Hook ==========
export const useChatHistory = (maxHistory = 50) => {
  const [histories, setHistories] = useState<Record<string, ChatMessage[]>>({})
  const [currentHistoryId, setCurrentHistoryId] = useState<string>('default')

  const saveHistory = useCallback((historyId: string, messages: ChatMessage[]) => {
    setHistories(prev => ({
      ...prev,
      [historyId]: messages.slice(-maxHistory),
    }))
  }, [maxHistory])

  const loadHistory = useCallback((historyId: string) => {
    setCurrentHistoryId(historyId)
    return histories[historyId] || []
  }, [histories])

  const deleteHistory = useCallback((historyId: string) => {
    setHistories(prev => {
      const newHistories = { ...prev }
      delete newHistories[historyId]
      return newHistories
    })
    if (currentHistoryId === historyId) setCurrentHistoryId('default')
  }, [currentHistoryId])

  const getAllHistories = useCallback(() => {
    return Object.entries(histories).map(([id, msgs]) => ({
      id,
      messages: msgs,
      title: msgs.find(m => m.role === 'user')?.content.slice(0, 50) || '新对话',
      createdAt: new Date().toISOString(),
      messageCount: msgs.length,
    }))
  }, [histories])

  return { histories, currentHistoryId, saveHistory, loadHistory, deleteHistory, getAllHistories }
}

// ========== 工具调用 Hook（旧版兼容，mock） ==========
export const useChatTools = () => {
  const [availableTools, setAvailableTools] = useState<string[]>([])
  const [toolResults, setToolResults] = useState<any[]>([])

  const enableTool = useCallback((toolName: string) => {
    setAvailableTools(prev => [...new Set([...prev, toolName])])
  }, [])
  const disableTool = useCallback((toolName: string) => {
    setAvailableTools(prev => prev.filter(t => t !== toolName))
  }, [])
  const addToolResult = useCallback((result: any) => {
    setToolResults(prev => [...prev, { ...result, timestamp: new Date().toISOString() }])
  }, [])
  const clearToolResults = useCallback(() => setToolResults([]), [])

  return { availableTools, toolResults, enableTool, disableTool, addToolResult, clearToolResults }
}

// ========== Agent 配置 Hook（旧版兼容） ==========
export const useChatAgents = () => {
  const agents = [
    {
      id: 'general', name: '通用助手', description: '综合性债券市场分析助手',
      systemPrompt: '你是一个专业的债券市场分析助手...',
      tools: ['news_search', 'factor_analysis', 'yield_query'],
    },
    {
      id: 'technical', name: '技术分析', description: '专注于技术指标和图表分析',
      systemPrompt: '你是一个专业的债券技术分析助手...',
      tools: ['technical_analysis', 'chart_generation', 'pattern_recognition'],
    },
    {
      id: 'fundamental', name: '基本面分析', description: '深度基本面研究和宏观经济分析',
      systemPrompt: '你是一个专业的债券基本面分析助手...',
      tools: ['macro_analysis', 'policy_analysis', 'industry_research'],
    },
    {
      id: 'risk', name: '风险管理', description: '风险评估和投资组合管理',
      systemPrompt: '你是一个专业的债券风险管理助手...',
      tools: ['risk_assessment', 'portfolio_optimization', 'stress_testing'],
    },
    {
      id: 'news', name: '新闻分析', description: '实时新闻监控和市场情绪分析',
      systemPrompt: '你是一个专业的债券新闻分析助手...',
      tools: ['news_search', 'sentiment_analysis', 'event_tracking'],
    },
  ]

  const getAgentById = useCallback((id: string) => agents.find(a => a.id === id), [])
  const getAgentTools = useCallback((id: string) => getAgentById(id)?.tools || [], [getAgentById])

  return { agents, getAgentById, getAgentTools }
}

// ═══════════════════════════════════════════════════════════════════════
// 新版：统一 Agent Chat Hook
// ═══════════════════════════════════════════════════════════════════════

export const useAgentChat = () => {
  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [thinking, setThinking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 流式进行中的临时消息
  const [streaming, setStreaming] = useState<{
    content: string
    thinking: boolean
    toolCalls: ToolCall[]
    toolResults: ToolCallResult[]
  } | null>(null)

  const abortRef = useRef<AbortController | null>(null)

  // 用 ref 持有 streaming 内容快照，避免在 setStreaming updater 里嵌套 setMessages
  const streamSnapRef = useRef<{
    content: string
    toolCalls: ToolCall[]
    toolResults: ToolCallResult[]
  }>({ content: '', toolCalls: [], toolResults: [] })

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isProcessing) return

    const userMsg: AgentMessage = { role: 'user', content: content.trim() }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setIsProcessing(true)
    setThinking(false)
    setError(null)

    // 初始化流式状态 & 快照
    streamSnapRef.current = { content: '', toolCalls: [], toolResults: [] }
    setStreaming({
      content: '',
      thinking: true,
      toolCalls: [],
      toolResults: [],
    })

    try {
      // 构建 API 所需的消息格式
      const apiMessages = newMessages.map(m => ({
        role: m.role,
        content: m.content,
      }))

      await sendChatMessageStream(apiMessages, {
        onThinking: () => {
          setStreaming(prev => prev ? { ...prev, thinking: true } : null)
        },
        onContent: (chunk) => {
          streamSnapRef.current.content += chunk
          setStreaming(prev =>
            prev
              ? { ...prev, content: prev.content + chunk, thinking: false }
              : { content: chunk, thinking: false, toolCalls: [], toolResults: [] }
          )
        },
        onToolCall: (toolCalls) => {
          const tcResults: ToolCallResult[] = toolCalls.map(tc => ({
            toolCallId: tc.id,
            toolName: tc.name,
            toolDisplayName: TOOL_DISPLAY_NAMES[tc.name] || tc.name,
            toolIcon: TOOL_ICONS[tc.name] || '🔧',
            input: tc.arguments,
            status: 'pending' as const,
            collapsed: true,
          }))
          streamSnapRef.current.toolCalls = toolCalls
          streamSnapRef.current.toolResults = tcResults
          setStreaming(prev =>
            prev
              ? { ...prev, toolCalls: toolCalls, toolResults: tcResults, thinking: false }
              : { content: '', thinking: false, toolCalls: toolCalls, toolResults: tcResults }
          )
        },
        onToolExecuting: (toolCallId) => {
          setStreaming(prev => {
            if (!prev) return null
            return {
              ...prev,
              toolResults: prev.toolResults.map(tr =>
                tr.toolCallId === toolCallId ? { ...tr, status: 'executing' as const } : tr
              ),
            }
          })
        },
        onToolResult: (toolCallId, toolName, result, err, durationMs) => {
          setStreaming(prev => {
            if (!prev) return null
            const updated = prev.toolResults.map(tr =>
              tr.toolCallId === toolCallId
                ? {
                    ...tr,
                    status: err ? ('error' as const) : ('success' as const),
                    output: result ?? undefined,
                    error: err ?? undefined,
                    durationMs: durationMs ?? 0,
                  }
                : tr
            )
            streamSnapRef.current.toolResults = updated
            return { ...prev, toolResults: updated }
          })
        },
        onDone: () => {
          // 从 ref 快照构建最终消息（避免在 setStreaming updater 内嵌套 setMessages）
          const snap = streamSnapRef.current
          const assistantMsg: AgentMessage = {
            role: 'assistant',
            content: snap.content,
            toolCalls: snap.toolCalls.length > 0 ? snap.toolCalls : undefined,
            toolResults: snap.toolResults.length > 0 ? snap.toolResults : undefined,
          }
          setMessages(prev => [...prev, assistantMsg])
          setStreaming(null)
          setIsProcessing(false)
          setThinking(false)
        },
        onError: (message) => {
          setError(message)
          setIsProcessing(false)
          setThinking(false)
          setStreaming(null)
        },
      })
    } catch (err) {
      setError((err as Error)?.message || '发送消息失败')
      setIsProcessing(false)
      setThinking(false)
      setStreaming(null)
    }
  }, [messages, isProcessing])

  const clearMessages = useCallback(() => {
    setMessages([])
    setStreaming(null)
    setThinking(false)
    setError(null)
    setIsProcessing(false)
  }, [])

  const stopProcessing = useCallback(() => {
    setIsProcessing(false)
    setStreaming(null)
    setThinking(false)
  }, [])

  return {
    messages,
    isProcessing,
    thinking,
    streaming,
    error,
    sendMessage,
    clearMessages,
    stopProcessing,
  }
}
