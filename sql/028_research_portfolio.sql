-- 028：账号级研究组合与持仓风险台账
--
-- 仅保存用户录入的研究配置及指标快照，不保存实时估值、交易或收益数据。
-- size_amount 统一使用人民币元；weight_pct/yield_pct 使用百分数口径。
-- 权重总和、乐观锁与跨用户校验由组合服务在父组合行锁事务内执行。

CREATE TABLE IF NOT EXISTS `research_portfolios` (
  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_username` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `size_amount` decimal(20,2) NOT NULL DEFAULT 0.00 COMMENT '研究规模（人民币元，非真实市值）',
  `as_of_date` date NOT NULL COMMENT '持仓指标对应日期',
  `target_duration` decimal(10,4) DEFAULT NULL COMMENT '可选目标久期（年）',
  `status` varchar(24) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT 'active / archived',
  `version` int(10) unsigned NOT NULL DEFAULT 1 COMMENT '乐观锁版本',
  `archived_at` datetime(6) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_research_portfolio_owner_updated` (`owner_username`, `status`, `updated_at`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='账号级研究组合（研究配置，不含交易与实时估值）';

CREATE TABLE IF NOT EXISTS `research_portfolio_holdings` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `portfolio_id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `bond_code` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `bond_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `asset_category` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `weight_pct` decimal(9,6) NOT NULL COMMENT '配置权重（百分数）',
  `yield_pct` decimal(10,6) DEFAULT NULL COMMENT '用户录入到期收益率（百分数）',
  `duration_years` decimal(10,4) DEFAULT NULL COMMENT '用户录入久期（年）',
  `sort_order` int(11) NOT NULL DEFAULT 0,
  `note` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_research_portfolio_holding_code` (`portfolio_id`, `bond_code`),
  KEY `idx_research_portfolio_holding_order` (`portfolio_id`, `sort_order`, `id`),
  CONSTRAINT `fk_research_portfolio_holding_portfolio`
    FOREIGN KEY (`portfolio_id`) REFERENCES `research_portfolios` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='研究组合持仓及手工指标快照';
