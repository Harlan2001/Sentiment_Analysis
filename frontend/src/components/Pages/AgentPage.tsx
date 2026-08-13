import React, { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Card, CardContent, CardHeader, CardTitle, Button } from '@/components/UI'
import { useAgentChat } from '@/hooks/useChatApi'
import { cn, formatDate, copyToClipboard } from '@/utils/helpers'
import { TOOL_DISPLAY_NAMES, TOOL_ICONS } from '@/constants'
import type { AgentMessage, ToolCall, ToolCallResult, AgentSkill } from '@/types'

// ═══════════════════════════════════════════════════════════════════════
// Skills 定义
// ═══════════════════════════════════════════════════════════════════════

const SKILLS: AgentSkill[] = [
  { name: '新闻搜索', description: '按关键词、日期搜索债券市场新闻', icon: '📰', category: 'news' },
  { name: '新闻详情', description: '查看新闻全文及关联分析因子', icon: '🔍', category: 'news' },
  { name: '相似新闻', description: '语义搜索历史上相似的新闻事件', icon: '🔗', category: 'news' },
  { name: '因子分析', description: '列出和分析债券市场影响因子', icon: '📊', category: 'analysis' },
  { name: '因子新闻', description: '查询特定因子相关的新闻事件', icon: '🏷️', category: 'analysis' },
  { name: '收益率曲线', description: '获取历史国债收益率数据', icon: '📈', category: 'data' },
  { name: '宏观信号', description: '计算因子的宏观信号（存在性/方向性）', icon: '⚡', category: 'analysis' },
  { name: '预测报告', description: '查看 AI 生成的市场分析预测', icon: '🔮', category: 'market' },
]

const SUGGESTED_QUESTIONS = [
  '今天有哪些重要的债券市场新闻？',
  '最近关于降息的新闻有哪些？',
  'MLF利率因子最近的信号如何？',
  '10年期国债收益率最近走势怎么样？',
]

// ═══════════════════════════════════════════════════════════════════════
// Skill 卡片组件
// ═══════════════════════════════════════════════════════════════════════

