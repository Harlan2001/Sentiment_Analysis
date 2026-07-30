import React, { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/UI/Card'
import Button from '@/components/UI/Button'
import { PredictionChart } from '@/components/UI/PredictionChart'

interface Scenario {
  id: string
  name: string
  description: string
  probability: number
  impact: 'high' | 'medium' | 'low'
  color: string
}

const scenarios: Scenario[] = [
  {
    id: 'optimistic',
    name: '乐观情景',
    description: '经济复苏超预期，政策宽松持续',
    probability: 0.25,
    impact: 'high',
    color: 'green'
  },
  {
    id: 'baseline',
    name: '基准情景',
    description: '经济稳步复苏，政策逐步正常化',
    probability: 0.55,
    impact: 'medium',
    color: 'blue'
  },
  {
    id: 'pessimistic',
    name: '悲观情景',
    description: '经济复苏放缓，政策收紧提前',
    probability: 0.20,
    impact: 'high',
    color: 'red'
  }
]

export const ScenarioAnalysis: React.FC = () => {
  const [selectedScenario, setSelectedScenario] = useState<Scenario>(scenarios[1])

  return (
    <div className="space-y-6">
      {/* 场景选择 */}
      <Card className="p-6">
        <CardHeader>
          <CardTitle>情景分析</CardTitle>
        </CardHeader>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {scenarios.map(scenario => (
            <div
              key={scenario.id}
              className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                selectedScenario.id === scenario.id
                  ? `border-${scenario.color}-500 bg-${scenario.color}-500/10`
                  : 'border-gray-600 bg-gray-800/50 hover:border-gray-500'
              }`}
              onClick={() => setSelectedScenario(scenario)}
            >
              <h3 className="font-semibold text-white mb-2">{scenario.name}</h3>
              <p className="text-sm text-gray-400 mb-3">{scenario.description}</p>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">发生概率</span>
                <span className="text-sm font-medium text-white">
                  {(scenario.probability * 100).toFixed(0)}%
                </span>
              </div>
              <div className="mt-2 bg-gray-700 rounded-full h-2">
                <div 
                  className={`bg-${scenario.color}-500 h-2 rounded-full`}
                  style={{ width: `${scenario.probability * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* 风险矩阵 */}
      <Card className="p-6">
        <CardHeader>
          <CardTitle>风险评估矩阵</CardTitle>
        </CardHeader>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-white mb-4">主要风险因素</h4>
            <div className="space-y-3">
              {[
                { factor: '政策收紧', probability: '中', impact: '高', level: 'orange' },
                { factor: '通胀反弹', probability: '低', impact: '高', level: 'yellow' },
                { factor: '地缘政治', probability: '中', impact: '中', level: 'orange' },
                { factor: '流动性收紧', probability: '中', impact: '中', level: 'orange' }
              ].map((risk, index) => (
                <div key={index} className="flex items-center justify-between bg-gray-800/50 rounded-lg p-3">
                  <span className="text-sm text-white">{risk.factor}</span>
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 rounded text-xs ${risk.level === 'orange' ? 'bg-orange-500/20 text-orange-400' : risk.level === 'yellow' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400'}`}>
                      {risk.probability}
                    </span>
                    <span className="text-xs text-gray-400">{risk.impact}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h4 className="font-medium text-white mb-4">投资建议</h4>
            <div className="space-y-3">
              {selectedScenario.id === 'optimistic' && (
                <>
                  <div className="bg-green-500/20 border border-green-500/50 rounded-lg p-3">
                    <h5 className="text-sm font-medium text-green-400 mb-1">增持建议</h5>
                    <p className="text-xs text-gray-300">适度增持长期债券，关注信用债机会</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-3">
                    <h5 className="text-sm font-medium text-white mb-1">行业配置</h5>
                    <p className="text-xs text-gray-400">重点关注城投债、产业债</p>
                  </div>
                </>
              )}
              
              {selectedScenario.id === 'baseline' && (
                <>
                  <div className="bg-blue-500/20 border border-blue-500/50 rounded-lg p-3">
                    <h5 className="text-sm font-medium text-blue-400 mb-1">均衡配置</h5>
                    <p className="text-xs text-gray-300">保持中性久期，适度分散投资</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-3">
                    <h5 className="text-sm font-medium text-white mb-1">风险控制</h5>
                    <p className="text-xs text-gray-400">控制信用风险敞口，保持流动性</p>
                  </div>
                </>
              )}
              
              {selectedScenario.id === 'pessimistic' && (
                <>
                  <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-3">
                    <h5 className="text-sm font-medium text-red-400 mb-1">防守策略</h5>
                    <p className="text-xs text-gray-300">缩短久期，增加高等级债券配置</p>
                  </div>
                  <div className="bg-gray-800/50 rounded-lg p-3">
                    <h5 className="text-sm font-medium text-white mb-1">现金管理</h5>
                    <p className="text-xs text-gray-400">保持充足现金，等待机会</p>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* 预测图表 */}
      <PredictionChart />
    </div>
  )
}