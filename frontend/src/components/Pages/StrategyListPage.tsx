import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, CardContent } from '@/components/UI'
import SelectStrategyPage from '@/select_strategy'

/**
 * 策略板块（合并 AI推荐 + AI策略生成）。
 * - 展示 AI 智能推荐（最新推荐 + 历史 + 手动触发）
 * - 提供「AI策略生成」入口（交互式对话生成，客户可指定要生成的策略）
 * - 不再展示金仕达（Kingstar）量化/交易策略看板数据
 */
const StrategyListPage: React.FC = () => {
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      {/* AI 策略生成入口 */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-white">AI 策略生成</h3>
              <p className="text-sm text-gray-400 mt-1">
                通过对话描述您的策略需求，AI 自动生成策略代码、逻辑概要并支持代码回测
              </p>
            </div>
            <Button
              variant="primary"
              onClick={() => navigate('/ai-strategy-generation-preview')}
              data-track="strategy_generate_entry"
            >
              ✨ 开始生成策略
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* AI 智能推荐（最新 + 历史 + 手动触发） */}
      <SelectStrategyPage />
    </div>
  )
}

export default StrategyListPage
