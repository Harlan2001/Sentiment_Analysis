import React, { useEffect, useState, useCallback } from 'react';
import { fetchChangeSnapshots, fetchChangeCompare, triggerChangeSnapshot } from '../../api';
import { Loading, Error, Empty } from '../UI';
import type {
  ChangeSnapshotItem,
  ChangeCompareResponse,
  StockRecommendItem,
  StockRemovedItem,
  StockModifiedItem,
  StrategyRecommendItem,
  StrategyRemovedItem,
  StrategyModifiedItem,
} from '../../types';

// ============ 状态徽章 ============
const StatusBadge: React.FC<{ status: number }> = ({ status }) => {
  if (status === 2) {
    return (
      <span className="px-1.5 py-0.5 text-xs rounded bg-amber-500/20 text-amber-300" title="波动较大，待确认">
        ⚠
      </span>
    );
  }
  if (status === 0) {
    return <span className="px-1.5 py-0.5 text-xs rounded bg-red-500/20 text-red-300">失败</span>;
  }
  return <span className="px-1.5 py-0.5 text-xs rounded bg-green-500/20 text-green-300">✓</span>;
};

// ============ 工具函数 ============
function fmtTime(iso?: string): string {
  if (!iso) return '-';
  // "2026-06-15 11:00:00" → "06/15 11:00"
  const parts = iso.split(/[\s-]/);
  if (parts.length >= 2) {
    return `${parts[1]}/${parts[2]} ${parts[3]?.slice(0, 5) || ''}`;
  }
  return iso;
}

function versionLabel(item: ChangeSnapshotItem): string {
  const t = item.version_time;
  if (!t) return '-';
  const parts = t.split(/[\s:-]/);
  return parts[3] ? `${parts[3]}:00` : t;
}

// ============ 总览看板卡片 ============
const SummaryCard: React.FC<{
  label: string;
  value: number;
  subtext: string;
  colorClass: string;
  icon: string;
}> = ({ label, value, subtext, colorClass, icon }) => (
  <div className={`border rounded-lg p-4 flex items-start gap-3 ${colorClass}`}>
    <div className="text-2xl">{icon}</div>
    <div>
      <div className="text-xs text-gray-400 mb-0.5">{label}</div>
      <div className="text-2xl font-bold text-gray-100">{value}</div>
      <div className="text-xs text-gray-500 mt-0.5">{subtext}</div>
    </div>
  </div>
);

// ============ 窗口说明条 ============
const WindowInfo: React.FC<{ compare: ChangeCompareResponse | null }> = ({ compare }) => {
  if (!compare) return null;
  const { base_info } = compare;
  return (
    <div className="bg-gray-800/60 border border-gray-700 rounded-lg px-4 py-3 text-sm text-gray-300">
      <span className="font-medium text-gray-200">正在对比：</span>
      <span className="text-blue-300">{fmtTime(base_info.old_version)} 版本</span>
      <span className="text-gray-500">（{fmtTime(base_info.old_window[0])} ~ {fmtTime(base_info.old_window[1])}）</span>
      <span className="mx-2 text-gray-500">vs</span>
      <span className="text-purple-300">{fmtTime(base_info.new_version)} 版本</span>
      <span className="text-gray-500">（{fmtTime(base_info.new_window[0])} ~ {fmtTime(base_info.new_window[1])}）</span>
      <span className="mx-3 text-gray-600">|</span>
      <span>新闻变动：</span>
      <span className="text-green-400">新增 {base_info.news_diff.added_count} 条</span>
      <span className="mx-1">，</span>
      <span className="text-red-400">移出 {base_info.news_diff.removed_count} 条</span>
    </div>
  );
};

