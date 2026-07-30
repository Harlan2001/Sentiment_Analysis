import React from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/UI/Card'

interface PredictionMetric {
  label: string
  value: string
  change: number
  status: 'positive' | 'negative' | 'neutral'
}

interface ForecastData {
  period: string
  predicted: number
  confidence: number
}

export const PredictionChart: React.FC = () => {
  const metrics: PredictionMetric[] = [
    { label: '10年期国债收益率', value: '2.35%', change: -0.05, status: 'positive' },
    { label: '信用利差', value: '1.2%', change: 0.15, status: 'negative' },
    { label: '流动性指数', value: '86.5', change: 2.3, status: 'positive' },
    { label: '市场情绪', value: '72.3', change: -1.8, status: 'neutral' }
  ]

  const forecastData: ForecastData[] = [
    { period: '1个月', predicted: 2.32, confidence: 0.85 },
    { period: '3个月', predicted: 2.28, confidence: 0.72 },
    { period: '6个月', predicted: 2.25, confidence: 0.65 },
    { period: '12个月', predicted: 2.20, confidence: 0.58 }
  ]

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* 预测指标卡片 */}
      <Card className="p-6">
        <CardHeader>
          <CardTitle>关键指标预测</CardTitle>
        </CardHeader>
        <div className="grid grid-cols-2 gap-4">
          {metrics.map((metric, index) => (
            <div key={index} className="bg-gray-800/50 rounded-lg p-4">
              <div className="text-sm text-gray-400 mb-1">{metric.label}</div>
              <div className="flex items-center justify-between">
                <span className="text-xl font-semibold text-white">{metric.value}</span>
                <span className={`text-sm px-2 py-1 rounded ${
                  metric.status === 'positive' ? 'bg-green-500/20 text-green-400' :
                  metric.status === 'negative' ? 'bg-red-500/20 text-red-400' :
                  'bg-yellow-500/20 text-yellow-400'
                }`}>
                  {metric.change > 0 ? '+' : ''}{metric.change}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* 趋势预测图 */}
      <Card className="p-6">
        <CardHeader>
          <CardTitle>收益率趋势预测</CardTitle>
        </CardHeader>
        <div className="h-64 flex items-center justify-center bg-gray-800/50 rounded-lg">
          <div className="text-center">
            <div className="text-4xl mb-4">📈</div>
            <p className="text-gray-400">预测图表渲染区域</p>
            <p className="text-sm text-gray-500 mt-2">基于AI模型的收益率曲线预测</p>
          </div>
        </div>
      </Card>

      {/* 预测表格 */}
      <Card className="p-6 lg:col-span-2">
        <CardHeader>
          <CardTitle>分时段预测详情</CardTitle>
        </CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left py-3 px-4 text-gray-400">预测周期</th>
                <th className="text-left py-3 px-4 text-gray-400">预测值</th>
                <th className="text-left py-3 px-4 text-gray-400">置信度</th>
                <th className="text-left py-3 px-4 text-gray-400">风险评估</th>
                <th className="text-left py-3 px-4 text-gray-400">建议</th>
              </tr>
            </thead>
            <tbody>
              {forecastData.map((data, index) => (
                <tr key={index} className="border-b border-gray-700/50">
                  <td className="py-3 px-4 text-white">{data.period}</td>
                  <td className="py-3 px-4 text-white">{data.predicted}%</td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-gray-700 rounded-full h-2">
                        <div 
                          className="bg-purple-500 h-2 rounded-full"
                          style={{ width: `${data.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-white text-xs">{(data.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-1 rounded text-xs ${
                      data.confidence > 0.8 ? 'bg-green-500/20 text-green-400' :
                      data.confidence > 0.6 ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-red-500/20 text-red-400'
                    }`}>
                      {data.confidence > 0.8 ? '低风险' : data.confidence > 0.6 ? '中风险' : '高风险'}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-gray-400 text-xs">
                    {data.confidence > 0.8 ? '可以考虑配置' : '建议观望'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}