-- 018：信用债收益率曲线与信用利差
--
-- 数据源：中债 historyDown 接口，nameType=2 为中短期票据收益率曲线。
-- 与现有国债曲线（nameType=1）走**同一个接口**，仅参数不同。
--
-- 设计取舍：**独立建表，不改 yield_data 主键**。
-- yield_data 现为 (date, period) 只装国债；若加入信用债维度需改主键，
-- 会牵动 db_yield / discover / returns / dashboard_service 四处下游查询。
-- 利差在查询时与国债相减计算，无需落库。

CREATE TABLE IF NOT EXISTS credit_curve (
  id BIGINT(20) NOT NULL AUTO_INCREMENT,
  trade_date DATE NOT NULL COMMENT '日期',
  term VARCHAR(10) NOT NULL COMMENT '期限码：1Y/2Y/3Y/5Y/7Y/10Y/15Y/20Y/30Y',
  value DECIMAL(10,4) NOT NULL COMMENT '中短期票据到期收益率(%)',
  curve_type VARCHAR(40) NOT NULL DEFAULT 'medium_term_note' COMMENT '曲线类型',
  source VARCHAR(40) NOT NULL DEFAULT 'chinabond',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_credit_curve (trade_date, term),
  KEY idx_credit_curve_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='中债中短期票据收益率曲线';