/**
 * 历史快照选择与对比组件
 */
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchDashboardHistory, triggerDashboardSnapshot } from '../../api';

interface Props {
  className?: string;
}

export const HistorySnapshot: React.FC<Props> = ({ className = '' }) => {
  const [showHistory, setShowHistory] = useState(false);
  const [snapshotCreating, setSnapshotCreating] = useState(false);
  const [selectedSnapshot, setSelectedSnapshot] = useState<any>(null);

  const { data: history, isLoading, refetch } = useQuery({
    queryKey: ['dashboard', 'history'],
    queryFn: () => fetchDashboardHistory(7),
    enabled: showHistory,
  });

  const handleCreateSnapshot = async () => {
    setSnapshotCreating(true);
    try {
      await triggerDashboardSnapshot();
      refetch();
    } catch (e) {
      console.error('快照创建失败', e);
    } finally {
      setSnapshotCreating(false);
    }
  };

  const handleViewSnapshot = (snap: any) => {
    setSelectedSnapshot(snap);
  };

  return (
    <div className={`rounded-lg border border-gray-700/50 bg-gray-800/60 p-4 ${className}`}>
      <div className="flex items-center justify-between">
        <div className="text-xs text-gray-400 font-medium">📅 历史快照</div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 rounded border border-gray-600"
          >
            {showHistory ? '收起' : '展开'}
          </button>
          <button
            onClick={handleCreateSnapshot}
            disabled={snapshotCreating}
            className="text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-3 py-1 rounded"
          >
            {snapshotCreating ? '创建中...' : '生成快照'}
          </button>
        </div>
      </div>

      {showHistory && (
        <div className="mt-3">
          {isLoading ? (
            <div className="text-gray-500 text-xs py-3 text-center">加载中...</div>
          ) : !history || history.length === 0 ? (
            <div className="text-gray-500 text-xs py-3 text-center">暂无历史快照，点击"生成快照"创建</div>
          ) : (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {history.map((snap: any) => (
                <div key={snap.id} className="flex items-center justify-between px-3 py-2 rounded bg-gray-700/30 border border-gray-700/30 hover:bg-gray-700/50 transition-colors">
                  <span className="text-xs text-gray-300">{snap.snapshot_time}</span>
                  <button
                    className="text-xs text-blue-400 hover:text-blue-300"
                    onClick={() => handleViewSnapshot(snap)}
                  >
                    查看
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 快照详情弹窗 */}
      {selectedSnapshot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setSelectedSnapshot(null)}>
          <div
            className="bg-gray-800 border border-gray-600 rounded-lg p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto mx-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-white">
                📸 快照详情 — {selectedSnapshot.snapshot_time}
              </h3>
              <button
                onClick={() => setSelectedSnapshot(null)}
                className="text-gray-400 hover:text-white text-lg"
              >
                ✕
              </button>
            </div>

            {selectedSnapshot.metrics?.top_cards && (
              <div className="grid grid-cols-3 gap-3 mb-4">
                <SnapshotValue label="新闻总量" value={selectedSnapshot.metrics.top_cards.news_total} />
                <SnapshotValue label="已分析" value={selectedSnapshot.metrics.top_cards.analyzed} />
                <SnapshotValue label="待分析" value={selectedSnapshot.metrics.top_cards.pending} />
                <SnapshotValue label="因子总数" value={selectedSnapshot.metrics.top_cards.factor_total} />
                <SnapshotValue label="收益率覆盖" value={`${selectedSnapshot.metrics.top_cards.yield_days}天`} />
              </div>
            )}

            {selectedSnapshot.metrics?.news && (
              <div className="mb-3">
                <div className="text-xs text-gray-400 mb-1">新闻数据流</div>
                <div className="text-xs text-gray-300 space-y-1 bg-gray-900/40 rounded p-3">
                  <div>总量: {selectedSnapshot.metrics.news.total?.toLocaleString()} | 来源: {selectedSnapshot.metrics.news.source_distribution?.map((d: any) => `${d.name}(${d.count})`).join(', ')}</div>
                </div>
              </div>
            )}

            {selectedSnapshot.metrics?.analysis && (
              <div className="mb-3">
                <div className="text-xs text-gray-400 mb-1">分析引擎</div>
                <div className="text-xs text-gray-300 space-y-1 bg-gray-900/40 rounded p-3">
                  <div>已分析: {selectedSnapshot.metrics.analysis.analyzed?.toLocaleString()} | 待分析: {selectedSnapshot.metrics.analysis.pending?.toLocaleString()} | 覆盖率: {selectedSnapshot.metrics.analysis.coverage_pct}%</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// 小工具
const SnapshotValue: React.FC<{ label: string; value: number | string }> = ({ label, value }) => (
  <div className="rounded bg-gray-700/30 px-3 py-2">
    <div className="text-[10px] text-gray-500">{label}</div>
    <div className="text-sm font-bold text-gray-200">
      {typeof value === 'number' ? value.toLocaleString() : value}
    </div>
  </div>
);