// ============ 标的卡片（新增） ============
const AddedStockCard: React.FC<{ item: StockRecommendItem }> = ({ item }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border-l-4 border-l-green-500 bg-gray-950/40 border border-gray-700 rounded-r-lg overflow-hidden">
      <button
        type="button"
        className="w-full p-3 text-left hover:bg-gray-900/30 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 text-xs rounded bg-green-500/20 text-green-300 font-medium">新增</span>
            <span className="text-sm font-semibold text-gray-100">{item.name}</span>
            <span className="text-xs text-gray-500">({item.code})</span>
          </div>
          <div className="flex items-center gap-3">
            <span className={`text-xs px-2 py-0.5 rounded ${
              item.rating === '强烈推荐' ? 'bg-blue-500/20 text-blue-300' :
              item.rating === '推荐' ? 'bg-green-500/20 text-green-300' :
              item.rating === '中性推荐' ? 'bg-gray-500/20 text-gray-300' :
              'bg-red-500/20 text-red-300'
            }`}>{item.rating}</span>
            <span className="text-xs text-gray-500">权重 {item.weight}</span>
            <span className={`text-xs ${expanded ? 'text-blue-300' : 'text-gray-600'}`}>
              {expanded ? '收起' : '展开'}
            </span>
          </div>
        </div>
        <div className="text-xs text-gray-500 mt-1 line-clamp-1">{item.reason}</div>
      </button>
      {expanded && (
        <div className="px-3 pb-3 border-t border-gray-700/50 pt-2">
          <div className="text-xs text-gray-400 leading-5 mb-2">{item.reason}</div>
          <div className="flex flex-wrap gap-1">
            {item.tags.map(tag => (
              <span key={tag} className="px-1.5 py-0.5 text-xs rounded bg-gray-700/50 text-gray-400">{tag}</span>
            ))}
          </div>
          <div className="text-xs text-gray-500 mt-1">风险等级：{item.risk_level}</div>
        </div>
      )}
    </div>
  );
};

// ============ 标的卡片（移除） ============
const RemovedStockCard: React.FC<{ item: StockRemovedItem }> = ({ item }) => (
  <div className="border-l-4 border-l-red-500 bg-gray-950/40 border border-gray-700 rounded-r-lg p-3">
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="px-1.5 py-0.5 text-xs rounded bg-red-500/20 text-red-300 font-medium">移出</span>
        <span className="text-sm font-semibold text-gray-400 line-through">{item.name}</span>
        <span className="text-xs text-gray-600">({item.code})</span>
      </div>
      <span className="text-xs text-gray-500">上一版本评级：{item.prev_rating || '-'}</span>
    </div>
  </div>
);

