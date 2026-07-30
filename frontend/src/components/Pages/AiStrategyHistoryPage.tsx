/** 当前用户的 AI 策略会话历史页，数据来自独立历史库。 */
import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchAiStrategyConversations } from '@/api'
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Empty, Error as ErrorState, Loading } from '@/components/UI'
import { formatBeijingDateTime } from '@/utils/helpers'

const AiStrategyHistoryPage: React.FC = () => {
  const navigate = useNavigate()
  const historyQuery = useQuery({
    queryKey: ['ai-strategy-conversations'],
    queryFn: fetchAiStrategyConversations,
  })

  return <div className="mx-auto max-w-6xl space-y-5">
    <div className="flex flex-col gap-4 border-b border-gray-800 pb-5 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h1 className="text-3xl font-bold text-blue-400">策略对话历史</h1>
        <p className="mt-2 text-sm text-gray-400">历史数据来自独立会话库；仅显示当前账号可访问的策略会话。</p>
      </div>
      <Button onClick={() => navigate('/ai-strategy-generation-preview')}>新建对话</Button>
    </div>

    {historyQuery.isLoading && <Loading text="正在读取历史会话..." />}
    {historyQuery.error && <ErrorState message={historyQuery.error instanceof Error ? historyQuery.error.message : '读取历史会话失败。'} />}
    {historyQuery.data && historyQuery.data.data.items.length === 0 && <Empty title="暂无历史会话" message="开始一次真实策略生成后，会话会保存在独立历史库中。" />}
    <div className="grid gap-4">
      {historyQuery.data?.data.items.map((conversation) => <Card key={conversation.id} hover onClick={() => navigate(`/ai-strategy-generation-preview/${conversation.id}`)}>
        <CardHeader className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="mb-1">{conversation.title}</CardTitle>
            <CardDescription>{conversation.instrument || '未识别具体交易品种'}</CardDescription>
          </div>
          <span className="w-fit rounded-full bg-blue-500/15 px-3 py-1 text-xs font-medium text-blue-300">v{conversation.current_local_version_no}</span>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 text-sm text-gray-400 sm:flex-row sm:items-center sm:justify-between">
          <span>最后活动（北京时间）：{formatBeijingDateTime(conversation.last_message_at || conversation.updated_at)}</span>
          <Button size="sm" onClick={(event) => { event.stopPropagation(); navigate(`/ai-strategy-generation-preview/${conversation.id}`) }}>继续对话</Button>
        </CardContent>
      </Card>)}
    </div>
  </div>
}

export default AiStrategyHistoryPage