const SkillCard: React.FC<{ skill: AgentSkill }> = ({ skill }) => {
  const categoryColors: Record<string, string> = {
    news: 'from-blue-500/20 to-blue-600/10 border-blue-500/30',
    analysis: 'from-purple-500/20 to-purple-600/10 border-purple-500/30',
    data: 'from-green-500/20 to-green-600/10 border-green-500/30',
    market: 'from-orange-500/20 to-orange-600/10 border-orange-500/30',
  }

  return (
    <div
      className={cn(
        'p-3 rounded-lg border bg-gradient-to-br transition-all duration-200',
        'hover:scale-[1.02] hover:shadow-lg cursor-default',
        categoryColors[skill.category] || categoryColors.news
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{skill.icon}</span>
        <span className="text-sm font-medium text-white">{skill.name}</span>
      </div>
      <p className="text-xs text-gray-400 leading-relaxed">{skill.description}</p>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════
// 工具调用卡片组件
// ═══════════════════════════════════════════════════════════════════════

const ToolCallCard: React.FC<{ result: ToolCallResult }> = ({ result }) => {
  const [expanded, setExpanded] = useState(false)

  const statusConfig = {
    pending: { icon: '⏳', text: '等待执行', color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
    executing: { icon: '🔄', text: '执行中...', color: 'text-blue-400', bg: 'bg-blue-500/10' },
    success: { icon: '✅', text: '完成', color: 'text-green-400', bg: 'bg-green-500/10' },
    error: { icon: '❌', text: '失败', color: 'text-red-400', bg: 'bg-red-500/10' },
  }
  const config = statusConfig[result.status]

  // 参数摘要：取 1-2 个关键参数
  const argEntries = Object.entries(result.input || {})
  const argSummary = argEntries
    .slice(0, 2)
    .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
    .join(', ')

  return (
    <div className={cn('rounded-lg border border-gray-700 overflow-hidden mb-2', config.bg)}>
      {/* 标题栏 */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-white/5 transition-colors text-left"
      >
        <span className={cn('text-sm', result.status === 'executing' && 'animate-spin')}>{config.icon}</span>
        <span className="text-sm font-medium text-white">
          {result.toolDisplayName || TOOL_DISPLAY_NAMES[result.toolName] || result.toolName}
        </span>
        <span className={cn('text-xs', config.color)}>{config.text}</span>
        {result.durationMs != null && result.durationMs > 0 && (
          <span className="text-xs text-gray-500 ml-auto">
            {result.durationMs < 1000 ? `${result.durationMs}ms` : `${(result.durationMs / 1000).toFixed(1)}s`}
          </span>
        )}
        <span className="text-xs text-gray-500 ml-auto">{expanded ? '收起 ▲' : '展开 ▼'}</span>
      </button>

      {/* 展开区 */}
      {expanded && (
        <div className="px-3 pb-3 border-t border-gray-700/50">
          {/* 参数 */}
          {argSummary && (
            <div className="mt-2">
              <span className="text-xs text-gray-500">参数：</span>
              <span className="text-xs text-gray-300">{argSummary}</span>
            </div>
          )}

          {/* 结果预览 */}
          {result.status === 'success' && result.output && (
            <div className="mt-2">
              <span className="text-xs text-gray-500 block mb-1">结果：</span>
              {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
              <pre className="text-xs text-gray-300 bg-gray-900/50 rounded p-2 max-h-40 overflow-y-auto whitespace-pre-wrap">
                {typeof result.output === 'string' ? result.output : JSON.stringify(result.output, null, 2)}
              </pre>
            </div>
          )}

          {/* 错误 */}
          {result.status === 'error' && result.error && (
            <div className="mt-2 text-xs text-red-400 bg-red-500/10 rounded p-2">{result.error}</div>
          )}
        </div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════
// Markdown 渲染组件
// ═══════════════════════════════════════════════════════════════════════

const MarkdownBody: React.FC<{ content: string }> = ({ content }) => (
  <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    components={{
      // 自定义暗色主题样式
      h1: ({ children, ...props }) => (
        <h1 className="text-xl font-bold text-white mt-4 mb-2" {...props}>
          {children}
        </h1>
      ),
      h2: ({ children, ...props }) => (
        <h2 className="text-lg font-semibold text-white mt-3 mb-2" {...props}>
          {children}
        </h2>
      ),
      h3: ({ children, ...props }) => (
        <h3 className="text-base font-semibold text-gray-200 mt-3 mb-1" {...props}>
          {children}
        </h3>
      ),
      p: ({ children, ...props }) => (
        <p className="text-sm text-gray-300 leading-relaxed mb-2" {...props}>
          {children}
        </p>
      ),
      ul: ({ children, ...props }) => (
        <ul className="list-disc list-inside text-sm text-gray-300 mb-2 space-y-1" {...props}>
          {children}
        </ul>
      ),
      ol: ({ children, ...props }) => (
        <ol className="list-decimal list-inside text-sm text-gray-300 mb-2 space-y-1" {...props}>
          {children}
        </ol>
      ),
      li: ({ children, ...props }) => (
        <li className="text-sm text-gray-300" {...props}>
          {children}
        </li>
      ),
      strong: ({ children, ...props }) => (
        <strong className="font-semibold text-white" {...props}>
          {children}
        </strong>
      ),
      code: ({ className, children, ...props }) => {
        const isInline = !className
        return isInline ? (
          <code className="px-1 py-0.5 bg-gray-700 text-gray-200 rounded text-xs" {...props}>
            {children}
          </code>
        ) : (
          <code
            className={cn('block p-3 bg-gray-800 text-gray-200 rounded text-xs overflow-x-auto', className)}
            {...props}
          >
            {children}
          </code>
        )
      },
      pre: ({ children, ...props }) => (
        <pre className="bg-gray-800 rounded-lg p-3 overflow-x-auto mb-2" {...props}>
          {children}
        </pre>
      ),
      table: ({ children, ...props }) => (
        <div className="overflow-x-auto mb-2">
          <table className="min-w-full text-sm border-collapse border border-gray-700" {...props}>
            {children}
          </table>
        </div>
      ),
      thead: ({ children, ...props }) => (
        <thead className="bg-gray-800" {...props}>
          {children}
        </thead>
      ),
      th: ({ children, ...props }) => (
        <th className="border border-gray-700 px-3 py-2 text-left text-xs font-medium text-gray-300" {...props}>
          {children}
        </th>
      ),
      td: ({ children, ...props }) => (
        <td className="border border-gray-700 px-3 py-2 text-xs text-gray-400" {...props}>
          {children}
        </td>
      ),
      a: ({ children, href, ...props }) => (
        <a
          className="text-blue-400 hover:text-blue-300 underline"
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          {...props}
        >
          {children}
        </a>
      ),
      blockquote: ({ children, ...props }) => (
        <blockquote className="border-l-2 border-purple-500 pl-3 my-2 text-sm text-gray-400 italic" {...props}>
          {children}
        </blockquote>
      ),
      hr: (props) => <hr className="border-gray-700 my-3" {...props} />,
    }}
  >
    {content}
  </ReactMarkdown>
)

// ═══════════════════════════════════════════════════════════════════════
// AgentPage 主组件
// ═══════════════════════════════════════════════════════════════════════

const AgentPage: React.FC = () => {
  const { messages, isProcessing, thinking, streaming, error, sendMessage, clearMessages, stopProcessing } =
    useAgentChat()

  const [inputMessage, setInputMessage] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming?.content])

  // 聚焦输入框
  useEffect(() => {
    if (!isProcessing) {
      inputRef.current?.focus()
    }
  }, [isProcessing])

  // 发送消息
  const handleSend = useCallback(() => {
    if (!inputMessage.trim() || isProcessing) return
    const content = inputMessage.trim()
    setInputMessage('')
    sendMessage(content)
  }, [inputMessage, isProcessing, sendMessage])

  // 键盘事件
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend]
  )

  // 点击建议问题
  const handleSuggestedQuestion = useCallback(
    (question: string) => {
      setInputMessage(question)
      // 自动发送
      sendMessage(question)
    },
    [sendMessage]
  )

  // 复制消息
  const handleCopy = useCallback(async (content: string) => {
    await copyToClipboard(content)
  }, [])

  const hasContent = messages.length > 0 || streaming !== null

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">🤖 智能分析助手</h1>
          <p className="text-gray-400 text-sm">
            基于 AI 的债券市场智能分析，支持新闻搜索、因子分析、宏观信号、收益率查询
          </p>
        </div>
        {hasContent && (
          <Button variant="outline" size="sm" onClick={clearMessages}>
            清除对话
          </Button>
        )}
      </div>

      {/* 主内容区域 */}
      <div className="grid grid-cols-1 gap-6">
        {/* 欢迎界面 / 聊天区域 */}
        <Card className={cn('flex flex-col', hasContent ? 'h-[650px]' : '')}>
          {!hasContent ? (
            /* ── 欢迎界面 ── */
            <>
              <CardContent className="py-8">
                {/* Agent 介绍 */}
                <div className="text-center mb-8">
                  <div className="text-5xl mb-4">🤖</div>
                  <h2 className="text-2xl font-bold text-white mb-2">智能分析助手</h2>
                  <p className="text-gray-400 max-w-lg mx-auto text-sm leading-relaxed">
                    我可以帮你分析债券市场——搜索新闻、查询因子、计算宏观信号、查看收益率走势。
                    <br />
                    直接提问，我会自动调用合适的工具来获取数据。
                  </p>
                </div>

                {/* Skills 网格 */}
                <div className="mb-8">
                  <h3 className="text-sm font-medium text-gray-300 mb-3 text-center">🛠️ 我能做什么</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {SKILLS.map((skill) => (
                      <SkillCard key={skill.name} skill={skill} />
                    ))}
                  </div>
                </div>

                {/* 建议问题 */}
                <div>
                  <h3 className="text-sm font-medium text-gray-300 mb-3 text-center">💡 试试这些问题</h3>
                  <div className="flex flex-wrap justify-center gap-2">
                    {SUGGESTED_QUESTIONS.map((q) => (
                      <button
                        key={q}
                        onClick={() => handleSuggestedQuestion(q)}
                        className="px-4 py-2 rounded-full text-sm bg-gray-800 border border-gray-700
                                   text-gray-300 hover:border-purple-500 hover:text-purple-400
                                   transition-all duration-200"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              </CardContent>

              {/* 底部输入区（欢迎界面也有） */}
              <div className="p-4 border-t border-gray-700 mt-auto">
                <div className="flex gap-3 max-w-2xl mx-auto">
                  <textarea
                    ref={inputRef}
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="向智能助手提问..."
                    className="flex-1 px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white
                               placeholder-gray-400 resize-none focus:border-gray-500 focus:outline-none
                               text-sm"
                    rows={2}
                  />
                  <Button onClick={handleSend} disabled={!inputMessage.trim()} className="self-end">
                    发送
                  </Button>
                </div>
              </div>
            </>
          ) : (
            /* ── 聊天界面 ── */
            <>
              {/* 消息列表 */}
              <CardContent className="flex-1 overflow-hidden py-0">
                <div className="h-full flex flex-col">
                  <div className="flex-1 overflow-y-auto space-y-4 py-4">
                    {/* 已固化的消息 */}
                    {messages.map((msg, idx) => (
                      <MessageBubble key={idx} message={msg} onCopy={handleCopy} />
                    ))}

                    {/* 流式进行中的消息 */}
                    {streaming && <StreamingBubble streaming={streaming} thinking={thinking} />}

                    {/* 错误 */}
                    {error && (
                      <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                        <p className="text-sm text-red-400">{error}</p>
                      </div>
                    )}

                    <div ref={messagesEndRef} />
                  </div>
                </div>
              </CardContent>

              {/* 输入区域 */}
              <div className="p-4 border-t border-gray-700">
                <div className="flex gap-3">
                  <textarea
                    ref={inputRef}
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="向智能助手提问..."
                    className="flex-1 px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white
                               placeholder-gray-400 resize-none focus:border-gray-500 focus:outline-none
                               text-sm"
                    rows={2}
                    disabled={isProcessing}
                  />
                  {isProcessing ? (
                    <Button variant="outline" onClick={stopProcessing} className="self-end">
                      停止
                    </Button>
                  ) : (
                    <Button onClick={handleSend} disabled={!inputMessage.trim()} className="self-end">
                      发送
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════
// 消息气泡（已固化的消息）
// ═══════════════════════════════════════════════════════════════════════

const MessageBubble: React.FC<{
  message: AgentMessage
  onCopy: (content: string) => void
}> = ({ message, onCopy }) => {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end gap-3">
        <div className="max-w-[80%] px-4 py-3 rounded-lg bg-purple-500/80 text-white">
          <div className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</div>
          <div className="text-xs opacity-70 mt-1">{formatDate(new Date(), 'HH:mm')}</div>
        </div>
        <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center flex-shrink-0">
          <span className="text-sm">👤</span>
        </div>
      </div>
    )
  }

  // 助手消息
  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center flex-shrink-0">
        <span className="text-sm">🤖</span>
      </div>

      <div className="max-w-[85%] min-w-0">
        {/* 工具调用卡片 */}
        {message.toolResults && message.toolResults.length > 0 && (
          <div className="mb-2">
            {message.toolResults.map((tr) => (
              <ToolCallCard key={tr.toolCallId} result={tr} />
            ))}
          </div>
        )}

        {/* Markdown 内容 */}
        {message.content && (
          <div className="px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-gray-200">
            <MarkdownBody content={message.content} />
            <div className="flex items-center gap-3 mt-2 pt-2 border-t border-gray-700/50">
              <span className="text-xs text-gray-500">{formatDate(new Date(), 'HH:mm')}</span>
              <button
                onClick={() => onCopy(message.content)}
                className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
              >
                复制
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════
// 流式消息气泡（实时进行中）
// ═══════════════════════════════════════════════════════════════════════

const StreamingBubble: React.FC<{
  streaming: {
    content: string
    thinking: boolean
    toolCalls: ToolCall[]
    toolResults: ToolCallResult[]
  }
  thinking: boolean
}> = ({ streaming, thinking }) => {
  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center flex-shrink-0">
        <span className="text-sm">🤖</span>
      </div>

      <div className="max-w-[85%] min-w-0">
        {/* 工具调用卡片 */}
        {streaming.toolResults.length > 0 && (
          <div className="mb-2">
            {streaming.toolResults.map((tr) => (
              <ToolCallCard key={tr.toolCallId} result={tr} />
            ))}
          </div>
        )}

        {/* 思考中状态 */}
        {thinking && !streaming.content && streaming.toolResults.length === 0 && (
          <div className="px-4 py-3 rounded-lg bg-gray-800 border border-gray-700">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">思考中</span>
              <span className="flex gap-1">
                <span
                  className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"
                  style={{ animationDelay: '0ms' }}
                />
                <span
                  className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"
                  style={{ animationDelay: '150ms' }}
                />
                <span
                  className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"
                  style={{ animationDelay: '300ms' }}
                />
              </span>
            </div>
          </div>
        )}

        {/* 流式内容 */}
        {streaming.content && (
          <div className="px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-gray-200">
            <MarkdownBody content={streaming.content} />
            <span className="inline-block w-2 h-4 bg-purple-400 ml-0.5 animate-pulse align-middle" />
          </div>
        )}

        {/* 工具执行中但无内容 */}
        {!thinking && !streaming.content && streaming.toolResults.length > 0 && (
          <div className="px-4 py-3 rounded-lg bg-gray-800 border border-gray-700">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">工具执行完成，正在分析结果...</span>
              <span className="flex gap-1">
                <span
                  className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"
                  style={{ animationDelay: '0ms' }}
                />
                <span
                  className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"
                  style={{ animationDelay: '150ms' }}
                />
                <span
                  className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"
                  style={{ animationDelay: '300ms' }}
                />
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default AgentPage
