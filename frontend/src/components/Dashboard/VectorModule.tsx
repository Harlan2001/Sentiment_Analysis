/**
 * 模块D：向量库 & 存储
 */
import React from 'react';
import type { VectorModuleData } from '../../types';
import { PanelTitle, MetricCard, ProgressBar } from './Widgets';
import { ALERT } from './constants';

interface Props { data: VectorModuleData; }

export const VectorModule: React.FC<Props> = ({ data }) => {
  const pendingStatus = data.pending_count > ALERT.VECTOR_PENDING_RED ? 'danger'
    : data.pending_count > ALERT.VECTOR_PENDING_YELLOW ? 'warning' : 'normal';
  const coverageStatus = data.coverage_pct < ALERT.VECTOR_COVERAGE_YELLOW ? 'warning' : 'normal';

  return (
    <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4">
      <PanelTitle title="向量库 & 存储" icon="🔍" />

      <div className="grid grid-cols-2 gap-2 mb-3">
        <MetricCard label="已向量化" value={data.indexed_count.toLocaleString()} />
        <MetricCard label="待向量化" value={data.pending_count.toLocaleString()} status={pendingStatus} />
      </div>

      {/* D6: 向量化覆盖率 */}
      <div className="mb-3">
        <ProgressBar label="向量化覆盖率" value={data.coverage_pct} status={coverageStatus} />
      </div>
    </div>
  );
};
