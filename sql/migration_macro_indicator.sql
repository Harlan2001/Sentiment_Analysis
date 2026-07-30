-- ============================================================
-- 宏观经济指标数据表 — 数据库迁移
-- 执行方式：在 Sentiment_analysis 库中执行此 SQL
-- ============================================================

CREATE TABLE IF NOT EXISTS `macro_indicator_data` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `indicator_code` varchar(100) NOT NULL COMMENT '指标代码，英文大写+下划线',
  `indicator_name` varchar(200) NOT NULL COMMENT '指标原始中文名称',
  `unit` varchar(50) DEFAULT NULL COMMENT '单位',
  `period_202607` decimal(20,4) DEFAULT NULL COMMENT '2026年7月',
  `period_202606` decimal(20,4) DEFAULT NULL COMMENT '2026年6月',
  `period_202605` decimal(20,4) DEFAULT NULL COMMENT '2026年5月',
  `period_202604` decimal(20,4) DEFAULT NULL COMMENT '2026年4月',
  `period_202603` decimal(20,4) DEFAULT NULL COMMENT '2026年3月',
  `period_202602` decimal(20,4) DEFAULT NULL COMMENT '2026年2月',
  `period_202601` decimal(20,4) DEFAULT NULL COMMENT '2026年1月',
  `period_202512` decimal(20,4) DEFAULT NULL COMMENT '2025年12月',
  `period_202511` decimal(20,4) DEFAULT NULL COMMENT '2025年11月',
  `period_202510` decimal(20,4) DEFAULT NULL COMMENT '2025年10月',
  `period_202509` decimal(20,4) DEFAULT NULL COMMENT '2025年9月',
  `period_202508` decimal(20,4) DEFAULT NULL COMMENT '2025年8月',
  `period_202507` decimal(20,4) DEFAULT NULL COMMENT '2025年7月',
  `period_202506` decimal(20,4) DEFAULT NULL COMMENT '2025年6月',
  `period_202505` decimal(20,4) DEFAULT NULL COMMENT '2025年5月',
  `period_202504` decimal(20,4) DEFAULT NULL COMMENT '2025年4月',
  `period_202503` decimal(20,4) DEFAULT NULL COMMENT '2025年3月',
  `period_202502` decimal(20,4) DEFAULT NULL COMMENT '2025年2月',
  `period_202501` decimal(20,4) DEFAULT NULL COMMENT '2025年1月',
  `period_202412` decimal(20,4) DEFAULT NULL COMMENT '2024年12月',
  `period_202411` decimal(20,4) DEFAULT NULL COMMENT '2024年11月',
  `period_202410` decimal(20,4) DEFAULT NULL COMMENT '2024年10月',
  `period_202409` decimal(20,4) DEFAULT NULL COMMENT '2024年9月',
  `period_202408` decimal(20,4) DEFAULT NULL COMMENT '2024年8月',
  `period_202407` decimal(20,4) DEFAULT NULL COMMENT '2024年7月',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_indicator_code` (`indicator_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='宏观经济指标月度数据';
