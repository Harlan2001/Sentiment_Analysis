import React, { useState, useRef, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, Button, Input, Loading, Error } from '../UI'
import { sendChatMessage, sendChatMessageStream } from '../../hooks/useChatApi'
import { cn, formatDate, copyToClipboard } from '../../utils/helpers'
import type { ChatMessage } from '../../types'

const AgentPage: React.FC = () => {
  // 状态管理
  const [selectedAgent, setSelectedAgent] = useState<string>('general')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('')
  const [error, setError] = useState<string | null>(null)
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  
  // Agent定义
  const agents = [
    {
      id: 'general',
      name: '通用助手',
      description: '综合性债券市场分析助手，可以回答各类问题',
      avatar: '🤖',
      color: 'blue',
      capabilities: ['市场分析', '新闻解读', '数据查询', '趋势预测']
    },
    {
      id: 'technical',
      name: '技术分析',
      description: '专注于技术指标和图表分析',
      avatar: '📈',
      color: 'green',
      capabilities: ['技术指标', '图表分析', '支撑阻力', '形态识别']
    },
    {
      id: 'fundamental',
      name: '基本面分析',
      description: '深度基本面研究和宏观经济分析',
      avatar: '🏛️',
      color: 'purple',
      capabilities: ['宏观经济', '政策解读', '行业分析', '公司研究']
    },
    {
      id: 'risk',
      name: '风险管理',
      description: '风险评估和投资组合管理',
      avatar: '🛡️',
      color: 'orange',
      capabilities: ['风险评估', '组合优化', '压力测试', '合规检查']
    },
    {
      id: 'news',
      name: '新闻分析',
      description: '实时新闻监控和市场情绪分析',
      avatar: '📰',
      color: 'red',
      capabilities: ['新闻监控', '情绪分析', '事件跟踪', '影响评估']
    }
  ]
  
  const currentAgent = agents.find(a => a.id === selectedAgent) || agents[0]
  
  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }
  
  useEffect(() => {
    scrollToBottom()
  }, [messages, currentStreamingMessage])
  
  // 获取Agent颜色样式
  const getAgentColorClasses = (color: string) => {
    const colorMap = {
      blue: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      green: 'bg-green-500/20 text-green-400 border-green-500/30',
      purple: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
      orange: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
      red: 'bg-red-500/20 text-red-400 border-red-500/30',
    }
    return colorMap[color as keyof typeof colorMap] || colorMap.blue
  }
  
  // 发送消息
  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isStreaming) return
    
    const userMessage: ChatMessage = {
      role: 'user',
      content: inputMessage.trim()
    }
    
    const newMessages = [...messages, userMessage]
    setMessages(newMessages)
    setInputMessage('')
    setError(null)
    setIsStreaming(true)
    setCurrentStreamingMessage('')
    
    try {
      let fullResponse = ''
      
      await sendChatMessageStream(
        [...newMessages],
        (chunk: string) => {
          fullResponse += chunk
          setCurrentStreamingMessage(fullResponse)
        },
        () => {
          const assistantMessage: ChatMessage = {
            role: 'assistant',
            content: fullResponse
          }
          setMessages(prev => [...prev, assistantMessage])
          setCurrentStreamingMessage('')
          setIsStreaming(false)
        },
        (error: string) => {
          setError(error)
          setIsStreaming(false)
          setCurrentStreamingMessage('')
        },
        true // 启用工具调用
      )
    } catch (error) {
      setError('发送消息失败，请重试')
      setIsStreaming(false)
      setCurrentStreamingMessage('')
    }
  }
  
  // 处理键盘事件
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }
  
  // 清除对话
  const handleClearMessages = () => {
    setMessages([])
    setCurrentStreamingMessage('')
    setError(null)
  }
  
  // 复制消息
  const handleCopyMessage = async (content: string) => {
    const success = await copyToClipboard(content)
    if (success) {
      // 可以显示复制成功的提示
      console.log('消息已复制到剪贴板')
    }
  }
  
  // 消息组件
  const MessageBubble: React.FC<{ message: ChatMessage }> = ({ message }) => (
    <div className={cn(
      "flex gap-3",
      message.role === 'user' ? "justify-end" : "justify-start"
    )}>
      {message.role === 'assistant' && (
        <div className={cn(
          "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
          getAgentColorClasses(currentAgent.color)
        )}>
          <span className="text-sm">{currentAgent.avatar}</span>
        </div>
      )}
      
      <div className={cn(
        "max-w-[80%] px-4 py-3 rounded-lg",
        message.role === 'user'
          ? "bg-purple-500 text-white"
          : "bg-gray-800 text-gray-200 border border-gray-700"
      )}>
        <div className="text-sm leading-relaxed whitespace-pre-wrap">
          {message.content}
        </div>
        
        <div className="flex items-center gap-2 mt-2">
          <span className="text-xs opacity-70">
            {formatDate(new Date(), 'HH:mm')}
          </span>
          
          <button
            onClick={() => handleCopyMessage(message.content)}
            className="text-xs opacity-70 hover:opacity-100 transition-opacity"
          >
            复制
          </button>
        </div>
      </div>
      
      {message.role === 'user' && (
        <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center flex-shrink-0">
          <span className="text-sm text-white">👤</span>
        </div>
      )}
    </div>
  )
  
  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div className="page-header">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-2">
          🤖 智能助手
        </h1>
        <p className="text-gray-400 text-sm">
          选择不同的AI助手获取专业分析
        </p>
      </div>
      
      {/* Agent选择 */}
      <Card>
        <CardHeader>
          <CardTitle>选择助手</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent) => (
              <div
                key={agent.id}
                onClick={() => setSelectedAgent(agent.id)}
                className={cn(
                  "p-4 rounded-lg border cursor-pointer transition-all",
                  selectedAgent === agent.id
                    ? getAgentColorClasses(agent.color)
                    : "border-gray-700 hover:border-gray-600 hover:bg-gray-800/50"
                )}
              >
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-2xl">{agent.avatar}</span>
                  <h3 className="font-medium text-white">{agent.name}</h3>
                </div>
                
                <p className="text-sm text-gray-400 mb-3">
                  {agent.description}
                </p>
                
                <div className="flex flex-wrap gap-1">
                  {agent.capabilities.map((capability) => (
                    <span
                      key={capability}
                      className="text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded"
                    >
                      {capability}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      
      {/* 聊天界面 */}
      <Card className="h-[600px] flex flex-col">
        <CardHeader className="flex-shrink-0">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <span className="text-xl">{currentAgent.avatar}</span>
              {currentAgent.name}
              <span className="text-sm font-normal text-gray-400">
                • {messages.length} 条对话
              </span>
            </CardTitle>
            
            <div className="flex items-center gap-2">
              {messages.length > 0 && (
                <Button variant="outline" size="sm" onClick={handleClearMessages}>
                  清除对话
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        
        {/* 消息列表 */}
        <CardContent className="flex-1 overflow-hidden">
          <div className="h-full flex flex-col">
            <div className="flex-1 overflow-y-auto space-y-4 pr-2">
              {messages.length === 0 && !isStreaming && (
                <div className="text-center py-8">
                  <span className="text-4xl mb-4 block">{currentAgent.avatar}</span>
                  <h3 className="text-lg font-medium text-white mb-2">
                    与 {currentAgent.name} 开始对话
                  </h3>
                  <p className="text-sm text-gray-400 max-w-md mx-auto">
                    {currentAgent.description}
                  </p>
                </div>
              )}
              
              {messages.map((message, index) => (
                <MessageBubble key={index} message={message} />
              ))}
              
              {/* 流式响应 */}
              {isStreaming && currentStreamingMessage && (
                <div className="flex gap-3">
                  <div className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                    getAgentColorClasses(currentAgent.color)
                  )}>
                    <span className="text-sm">{currentAgent.avatar}</span>
                  </div>
                  
                  <div className="max-w-[80%] px-4 py-3 rounded-lg bg-gray-800 text-gray-200 border border-gray-700">
                    <div className="text-sm leading-relaxed whitespace-pre-wrap">
                      {currentStreamingMessage}
                      <span className="inline-block w-2 h-4 bg-gray-400 ml-1 animate-pulse"></span>
                    </div>
                  </div>
                </div>
              )}
              
              {isStreaming && !currentStreamingMessage && (
                <div className="flex gap-3">
                  <div className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                    getAgentColorClasses(currentAgent.color)
                  )}>
                    <span className="text-sm">{currentAgent.avatar}</span>
                  </div>
                  
                  <div className="max-w-[80%] px-4 py-3 rounded-lg bg-gray-800 border border-gray-700">
                    <Loading text="思考中..." />
                  </div>
                </div>
              )}
              
              {error && (
                <Error title="错误" message={error} />
              )}
              
              <div ref={messagesEndRef} />
            </div>
          </div>
        </CardContent>
        
        {/* 输入区域 */}
        <div className="p-4 border-t border-gray-700">
          <div className="flex gap-3">
            <div className="flex-1">
              <textarea
                ref={inputRef}
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={`向 ${currentAgent.name} 提问...`}
                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 resize-none focus:border-purple-500 focus:outline-none"
                rows={2}
                disabled={isStreaming}
              />
            </div>
            
            <Button
              onClick={handleSendMessage}
              disabled={!inputMessage.trim() || isStreaming}
              loading={isStreaming}
            >
              发送
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default AgentPage