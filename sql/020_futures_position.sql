-- 016：期货持仓排名（中金所国债期货）
--
-- 数据来源：中金所成交持仓排名 CSV（公开接口，无需认证）
--   http://www.cffex.com.cn/sj/ccpm/YYYYMM/DD/{品种}_1.csv
--
-- 覆盖品种：T(10年) / TF(5年) / TS(2年) / TL(30年) —— 仅国债期货。
-- 落库策略：**每日快照**，逐步积累；按 (日期,合约,会员,排名口径) 唯一去重保证幂等。

CREATE TABLE IF NOT EXISTS futures_position (
  id CHAR(36) NOT NULL,
  trade_date DATE NOT NULL COMMENT '交易日',
  variety VARCHAR(8) NOT NULL COMMENT '品种：T/TF/TS/TL',
  contract VARCHAR(24) NOT NULL COMMENT '合约代码，如 T2612',
  rank_no INT NOT NULL COMMENT '排名（1-20）',
  volume_trader VARCHAR(80) NULL COMMENT '成交量排名-会员简称',
  volume INT NULL COMMENT '成交量',
  volume_change INT NULL COMMENT '成交量较上一交易日增减',
  long_trader VARCHAR(80) NULL COMMENT '持买单量排名-会员简称',
  long_position INT NULL COMMENT '持买单量',
  long_change INT NULL COMMENT '持买单量增减',
  short_trader VARCHAR(80) NULL COMMENT '持卖单量排名-会员简称',
  short_position INT NULL COMMENT '持卖单量',
  short_change INT NULL COMMENT '持卖单量增减',
  source VARCHAR(40) NOT NULL DEFAULT 'cffex',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_futures_position (trade_date, contract, rank_no),
  KEY idx_futures_position_variety (variety, trade_date),
  KEY idx_futures_position_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='国债期货持仓排名（中金所每日快照）';