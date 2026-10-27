-- 024：美债收益率与中美利差
--
-- 数据源：美国财政部官方 CSV（免密钥、官方公开、合规）
--   https://home.treasury.gov/resource-center/data-chart-center/interest-rates/
-- 只存关键期限（2Y/10Y/30Y），避免无谓的全曲线存储。
--
-- 中美利差 = 中债 10Y − 美债 10Y，在查询时与 yield_data 相减计算，不落库。

CREATE TABLE IF NOT EXISTS treasury_yield (
  id BIGINT(20) NOT NULL AUTO_INCREMENT,
  trade_date DATE NOT NULL COMMENT '日期（美方交易日）',
  term VARCHAR(10) NOT NULL COMMENT '期限码：2Y/10Y/30Y',
  value DECIMAL(10,4) NOT NULL COMMENT '收益率(%)',
  source VARCHAR(40) NOT NULL DEFAULT 'us_treasury',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_treasury_yield (trade_date, term),
  KEY idx_treasury_yield_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='美债收益率（美国财政部）';