import { useState, useCallback } from 'react'
import { sendChatMessage, sendChatMessageStream } from '../api'
import type { ChatMessage, ChatResponse } from '../types'

// 导出API函数供外部使用
export { sendChatMessage, sendChatMessageStream }

// 基础聊天Hook
export const useChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const sendMessage = useCallback(async (content: string, enableTools = false) => {
    if (!content.trim() || isLoading) return
    
    const userMessage: ChatMessage = {
      role: 'user',
      content: content.trim()
    }
    
    const newMessages = [...messages, userMessage]
    setMessages(newMessages)
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await sendChatMessage(newMessages, enableTools)
      
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.content || ''
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
  
  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages
  }
}

// 流式聊天Hook
export const useStreamingChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentMessage, setCurrentMessage] = useState('')
  const [error, setError] = useState<string | null>(null)
  
  const sendMessage = useCallback(async (content: string, enableTools = false) => {
    if (!content.trim() || isStreaming) return
    
    const userMessage: ChatMessage = {
      role: 'user',
      content: content.trim()
    }
    
    const newMessages = [...messages, userMessage]
    setMessages(newMessages)
    setIsStreaming(true)
    setCurrentMessage('')
    setError(null)
    
    try {
      let fullResponse = ''
      
      await sendChatMessageStream(
        newMessages,
        (chunk) => {
          fullResponse += chunk
          setCurrentMessage(fullResponse)
        },
        () => {
          const assistantMessage: ChatMessage = {
            role: 'assistant',
            content: fullResponse
          }
          setMessages(prev => [...prev, assistantMessage])
          setCurrentMessage('')
          setIsStreaming(false)
        },
        (errorMessage) => {
          setError(errorMessage)
          setIsStreaming(false)
          setCurrentMessage('')
        },
        enableTools
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
  
  return {
    messages,
    isStreaming,
    currentMessage,
    error,
    sendMessage,
    clearMessages,
    stopStreaming
  }
}

// 聊天历史管理Hook
export const useChatHistory = (maxHistory = 50) => {
  const [histories, setHistories] = useState<Record<string, ChatMessage[]>>({})
  const [currentHistoryId, setCurrentHistoryId] = useState<string>('default')
  
  const saveHistory = useCallback((historyId: string, messages: ChatMessage[]) => {
    setHistories(prev => ({
      ...prev,
      [historyId]: messages.slice(-maxHistory)
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
    
    if (currentHistoryId === historyId) {
      setCurrentHistoryId('default')
    }
  }, [currentHistoryId])
  
  const getAllHistories = useCallback(() => {
    return Object.entries(histories).map(([id, messages]) => ({
      id,
      messages,
      title: messages.find(m => m.role === 'user')?.content.slice(0, 50) || '新对话',
      createdAt: new Date().toISOString(),
      messageCount: messages.length
    }))
  }, [histories])
  
  return {
    histories,
    currentHistoryId,
    saveHistory,
    loadHistory,
    deleteHistory,
    getAllHistories
  }
}

// 工具调用Hook
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
    setToolResults(prev => [...prev, {
      ...result,
      timestamp: new Date().toISOString()
    }])
  }, [])
  
  const clearToolResults = useCallback(() => {
    setToolResults([])
  }, [])
  
  return {
    availableTools,
    toolResults,
    enableTool,
    disableTool,
    addToolResult,
    clearToolResults
  }
}

// Agent配置Hook
export const useChatAgents = () => {
  const agents = [
    {
      id: 'general',
      name: '通用助手',
      description: '综合性债券市场分析助手',
      systemPrompt: '你是一个专业的债券市场分析助手，可以回答关于债券市场、收益率分析、宏观经济等各类问题。',
      tools: ['news_search', 'factor_analysis', 'yield_query']
    },
    {
      id: 'technical',
      name: '技术分析',
      description: '专注于技术指标和图表分析',
      systemPrompt: '你是一个专业的债券技术分析助手，专注于技术指标分析、图表形态识别、支撑阻力位分析等。',
      tools: ['technical_analysis', 'chart_generation', 'pattern_recognition']
    },
    {
      id: 'fundamental',
      name: '基本面分析',
      description: '深度基本面研究和宏观经济分析',
      systemPrompt: '你是一个专业的债券基本面分析助手，专注于宏观经济分析、政策解读、行业研究等。',
      tools: ['macro_analysis', 'policy_analysis', 'industry_research']
    },
    {
      id: 'risk',
      name: '风险管理',
      description: '风险评估和投资组合管理',
      systemPrompt: '你是一个专业的债券风险管理助手，专注于风险评估、投资组合优化、压力测试等。',
      tools: ['risk_assessment', 'portfolio_optimization', 'stress_testing']
    },
    {
      id: 'news',
      name: '新闻分析',
      description: '实时新闻监控和市场情绪分析',
      systemPrompt: '你是一个专业的债券新闻分析助手，专注于新闻监控、市场情绪分析、事件跟踪等。',
      tools: ['news_search', 'sentiment_analysis', 'event_tracking']
    }
  ]
  
  const getAgentById = useCallback((id: string) => {
    return agents.find(agent => agent.id === id)
  }, [])
  
  const getAgentTools = useCallback((id: string) => {
    const agent = getAgentById(id)
    return agent?.tools || []
  }, [getAgentById])
  
  return {
    agents,
    getAgentById,
    getAgentTools
  }
}