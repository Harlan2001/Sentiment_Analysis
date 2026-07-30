import React from 'react';
import type { ServiceStatus } from '@/types';
import { StatusLight } from './Widgets';

interface Props {
  status: ServiceStatus;
}

export const ServiceStatusCard: React.FC<Props> = ({ status }) => (
  <div className="rounded-lg border border-gray-700/50 bg-gray-800/60 p-4 mb-4">
    <div className="text-xs text-gray-400 font-medium mb-3">🔌 底层服务健康状态</div>
    <div className="flex flex-wrap gap-3">
      <StatusLight
        label="MySQL"
        ok={status.mysql.ok}
        detail={status.mysql.ok ? `${status.mysql.latency_ms}ms` : status.mysql.error}
      />
    </div>
  </div>
);
