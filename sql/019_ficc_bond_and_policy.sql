-- 015：FICC 扩展 —— 债券档案（券池）+ 政策法规
--
-- 两张表均为**新增**，不修改任何现有表结构。
-- 多租户沿用项目惯例：owner_username 字段 + deleted_at 软删。

-- ============ 债券档案（券池）============
-- 数据来源：东方财富数据中心可转债列表（RPT_BOND_CB_LIST）。
-- 该源只覆盖交易所可转债，不含银行间国债/政金债/中票短融，故 bond_market 区分沪深两市。
CREATE TABLE IF NOT EXISTS bond_master (
  id CHAR(36) NOT NULL,
  owner_username VARCHAR(191) NOT NULL,
  bond_code VARCHAR(32) NOT NULL COMMENT '债券代码',
  bond_name VARCHAR(120) NOT NULL COMMENT '债券名称',
  bond_category VARCHAR(40) NULL COMMENT '债券类别（复用组合分析的 9 类口径）',
  bond_market VARCHAR(20) NULL COMMENT '市场：CNSESH=上交所 / CNSESZ=深交所',
  issuer VARCHAR(191) NULL COMMENT '发行人',
  rating VARCHAR(20) NULL COMMENT '评级',
  maturity_date DATE NULL COMMENT '到期日',
  coupon_rate DECIMAL(8,4) NULL COMMENT '票面利率(%)',
  issue_year VARCHAR(8) NULL COMMENT '发行年份',
  issue_scale DECIMAL(20,4) NULL COMMENT '发行规模（亿元）',
  industry VARCHAR(80) NULL COMMENT '行业',
  source VARCHAR(40) NOT NULL DEFAULT 'manual' COMMENT '数据来源：manual / excel / eastmoney',
  source_updated_at DATETIME(6) NULL COMMENT '数据源侧的更新时间',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  deleted_at DATETIME(6) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_bond_master_owner_code (owner_username, bond_code),
  KEY idx_bond_master_filter (owner_username, deleted_at, bond_category, rating),
  KEY idx_bond_master_maturity (owner_username, deleted_at, maturity_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='债券档案（券池）';

-- ============ 政策法规 ============
-- 政策事件**不新增采集源**：由现有 news + news_factor + factor(POLICY) 派生。
-- 本表只承载"需要人工确认/剔除"的状态，事件内容本身仍以 news 为准。
CREATE TABLE IF NOT EXISTS policy_event (
  id CHAR(36) NOT NULL,
  owner_username VARCHAR(191) NOT NULL,
  news_id BIGINT(20) UNSIGNED NOT NULL COMMENT '关联 news.id',
  event_date DATE NOT NULL COMMENT '事件日期（取新闻发布日期）',
  title VARCHAR(300) NOT NULL,
  source VARCHAR(50) NULL,
  policy_category VARCHAR(64) NULL COMMENT '代表性 POLICY 因子 code',
  scope ENUM('domestic','overseas') NOT NULL DEFAULT 'domestic' COMMENT '国内 / 涉外',
  status ENUM('pending','confirmed','excluded') NOT NULL DEFAULT 'pending' COMMENT '待确认 / 已确认 / 已剔除',
  note VARCHAR(500) NULL COMMENT '剔除或确认备注',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_policy_event_owner_news (owner_username, news_id),
  KEY idx_policy_event_list (owner_username, status, event_date),
  KEY idx_policy_event_date (event_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='政策事件（人工确认态）';