import React, { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, Button } from '@/components/UI'
import { Loading, Error, Empty } from '@/components/UI'
import { useForecastReport, useForecastHistory } from '@/hooks/useForecastApi'
import { formatDate } from '@/utils/helpers'
import { logAction } from '@/utils/behaviorLogger'
import type {
   ForecastReport,
   ForecastHistoryItem,
   ForecastPrediction,
   FullForecastReport,
   ScenarioAnalysis,
   ScenarioItem
} from '@/types'

// 常量定义
const MODEL_NAME = "kingstar"
const PROMPT_VERSION = "v2.0"

const toFullForecastReport = (prediction: ForecastReport['prediction']): FullForecastReport | null => {
  if (!prediction) return null

  if (typeof prediction === 'string') {
    try {
      return JSON.parse(prediction) as FullForecastReport
    } catch {
      return null
    }
  }

  return prediction as FullForecastReport
}

const PredictionPage: React.FC = () => {
  // 状态管理 - 不需要默认选中日期，API会自动返回最近的预测
  const [selectedDate, setSelectedDate] = useState<string>('')
  const [activeTab, setActiveTab] = useState<'current' | 'history'>('current')
  const [expandedHistoryDate, setExpandedHistoryDate] = useState<string | null>(null)
  const [historyLimit, setHistoryLimit] = useState<number>(90)
  
  // 数据获取 - 不传日期会自动获取最近的预测报告
  // 如果 selectedDate 为空，传递 undefined 获取最近的
  const {
    data: currentReport,
    isLoading: currentLoading,
    error: currentError,
    refetch: refetchCurrent
  } = useForecastReport(selectedDate || undefined)
  
  const { 
    data: historyData, 
    isLoading: historyLoading, 
    error: historyError 
  } = useForecastHistory(historyLimit)
  
  const isLoading = activeTab === 'current' ? currentLoading : historyLoading
  const error = activeTab === 'current' ? currentError : historyError
  
  const getProbabilityColor = (probability: number) => {
    if (probability > 0.6) return 'text-green-400'
    if (probability > 0.4) return 'text-yellow-400'
    return 'text-red-400'
  }
  
  const getScenarioIcon = (scenario: string) => {
    switch (scenario) {
      case 'bullish':
        return '📈'
      case 'bearish':
        return '📉'
      case 'black_swan':
        return '🦢'
      default:
        return '📊'
    }
  }
  

  const PredictionCard: React.FC<{
    title: string
    prediction?: ForecastPrediction
    period: string
  }> = ({ title, prediction, period }) => {
    if (!prediction) return null
    
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {title}
            <span className="text-sm font-normal text-gray-400">({period})</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* 概率显示 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-3 bg-green-500/10 rounded-lg border border-green-500/20">
                <p className="text-sm text-gray-400 mb-1">上涨概率</p>
                <p className={`text-2xl font-bold ${getProbabilityColor(prediction.上涨概率)}`}>
                  {(prediction.上涨概率 * 100).toFixed(1)}%
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  +{prediction.上涨基点.toFixed(1)} BP
                </p>
              </div>
              
              <div className="text-center p-3 bg-red-500/10 rounded-lg border border-red-500/20">
                <p className="text-sm text-gray-400 mb-1">下跌概率</p>
                <p className={`text-2xl font-bold ${getProbabilityColor(prediction.下跌概率)}`}>
                  {(prediction.下跌概率 * 100).toFixed(1)}%
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {prediction.下跌基点.toFixed(1)} BP
                </p>
              </div>
            </div>
            
             {/* 预测理由 */}
             {prediction.分析理由 && (
               <div>
                 <h4 className="text-sm font-medium text-white mb-2">分析理由</h4>
                 <p className="text-sm text-gray-300 leading-relaxed">
                   {prediction.分析理由}
                 </p>
               </div>
             )}
             
             {/* 置信度 */}
             {prediction.置信度 !== undefined && (
               <div>
                 <h4 className="text-sm font-medium text-white mb-2">置信度</h4>
                 <div className="w-full bg-gray-700 rounded-full h-2.5">
                   <div
                     className="bg-blue-400 h-2.5 rounded-full"
                     style={{ width: `${(prediction.置信度 * 100).toFixed(0)}%` }}
                   ></div>
                 </div>
                 <p className="text-sm text-gray-400 mt-1">
                   {(prediction.置信度 * 100).toFixed(0)}%
                 </p>
               </div>
             )}
             
             {/* 假设条件 */}
             {prediction.假设条件 && prediction.假设条件.length > 0 && (
               <div>
                 <h4 className="text-sm font-medium text-white mb-2">假设条件</h4>
                 <ul className="list-disc pl-5 space-y-1">
                   {prediction.假设条件.map((assumption, idx) => (
                     <li key={idx} className="text-sm text-gray-300">{assumption}</li>
                   ))}
                 </ul>
               </div>
             )}
             
             {/* 方向判断 */}
             <div className="pt-3 border-t border-gray-700">
               <div className="flex items-center justify-between">
                 <span className="text-sm text-gray-400">方向判断</span>
                 <span className={`text-sm font-medium ${
                   prediction.上涨概率 > prediction.下跌概率
                     ? 'text-green-400'
                     : 'text-red-400'
                 }`}>
                   {prediction.上涨概率 > prediction.下跌概率 ? '看涨' : '看跌'}
                 </span>
               </div>
             </div>
          </div>
        </CardContent>
      </Card>
    )
  }

   const ScenarioCard: React.FC<{
     title: string
     scenario: ScenarioItem
     type: keyof ScenarioAnalysis
   }> = ({ title, scenario, type }) => {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="text-xl">{getScenarioIcon(type)}</span>
            {title}
            <span className="text-sm font-normal text-gray-400">
              概率: {(scenario.概率 * 100).toFixed(1)}%
            </span>
          </CardTitle>
        </CardHeader>
         <CardContent>
           {scenario.触发条件 && (
             <div className="mb-3 pb-3 border-b border-gray-700">
               <h4 className="text-sm font-medium text-white mb-2">触发条件</h4>
               <p className="text-sm text-gray-300 leading-relaxed">
                 {scenario.触发条件}
               </p>
             </div>
           )}
           <p className="text-sm text-gray-300 leading-relaxed">
             {scenario.描述}
           </p>
         </CardContent>
      </Card>
    )
  }
  
  const FullReportView: React.FC<{
    report: ForecastReport
    fullReport: FullForecastReport
  }> = ({ report, fullReport }) => {
    // 直接使用中文键名，不需要兼容英文
    const marketOverview = fullReport['市场概览']
    const technicalAnalysis = fullReport['技术分析']
    const factorAnalysis = fullReport['因子分析']
    const strategyRecommendations = fullReport['策略建议']
    const riskWarnings = fullReport['风险提示']
    
     // 获取预测数据 - 统一使用中文键名
     const predictions = {
       day: fullReport['预测结果']?.['日'],
       week: fullReport['预测结果']?.['周'],
       month: fullReport['预测结果']?.['月']
     }
     
      // 获取情景分析 - 统一使用中文键名
      const scenarioAnalysis = {
        baseline: fullReport['情景分析']?.['基准'],
        bullish: fullReport['情景分析']?.['牛市'],
        bearish: fullReport['情景分析']?.['熊市'],
        black_swan: fullReport['情景分析']?.['黑天鹅']
      }
    

    return (
      <div className="space-y-6">
         {/* ☆ 打印专用报告主标题（仅 print 显示） */}
         <div className="print-report-title no-print" aria-hidden="true">
           <h1>AI 债券市场智能分析报告</h1>
           <p className="print-report-date">报告日期：{report.trade_date}</p>
           <p className="print-report-meta">
             模型：{report.model_name} | 版本：{report.prompt_version} | 生成时间：{formatDate(report.created_at, 'YYYY-MM-DD HH:mm')}
           </p>
         </div>

         {/* 报告信息头部 */}
         <Card>
           <CardContent className="p-4">
             <div className="flex items-center justify-between">
               <div>
                 <h3 className="text-lg font-semibold text-white">
                   {report.trade_date} 市场预测分析报告
                 </h3>
                 <p className="text-sm text-gray-400">
                   模型: {report.model_name} | 版本: {report.prompt_version}
                 </p>
               </div>
               <div className="text-right">
                 <p className="text-sm text-gray-400">生成时间</p>
                 <p className="text-sm text-white">
                   {formatDate(report.created_at, 'MM-DD HH:mm')}
                 </p>
               </div>
             </div>
             
             {/* 报告摘要 */}
             {fullReport.报告摘要 && (
               <div className="mt-4 pt-4 border-t border-gray-700">
                 <h4 className="text-sm font-medium text-white mb-2">报告摘要</h4>
                 <p className="text-sm text-gray-300 leading-relaxed">
                   {fullReport.报告摘要}
                 </p>
               </div>
             )}
           </CardContent>
         </Card>

         {/* 市场概览 */}
        {marketOverview && (
          <Card>
            <CardHeader>
              <CardTitle>🌍 市场概览</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-gray-300 text-base leading-relaxed whitespace-pre-line">
                {typeof marketOverview === 'string'
                  ? marketOverview.split(/\*\*(.*?)\*\*/g).map((part, index) =>
                      index % 2 === 0 ? part : <strong key={index} className="text-white font-semibold">{part}</strong>
                    )
                  : String(marketOverview)}
              </div>
            </CardContent>
          </Card>
        )}

        {/* 技术分析 */}
        {technicalAnalysis && (
          <Card>
            <CardHeader>
              <CardTitle>📊 技术分析</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-gray-300 text-base leading-relaxed whitespace-pre-line">
                {typeof technicalAnalysis === 'string'
                  ? technicalAnalysis.split(/\*\*(.*?)\*\*/g).map((part, index) =>
                      index % 2 === 0 ? part : <strong key={index} className="text-white font-semibold">{part}</strong>
                    )
                  : String(technicalAnalysis)}
              </div>
            </CardContent>
          </Card>
        )}

        {/* 因子分析 */}
        {factorAnalysis && (
          <Card>
            <CardHeader>
              <CardTitle>🔍 因子分析</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-gray-300 text-base leading-relaxed whitespace-pre-line">
                {typeof factorAnalysis === 'string'
                  ? factorAnalysis.split(/\*\*(.*?)\*\*/g).map((part, index) =>
                      index % 2 === 0 ? part : <strong key={index} className="text-white font-semibold">{part}</strong>
                    )
                  : String(factorAnalysis)}
              </div>
            </CardContent>
          </Card>
        )}

        {/* 预测结果 */}
        {(predictions.day || predictions.week || predictions.month) && (
          <div>
            <h3 className="text-lg font-semibold text-white mb-4">🎯 预测结果</h3>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <PredictionCard
                title="日度预测"
                prediction={predictions.day}
                period="1天"
              />
              <PredictionCard
                title="周度预测"
                prediction={predictions.week}
                period="1周"
              />
              <PredictionCard
                title="月度预测"
                prediction={predictions.month}
                period="1月"
              />
            </div>
          </div>
        )}

         {/* 情景分析 */}
         {(scenarioAnalysis.baseline || scenarioAnalysis.bullish || scenarioAnalysis.bearish || scenarioAnalysis.black_swan) && (
           <div>
             <h3 className="text-lg font-semibold text-white mb-4">🔮 情景分析</h3>
             <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
               {scenarioAnalysis.baseline && (
                 <ScenarioCard
                   title="基准情景"
                   scenario={scenarioAnalysis.baseline}
                   type="bullish"
                 />
               )}
               {scenarioAnalysis.bullish && (
                 <ScenarioCard
                   title="牛市情景"
                   scenario={scenarioAnalysis.bullish}
                   type="bullish"
                 />
               )}
               {scenarioAnalysis.bearish && (
                 <ScenarioCard
                   title="熊市情景"
                   scenario={scenarioAnalysis.bearish}
                   type="bearish"
                 />
               )}
               {scenarioAnalysis.black_swan && (
                 <ScenarioCard
                   title="黑天鹅事件"
                   scenario={scenarioAnalysis.black_swan}
                   type="black_swan"
                 />
               )}
             </div>
           </div>
         )}

        {/* 策略建议 */}
        {strategyRecommendations && (
          <Card>
            <CardHeader>
              <CardTitle>💡 策略建议</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-gray-300 text-base leading-relaxed whitespace-pre-line">
                {typeof strategyRecommendations === 'string'
                  ? strategyRecommendations.split(/\*\*(.*?)\*\*/g).map((part, index) =>
                      index % 2 === 0 ? part : <strong key={index} className="text-white font-semibold">{part}</strong>
                    )
                  : String(strategyRecommendations)}
              </div>
            </CardContent>
          </Card>
        )}

        {/* 风险提示 */}
        {riskWarnings && (
          <Card>
            <CardHeader>
              <CardTitle>⚠️ 风险提示</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-gray-300 text-base leading-relaxed whitespace-pre-line">
                {typeof riskWarnings === 'string'
                  ? riskWarnings.split(/\*\*(.*?)\*\*/g).map((part, index) =>
                      index % 2 === 0 ? part : <strong key={index} className="text-white font-semibold">{part}</strong>
                    )
                  : String(riskWarnings)}
              </div>
            </CardContent>
          </Card>
        )}

        {/* ☆ 免责声明 & 风险提示（仅 print 显示） */}
        <div className="disclaimer no-print" aria-hidden="true">
          <h4>【免责声明】</h4>
          <p>本报告基于公开数据和模型分析生成，仅供专业投资者参考，不构成任何投资建议或承诺。</p>
          <p>报告中的预测结果基于历史数据和特定模型假设，实际市场走势可能与预测存在偏差。</p>
          <p>投资者应根据自身风险承受能力独立做出投资决策，并自行承担投资风险。</p>
          <h4 style={{ marginTop: '6px' }}>【交易风险提示】</h4>
          <p>债券投资面临利率风险、信用风险、流动性风险等多种风险因素。过往表现不代表未来收益，请谨慎投资。</p>
        </div>
      </div>
    )
  }
  
  const CurrentPredictions = () => {
   if (!currentReport?.reports.length) {
     return (
       <Empty
         title="暂无预测报告"
         message="当前日期没有可用的市场预测"
         action={{
           label: '刷新数据',
           onClick: () => refetchCurrent()
         }}
       />
     )
   }
   
   // 选择最新的完整报告（按 created_at 降序，缺失时回退 trade_date）
   const fullReportItem = [...currentReport.reports]
     .filter(r => r.forecast_type === 'full_report')
     .sort((a, b) => {
       const aTime = new Date(a.created_at || a.trade_date).getTime()
       const bTime = new Date(b.created_at || b.trade_date).getTime()
       return bTime - aTime
     })[0]
   
   if (!fullReportItem) {
     // 理论上不应该到达这里，因为现在只生成full_report类型
     return (
       <Empty
         title="格式错误"
         message="未找到完整预测报告数据"
         action={{
           label: '刷新数据',
           onClick: () => refetchCurrent()
         }}
       />
     )
   }
   
   const fullReport = toFullForecastReport(fullReportItem.prediction)
   if (!fullReport) {
     return (
       <Error
         title="报告解析失败"
         message="完整报告数据格式异常，请刷新后重试"
       />
     )
   }

   // 渲染完整报告
   return <FullReportView report={fullReportItem} fullReport={fullReport} />
 }
  
  const HistoryPredictions = () => {
    if (!historyData?.history.length) {
      return (
        <Empty
          title="暂无历史记录"
          message="没有找到历史预测数据"
        />
      )
    }
    
    // 只保留有完整报告的记录，已经按日期降序排序
    // 根据forecast_type是否为full_report判断（历史数据结构保持兼容处理）
    const validHistoryItems = historyData.sortedHistory.filter(historyItem => {
      return !!historyItem.reports.full_report;
    })
    
    if (validHistoryItems.length === 0) {
      return (
        <Empty
          title="无完整报告"
          message="所选范围内没有完整预测报告"
        />
      )
    }
    
    return (
      <div className="space-y-4">
        {/* 统计信息 */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <span className="text-sm font-medium text-white">历史预测记录</span>
              </div>
              
              <div className="flex items-center gap-3">
                <div className="text-sm text-gray-400">
                  当前展示窗口: 最近 {historyData.history.length} 个交易日（完整报告 {validHistoryItems.length} 条）
                </div>
                <select
                  value={historyLimit}
                  onChange={(e) => {
                    setExpandedHistoryDate(null)
                    setHistoryLimit(Number(e.target.value))
                  }}
                  className="px-2 py-1.5 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm"
                >
                  {[30, 60, 90, 180, 365].map((n) => (
                    <option key={n} value={n}>
                      最近 {n} 天
                    </option>
                  ))}
                </select>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setExpandedHistoryDate(null)
                    setHistoryLimit((prev) => prev + 30)
                  }}
                >
                  加载更多
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
        
        {/* 历史记录 */}
        <div className="space-y-6">
          {validHistoryItems.map((historyItem: ForecastHistoryItem) => {
            const isExpanded = expandedHistoryDate === historyItem.date
            const fullReport = historyItem.reports.full_report!
            
            // 创建一个模拟的ForecastReport对象
            const forecastReport: ForecastReport = {
              trade_date: historyItem.date,
              model_name: MODEL_NAME || 'kingstar',
              prompt_version: PROMPT_VERSION || 'v2.0',
              forecast_type: 'full_report',
              prediction: fullReport,
              created_at: historyItem.date
            }
            
            return (
              <Card key={historyItem.date} className="cursor-pointer"
                    onClick={() => {
                setExpandedHistoryDate(isExpanded ? null : historyItem.date)
              }}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>{historyItem.date} 完整市场预测分析报告</span>
                    <span className="text-blue-400">{isExpanded ? '收起' : '点击展开'}</span>
                  </CardTitle>
                </CardHeader>
                {isExpanded && (
                  <CardContent>
                    <div className="mt-4 pt-4 border-t border-gray-700">
                      <FullReportView report={forecastReport} fullReport={fullReport} />
                    </div>
                  </CardContent>
                )}
              </Card>
            )
          })}
        </div>
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div className="page-header">
        <h1 className="text-3xl font-bold text-white mb-2">
          🔮 市场预测
        </h1>
        <p className="text-gray-400 text-sm">
          AI驱动的债券市场走势预测分析报告
        </p>
      </div>
      
      {/* 日期选择 */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <label className="text-sm font-medium text-gray-400">查询日期</label>
                <input
                  type="date"
                  value={selectedDate}
                  onChange={(e) => {
                    const v = e.target.value;
                    setSelectedDate(v);
                    if (v) logAction('date_select', '/prediction', v);
                  }}
                  className="ml-2 px-3 py-1.5 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm"
                />
              </div>
              
              {selectedDate && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedDate('')}
                >
                  清除日期
                </Button>
              )}
            </div>
            
            <Button onClick={() => { refetchCurrent(); logAction('report_view', '/prediction', selectedDate || undefined); }}>
              刷新数据
            </Button>
          </div>
        </CardContent>
      </Card>
      
      {/* 标签页导航 */}
      <div className="flex space-x-1 p-1 bg-gray-800 rounded-lg no-print">
        <button
          onClick={() => setActiveTab('current')}
          data-track="tab_switch"
          data-target="current"
          className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === 'current'
              ? 'bg-purple-500 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-700'
          }`}
        >
          当前预测
        </button>
        <button
          onClick={() => setActiveTab('history')}
          data-track="tab_switch"
          data-target="history"
          className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === 'history'
              ? 'bg-purple-500 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-700'
          }`}
        >
          历史记录
        </button>
      </div>
      
      {/* 内容区域 */}
      <div className="min-h-[400px]">
        {isLoading ? (
          <Loading text="加载预测数据..." />
        ) : error ? (
          <Error title="加载失败" message={error.message} />
        ) : activeTab === 'current' ? (
          <CurrentPredictions />
        ) : (
          <HistoryPredictions />
        )}
      </div>
    </div>
  )
}

export default PredictionPage