-- 023：因子事件研究（回测仿真）
--
-- 用现有 news_factor（6.4 万行，跨 2021-2026，覆盖 381 个因子）做事件研究：
--   某因子在 t 时刻出现（带 direction）→ 观察之后 T+N 的 10Y 国债收益率变动
--
-- 为什么不测 directional 信号：现有信号日志仅 47 行 / 8 个高度重叠的时间窗，
-- 9 个因子各只有 1 个样本，做出来每格 1~2 条反而误导。news_factor 样本量大三个数量级。
--
-- 结果**批量计算后落库**，页面读结果（6.4 万行全表扫描不适合实时算）。

CREATE TABLE IF NOT EXISTS factor_event_study (
  id BIGINT(20) NOT NULL AUTO_INCREMENT,
  factor_code VARCHAR(255) NOT NULL COMMENT '因子代码',
  factor_name VARCHAR(255) NULL,
  holding_days INT NOT NULL COMMENT '持有期（交易日）：1/5/20',
  sample_size INT NOT NULL DEFAULT 0 COMMENT '样本数',
  hit_count INT NOT NULL DEFAULT 0 COMMENT '方向命中数',
  hit_rate DECIMAL(6,4) NULL COMMENT '方向命中率',
  majority_base DECIMAL(6,4) NULL COMMENT '多数类基准（无脑猜多数方向的命中率）',
  avg_move_bp DECIMAL(10,4) NULL COMMENT '平均变动(bp)',
  median_move_bp DECIMAL(10,4) NULL COMMENT '中位数变动(bp)',
  period_start DATE NULL COMMENT '样本起始',
  period_end DATE NULL COMMENT '样本结束',
  period_label VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT '统计分组：all 或年度(如 2025)',
  computed_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '计算时间',
  PRIMARY KEY (id),
  UNIQUE KEY uq_factor_event_study (factor_code, holding_days, period_label),
  KEY idx_factor_event_study_code (factor_code, holding_days),
  KEY idx_factor_event_study_hit (hit_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='因子事件研究结果';