// ============ 标的卡片（调整） ============
const ModifiedStockCard: React.FC<{ item: StockModifiedItem }> = ({ item }) => {
  const [expanded, setExpanded] = useState(false);
  const hasRatingChange = item.old_rating && item.new_rating;
  const hasWeightChange = item.old_weight !== undefined && item.new_weight !== undefined;
  const hasReasonChange = !!item.old_reason && !!item.new_reason;

  return (
    <div className="border-l-4 border-l-yellow-500 bg-gray-950/40 border border-gray-700 rounded-r-lg overflow-hidden">
      <button
        type="button"
        className="w-full p-3 text-left hover:bg-gray-900/30 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 text-xs rounded bg-yellow-500/20 text-yellow-300 font-medium">调整</span>
            <span className="text-sm font-semibold text-gray-100">{item.name}</span>
            <span className="text-xs text-gray-500">({item.code})</span>
          </div>
          <span className={`text-xs ${expanded ? 'text-blue-300' : 'text-gray-600'}`}>
            {expanded ? '收起' : '详情'}
          </span>
        </div>
        <div className="text-xs text-gray-500 mt-1">
          {hasRatingChange && (
            <span>
              <span className="text-gray-500">{item.old_rating}</span>
              <span className="mx-1 text-yellow-400">→</span>
              <span className="text-yellow-300">{item.new_rating}</span>
            </span>
          )}
          {hasWeightChange && (
            <span className="ml-3">
              权重 <span className="text-gray-500">{item.old_weight}</span>
              <span className="mx-1 text-yellow-400">→</span>
              <span className="text-yellow-300">{item.new_weight}</span>
            </span>
          )}
        </div>
      </button>
      {expanded && (
        <div className="px-3 pb-3 border-t border-gray-700/50 pt-2 space-y-2">
          {hasReasonChange && (
            <div>
              <div className="text-xs text-gray-500 mb-1">旧推荐理由：</div>
              <div className="text-xs text-gray-400 bg-gray-900/50 rounded p-2">{item.old_reason}</div>
              <div className="text-xs text-gray-500 mb-1 mt-2">新推荐理由：</div>
              <div className="text-xs text-gray-300 bg-gray-900/50 rounded p-2">{item.new_reason}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ============ 策略卡片（新增） ============
const AddedStrategyCard: React.FC<{ item: StrategyRecommendItem }> = ({ item }) => (
  <div className="border-l-4 border-l-green-500 bg-gray-950/40 border border-gray-700 rounded-r-lg p-3">
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="px-1.5 py-0.5 text-xs rounded bg-green-500/20 text-green-300 font-medium">新增</span>
        <span className="text-sm font-semibold text-gray-100">{item.name}</span>
        <span className="text-xs text-gray-500">({item.id})</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-gray-500">优先级 {item.priority}</span>
        <span className="text-xs text-gray-500">权重 {item.weight}</span>
      </div>
    </div>
    <div className="text-xs text-gray-500 mt-1">适用标的：{item.target_pool.join(', ')}</div>
  </div>
);

// ============ 策略卡片（移除） ============
const RemovedStrategyCard: React.FC<{ item: StrategyRemovedItem }> = ({ item }) => (
  <div className="border-l-4 border-l-red-500 bg-gray-950/40 border border-gray-700 rounded-r-lg p-3">
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="px-1.5 py-0.5 text-xs rounded bg-red-500/20 text-red-300 font-medium">移出</span>
        <span className="text-sm font-semibold text-gray-400 line-through">{item.name}</span>
        <span className="text-xs text-gray-600">({item.id})</span>
      </div>
      <span className="text-xs text-gray-500">上一版本优先级：{item.prev_priority || '-'}</span>
    </div>
  </div>
);

// ============ 策略卡片（调整） ============
const ModifiedStrategyCard: React.FC<{ item: StrategyModifiedItem }> = ({ item }) => {
  const hasPrioChange = item.old_priority !== undefined && item.new_priority !== undefined;
  const hasWeightChange = item.old_weight !== undefined && item.new_weight !== undefined;
  const hasLogicChange = !!item.old_trigger_logic && !!item.new_trigger_logic;

  return (
    <div className="border-l-4 border-l-yellow-500 bg-gray-950/40 border border-gray-700 rounded-r-lg p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="px-1.5 py-0.5 text-xs rounded bg-yellow-500/20 text-yellow-300 font-medium">调整</span>
          <span className="text-sm font-semibold text-gray-100">{item.name}</span>
          <span className="text-xs text-gray-500">({item.id})</span>
        </div>
      </div>
      <div className="text-xs text-gray-500 mt-1 space-x-3">
        {hasPrioChange && (
          <span>
            优先级 <span className="text-gray-500">{item.old_priority}</span>
            <span className="mx-1 text-yellow-400">→</span>
            <span className="text-yellow-300">{item.new_priority}</span>
          </span>
        )}
        {hasWeightChange && (
          <span>
            权重 <span className="text-gray-500">{item.old_weight}</span>
            <span className="mx-1 text-yellow-400">→</span>
            <span className="text-yellow-300">{item.new_weight}</span>
          </span>
        )}
      </div>
      {hasLogicChange && (
        <div className="text-xs text-gray-500 mt-1">
          触发逻辑已更新
        </div>
      )}
    </div>
  );
};

// ============ 分组区块 ============
const ChangeGroup: React.FC<{
  title: string;
  count: number;
  color: 'green' | 'red' | 'yellow' | 'blue';
  defaultExpanded?: boolean;
  children: React.ReactNode;
}> = ({ title, count, color, defaultExpanded = true, children }) => {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const colorMap = {
    green: 'text-green-300 bg-green-500/10 border-green-500/30',
    red: 'text-red-300 bg-red-500/10 border-red-500/30',
    yellow: 'text-yellow-300 bg-yellow-500/10 border-yellow-500/30',
    blue: 'text-blue-300 bg-blue-500/10 border-blue-500/30',
  };

  return (
    <div className="border border-gray-700/50 rounded-lg overflow-hidden">
      <button
        type="button"
        className={`w-full px-3 py-2 flex items-center justify-between text-sm font-medium border-b ${colorMap[color]}`}
        onClick={() => setExpanded(!expanded)}
      >
        <span>{title}（{count}）</span>
        <span className="text-xs text-gray-500">{expanded ? '收起 ▲' : '展开 ▼'}</span>
      </button>
      {expanded && <div className="p-2 space-y-2">{children}</div>}
    </div>
  );
};

// ============ 主页面 ============
const ChangePage: React.FC = () => {
  const [snapshots, setSnapshots] = useState<ChangeSnapshotItem[]>([]);
  const [compare, setCompare] = useState<ChangeCompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState<string | null>(null);

  // 选中的两个版本 ID
  const [selectedIds, setSelectedIds] = useState<[number, number]>([0, 0]);

  // 加载快照列表
  const loadSnapshots = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchChangeSnapshots(48);
      setSnapshots(res.items || []);
      if (res.items && res.items.length >= 2) {
        // 默认选中最新两个
        const ids: [number, number] = [res.items[1].id, res.items[0].id];
        setSelectedIds(ids);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  // 加载对比
  const loadCompare = useCallback(async (oldId: number, newId: number) => {
    if (!oldId || !newId) return;
    setComparing(true);
    setError(null);
    try {
      const res = await fetchChangeCompare(oldId, newId);
      setCompare(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : '对比失败');
    } finally {
      setComparing(false);
    }
  }, []);

  // 初始化
  useEffect(() => {
    loadSnapshots();
  }, [loadSnapshots]);

  // 当选中的版本变化时自动对比
  useEffect(() => {
    if (selectedIds[0] && selectedIds[1]) {
      loadCompare(selectedIds[0], selectedIds[1]);
    }
  }, [selectedIds, loadCompare]);

  // 触发快照
  const handleTrigger = async () => {
    setTriggering(true);
    setTriggerMsg(null);
    try {
      const res = await triggerChangeSnapshot(false);
      setTriggerMsg(res.message || '触发成功');
      // 刷新列表
      await loadSnapshots();
    } catch (err) {
      setTriggerMsg(err instanceof Error ? err.message : '触发失败');
    } finally {
      setTriggering(false);
    }
  };

  // 时间轴点击
  const handleTimelineClick = (id: number) => {
    setSelectedIds(prev => {
      // 切换选择：如果已选中，取消；否则替换较旧的
      if (prev[0] === id) return [prev[1], 0].filter(Boolean) as [number, number];
      if (prev[1] === id) return [prev[0], 0].filter(Boolean) as [number, number];
      // 新选：替换旧位置
      return [prev[1] || id, id] as [number, number];
    });
  };

  // --- 渲染 ---

  if (loading) return <Loading message="正在加载快照列表..." />;

  const diff = compare?.diff_summary;
  const hasStockChanges = diff && (diff.new_stocks > 0 || diff.removed_stocks > 0 || diff.rating_changes > 0);
  const hasStrategyChanges = diff && (diff.strategy_changes > 0);
  const noChanges = diff && !hasStockChanges && !hasStrategyChanges;

  const selectedA = snapshots.find(s => s.id === selectedIds[0]);
  const selectedB = snapshots.find(s => s.id === selectedIds[1]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            策略变动对比
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            按小时追踪标的推荐与策略建议变化，驱动原因一目了然
          </p>
        </div>
        <button
          type="button"
          disabled={triggering}
          className={`px-4 py-2 text-sm rounded-lg transition-all ${
            triggering
              ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
              : 'bg-gradient-to-r from-blue-500 to-purple-500 text-white hover:shadow-lg hover:shadow-purple-500/20'
          }`}
          onClick={handleTrigger}
        >
          {triggering ? '生成中...' : '🔄 手动生成快照'}
        </button>
      </div>

      {triggerMsg && (
        <div className="text-sm text-gray-300 bg-gray-800/60 border border-gray-700 rounded-lg px-4 py-2">
          {triggerMsg}
        </div>
      )}

      {error && <Error message={error} />}

      {/* 窗口说明条 */}
      <WindowInfo compare={compare} />

      {snapshots.length === 0 ? (
        <Empty message="暂无快照数据，请点击「手动生成快照」按钮创建第一个版本" />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[200px_1fr] gap-4">
          {/* 左：时间轴 */}
          <div className="border border-gray-700 rounded-lg bg-gray-950/30 p-3 space-y-1 max-h-[600px] overflow-y-auto">
            <div className="text-xs text-gray-500 mb-2 font-medium">
              版本时间轴
              <span className="ml-1 text-gray-600">（点击选择两个版本对比）</span>
            </div>
            {snapshots.map((item, idx) => {
              const isSelected = item.id === selectedIds[0] || item.id === selectedIds[1];
              const isNewer = item.id === selectedIds[1];
              const isOlder = item.id === selectedIds[0];
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center justify-between ${
                    isSelected
                      ? isNewer
                        ? 'bg-purple-500/20 border border-purple-500/40 text-purple-200'
                        : 'bg-blue-500/20 border border-blue-500/40 text-blue-200'
                      : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-200'
                  }`}
                  onClick={() => handleTimelineClick(item.id)}
                  title={`窗口：${fmtTime(item.window_start)} ~ ${fmtTime(item.window_end)} | 新闻：${item.news_total} 条`}
                >
                  <span className="flex items-center gap-1.5">
                    <StatusBadge status={item.generate_status} />
                    {versionLabel(item)}
                  </span>
                  <span className="text-xs text-gray-600">
                    {isNewer ? '新版' : isOlder ? '旧版' : ''}
                  </span>
                </button>
              );
            })}
          </div>

          {/* 右：对比内容 */}
          <div className="space-y-4">
            {comparing ? (
              <Loading message="正在对比..." />
            ) : !compare ? (
              <Empty message="请在左侧时间轴中选择两个版本进行对比" />
            ) : noChanges ? (
              <div className="border border-gray-700 rounded-lg bg-gray-950/30 p-8 text-center">
                <div className="text-4xl mb-3">📭</div>
                <div className="text-gray-300 font-medium">无新闻更新，标的和策略推荐暂不变动</div>
                <div className="text-gray-500 text-sm mt-1">
                  {fmtTime(selectedB?.version_time)} vs {fmtTime(selectedA?.version_time)}：无可感知变化
                </div>
              </div>
            ) : (
              <>
                {/* 变动总览看板 */}
                {diff && (
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <SummaryCard
                      label="新增标的"
                      value={diff.new_stocks}
                      subtext="本小时新增正面舆情驱动"
                      colorClass="border-green-500/30 bg-green-500/5"
                      icon="🟢"
                    />
                    <SummaryCard
                      label="移除标的"
                      value={diff.removed_stocks}
                      subtext="旧新闻影响力消退"
                      colorClass="border-red-500/30 bg-red-500/5"
                      icon="🔴"
                    />
                    <SummaryCard
                      label="评级调整"
                      value={diff.rating_changes}
                      subtext="舆情倾向变化"
                      colorClass="border-yellow-500/30 bg-yellow-500/5"
                      icon="🟡"
                    />
                    <SummaryCard
                      label="策略变动"
                      value={diff.strategy_changes}
                      subtext="权重/优先级更新"
                      colorClass="border-blue-500/30 bg-blue-500/5"
                      icon="🔵"
                    />
                  </div>
                )}

                {/* 标的变动区 */}
                {hasStockChanges && compare && (
                  <div>
                    <h2 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
                      <span className="w-1 h-4 bg-gradient-to-b from-blue-400 to-purple-400 rounded-full" />
                      标的推荐变动
                    </h2>
                    <div className="space-y-2">
                      {compare.stock_changes.added.length > 0 && (
                        <ChangeGroup title="新增标的" count={compare.stock_changes.added.length} color="green">
                          {compare.stock_changes.added.map(item => (
                            <AddedStockCard key={item.code} item={item} />
                          ))}
                        </ChangeGroup>
                      )}
                      {compare.stock_changes.removed.length > 0 && (
                        <ChangeGroup title="移除标的" count={compare.stock_changes.removed.length} color="red">
                          {compare.stock_changes.removed.map(item => (
                            <RemovedStockCard key={item.code} item={item} />
                          ))}
                        </ChangeGroup>
                      )}
                      {compare.stock_changes.modified.length > 0 && (
                        <ChangeGroup title="评级/权重调整" count={compare.stock_changes.modified.length} color="yellow">
                          {compare.stock_changes.modified.map((item, i) => (
                            <ModifiedStockCard key={`${item.code}-${i}`} item={item} />
                          ))}
                        </ChangeGroup>
                      )}
                    </div>
                  </div>
                )}

                {/* 策略变动区 */}
                {hasStrategyChanges && compare && (
                  <div>
                    <h2 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
                      <span className="w-1 h-4 bg-gradient-to-b from-purple-400 to-pink-400 rounded-full" />
                      策略建议变动
                    </h2>
                    <div className="space-y-2">
                      {compare.strategy_changes.added.length > 0 && (
                        <ChangeGroup title="新增策略" count={compare.strategy_changes.added.length} color="green">
                          {compare.strategy_changes.added.map(item => (
                            <AddedStrategyCard key={item.id} item={item} />
                          ))}
                        </ChangeGroup>
                      )}
                      {compare.strategy_changes.removed.length > 0 && (
                        <ChangeGroup title="移除策略" count={compare.strategy_changes.removed.length} color="red">
                          {compare.strategy_changes.removed.map(item => (
                            <RemovedStrategyCard key={item.id} item={item} />
                          ))}
                        </ChangeGroup>
                      )}
                      {compare.strategy_changes.modified.length > 0 && (
                        <ChangeGroup title="权重/优先级调整" count={compare.strategy_changes.modified.length} color="yellow">
                          {compare.strategy_changes.modified.map((item, i) => (
                            <ModifiedStrategyCard key={`${item.id}-${i}`} item={item} />
                          ))}
                        </ChangeGroup>
                      )}
                    </div>
                  </div>
                )}

                {/* 无变动标的折叠区 */}
                {compare && (
                  <ChangeGroup title="无变动标的" count={
                    (compare.new_summary && (compare.stock_changes.added.length + compare.stock_changes.removed.length + compare.stock_changes.modified.length) > 0)
                      ? Math.max(0, 0) : 0
                  } color="blue" defaultExpanded={false}>
                    <div className="text-xs text-gray-500 p-2">
                      其余标的推荐评级与权重在本窗口内未发生变化。
                    </div>
                  </ChangeGroup>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ChangePage;
