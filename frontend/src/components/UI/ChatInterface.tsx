import React, { useState, useRef, useEffect } from 'react'
import Button from '../UI/Button'
import { Input } from '../UI/Input'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  agentId: string
}

interface Agent {
  id: string
  name: string
  description: string
  avatar: string
  capabilities: string[]
}

const agents: Agent[] = [
  {
    id: 'market-analyst',
    name: '市场分析师',
    description: '专业债券市场分析，政策解读，趋势预测',
    avatar: '📊',
    capabilities: ['市场分析', '政策解读', '趋势预测', '风险评估']
  },
  {
    id: 'sentiment-expert',
    name: '情感分析专家',
    description: '新闻情感分析，舆情监控，热点追踪',
    avatar: '🔍',
    capabilities: ['情感分析', '舆情监控', '热点追踪', '新闻聚合']
  },
  {
    id: 'risk-advisor',
    name: '风险顾问',
    description: '信用风险评估，投资组合优化，预警提示',
    avatar: '⚠️',
    capabilities: ['信用评估', '组合优化', '风险预警', '合规检查']
  },
  {
    id: 'data-scientist',
    name: '数据科学家',
    description: '量化分析，模型训练，因子挖掘',
    avatar: '🧮',
    capabilities: ['量化分析', '模型训练', '因子挖掘', '回测验证']
  }
]

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [selectedAgent, setSelectedAgent] = useState<Agent>(agents[0])
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
      agentId: selectedAgent.id
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    // Simulate AI response
    setTimeout(() => {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `我是${selectedAgent.name}。针对您的问题"${userMessage.content}"，我正在为您分析相关数据并提供专业见解。${selectedAgent.capabilities.slice(0, 2).join('、')}是我的专长领域。`,
        timestamp: new Date(),
        agentId: selectedAgent.id
      }
      setMessages(prev => [...prev, assistantMessage])
      setIsLoading(false)
    }, 1000 + Math.random() * 2000)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className="flex h-[600px] bg-gray-900/50 rounded-xl border border-gray-700 overflow-hidden">
      {/* Agent Sidebar */}
      <div className="w-80 border-r border-gray-700 p-4">
        <h3 className="text-lg font-semibold text-white mb-4">选择AI助手</h3>
        <div className="space-y-3">
          {agents.map(agent => (
            <div
              key={agent.id}
              className={`p-3 rounded-lg border cursor-pointer transition-all ${
                selectedAgent.id === agent.id
                  ? 'bg-purple-500/20 border-purple-500'
                  : 'bg-gray-800 border-gray-600 hover:border-gray-500'
              }`}
              onClick={() => setSelectedAgent(agent)}
            >
              <div className="flex items-center gap-3 mb-2">
                <span className="text-2xl">{agent.avatar}</span>
                <div>
                  <h4 className="font-medium text-white">{agent.name}</h4>
                  <p className="text-xs text-gray-400">{agent.description}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {agent.capabilities.map(cap => (
                  <span
                    key={cap}
                    className="px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded"
                  >
                    {cap}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Chat Header */}
        <div className="p-4 border-b border-gray-700 bg-gray-800/50">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{selectedAgent.avatar}</span>
            <div>
              <h3 className="font-semibold text-white">{selectedAgent.name}</h3>
              <p className="text-sm text-gray-400">{selectedAgent.description}</p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center py-8">
              <div className="text-4xl mb-4">{selectedAgent.avatar}</div>
              <h3 className="text-lg font-medium text-white mb-2">
                与{selectedAgent.name}对话
              </h3>
              <p className="text-gray-400 text-sm">
                {selectedAgent.capabilities.join('、')}等专业服务
              </p>
            </div>
          ) : (
            messages.map(message => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[70%] rounded-lg px-4 py-3 ${
                    message.role === 'user'
                      ? 'bg-purple-500 text-white'
                      : 'bg-gray-800 text-gray-100 border border-gray-600'
                  }`}
                >
                  <div className="text-sm">{message.content}</div>
                  <div className="text-xs opacity-70 mt-1">
                    {message.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))
          )}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 text-gray-100 border border-gray-600 rounded-lg px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  <span className="text-sm text-gray-400 ml-2">正在思考...</span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-gray-700 bg-gray-800/50">
          <div className="flex gap-2">
            <Input
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder={`向${selectedAgent.name}提问...`}
              className="flex-1"
              disabled={isLoading}
            />
            <Button
              onClick={handleSendMessage}
              disabled={isLoading || !inputValue.trim()}
              className="px-6"
            >
              发送
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}