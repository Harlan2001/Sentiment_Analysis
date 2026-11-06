-- 生产库 Sentiment_analysis 表结构只读快照（由 scripts/export_prod_schema.py 生成）

-- 生成时间: 2026-11-06 16:44; 用于重建测试库 Sentiment_analysis_test

SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS `ai_strategy_conversations`;

DROP TABLE IF EXISTS `ai_strategy_messages`;

DROP TABLE IF EXISTS `ai_strategy_recommendation`;

DROP TABLE IF EXISTS `ai_strategy_versions`;

DROP TABLE IF EXISTS `analysis`;

DROP TABLE IF EXISTS `bond_master`;

DROP TABLE IF EXISTS `credit_curve`;

DROP TABLE IF EXISTS `daily_news_summary_tasks`;

DROP TABLE IF EXISTS `dashboard_metric_cache`;

DROP TABLE IF EXISTS `dashboard_snapshot`;

DROP TABLE IF EXISTS `factor`;

DROP TABLE IF EXISTS `factor_discovery_history`;

DROP TABLE IF EXISTS `factor_event_study`;

DROP TABLE IF EXISTS `forecast_report`;

DROP TABLE IF EXISTS `futures_position`;

DROP TABLE IF EXISTS `graph_augment_jobs`;

DROP TABLE IF EXISTS `kronos_kline_prediction`;

DROP TABLE IF EXISTS `llm_usage_log`;

DROP TABLE IF EXISTS `macro_indicator_data`;

DROP TABLE IF EXISTS `macro_signal_request_log`;

DROP TABLE IF EXISTS `news`;

DROP TABLE IF EXISTS `news_content_blocks`;

DROP TABLE IF EXISTS `news_factor`;

DROP TABLE IF EXISTS `news_importance_score`;

DROP TABLE IF EXISTS `news_vectors`;

DROP TABLE IF EXISTS `policy_analysis`;

DROP TABLE IF EXISTS `policy_document`;

DROP TABLE IF EXISTS `policy_event`;

DROP TABLE IF EXISTS `portfolio_strategy_analysis_cache`;

DROP TABLE IF EXISTS `report_analysis`;

DROP TABLE IF EXISTS `report_factor`;

DROP TABLE IF EXISTS `report_figure`;

DROP TABLE IF EXISTS `report_generation_tasks`;

DROP TABLE IF EXISTS `research_report`;

DROP TABLE IF EXISTS `strategy_change_snapshot`;

DROP TABLE IF EXISTS `strategy_push_history`;

DROP TABLE IF EXISTS `task_events`;

DROP TABLE IF EXISTS `task_runs`;

DROP TABLE IF EXISTS `treasury_yield`;

DROP TABLE IF EXISTS `user_behavior_profile`;

DROP TABLE IF EXISTS `user_page_view`;

DROP TABLE IF EXISTS `user_session`;

DROP TABLE IF EXISTS `users`;

DROP TABLE IF EXISTS `wechat_article`;

DROP TABLE IF EXISTS `workbench_conversations`;

DROP TABLE IF EXISTS `workbench_feishu_connections`;

DROP TABLE IF EXISTS `workbench_feishu_mcp_audit_logs`;

DROP TABLE IF EXISTS `workbench_feishu_oauth_states`;

DROP TABLE IF EXISTS `workbench_message_skills`;

DROP TABLE IF EXISTS `workbench_messages`;

DROP TABLE IF EXISTS `workbench_project_members`;

DROP TABLE IF EXISTS `workbench_project_memories`;

DROP TABLE IF EXISTS `workbench_projects`;

DROP TABLE IF EXISTS `workbench_skill_attachment_chunks`;

DROP TABLE IF EXISTS `workbench_skill_attachments`;

DROP TABLE IF EXISTS `workbench_skill_versions`;

DROP TABLE IF EXISTS `workbench_skills`;

DROP TABLE IF EXISTS `workbench_user_memories`;

DROP TABLE IF EXISTS `workbench_user_memory_settings`;

DROP TABLE IF EXISTS `workbench_user_system_skills`;

DROP TABLE IF EXISTS `workbench_users`;

DROP TABLE IF EXISTS `workbench_watchlist_items`;

DROP TABLE IF EXISTS `workbench_workspaces`;

DROP TABLE IF EXISTS `yield_data`;

CREATE TABLE `ai_strategy_conversations` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `owner_username` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `instrument` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(24) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
  `remote_template_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `remote_session_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `current_local_version_no` int(10) unsigned NOT NULL DEFAULT '0',
  `last_message_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ai_strategy_conversations_owner_updated` (`owner_username`,`updated_at`),
  KEY `idx_ai_strategy_conversations_owner_status` (`owner_username`,`status`),
  KEY `idx_ai_strategy_conversations_owner_deleted_updated` (`owner_username`,`deleted_at`,`updated_at`)
) ENGINE=InnoDB AUTO_INCREMENT=62 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `ai_strategy_messages` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `conversation_id` bigint(20) unsigned NOT NULL,
  `owner_username` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `sequence_no` int(10) unsigned NOT NULL,
  `role` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(24) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending',
  `remote_message_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `generated_prompt` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `system_draft_prompt` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `user_edited_prompt` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `final_sent_prompt` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `references_json` json DEFAULT NULL,
  `context_json` json DEFAULT NULL,
  `validation_json` json DEFAULT NULL COMMENT '我方验收门结论',
  `elapsed_seconds` decimal(10,3) DEFAULT NULL,
  `public_error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `stage` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `stage_updated_at` datetime DEFAULT NULL,
  `run_started_at` datetime DEFAULT NULL,
  `log_tail` mediumtext COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ai_strategy_messages_sequence` (`conversation_id`,`sequence_no`),
  KEY `idx_ai_strategy_messages_owner_conversation` (`owner_username`,`conversation_id`),
  CONSTRAINT `fk_ai_strategy_messages_conversation` FOREIGN KEY (`conversation_id`) REFERENCES `ai_strategy_conversations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=123 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `ai_strategy_recommendation` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `analysis_date` date NOT NULL,
  `news_summary` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `outcome` json NOT NULL,
  `model_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `news_count` int(11) NOT NULL DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `analysis_date` (`analysis_date`),
  KEY `idx_ai_strategy_recommendation_date` (`analysis_date`),
  KEY `idx_ai_strategy_recommendation_updated` (`updated_at`)
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI strategy and target recommendation cache';

CREATE TABLE `ai_strategy_versions` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `conversation_id` bigint(20) unsigned NOT NULL,
  `owner_username` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_message_id` bigint(20) unsigned NOT NULL,
  `local_version_no` int(10) unsigned NOT NULL,
  `remote_template_version_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `remote_template_version_no` int(11) DEFAULT NULL,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `code` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `backtest_passed` tinyint(1) DEFAULT NULL,
  `backtest_exit_code` int(11) DEFAULT NULL,
  `backtest_summary` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `backtest_metrics_json` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ai_strategy_versions_local` (`conversation_id`,`local_version_no`),
  KEY `idx_ai_strategy_versions_owner_conversation` (`owner_username`,`conversation_id`),
  KEY `fk_ai_strategy_versions_message` (`source_message_id`),
  CONSTRAINT `fk_ai_strategy_versions_conversation` FOREIGN KEY (`conversation_id`) REFERENCES `ai_strategy_conversations` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ai_strategy_versions_message` FOREIGN KEY (`source_message_id`) REFERENCES `ai_strategy_messages` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `analysis` (
  `news_id` bigint(20) unsigned NOT NULL,
  `direction` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `horizon` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `reason` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `model` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`news_id`,`model`),
  CONSTRAINT `fk_analysis_news_id` FOREIGN KEY (`news_id`) REFERENCES `news` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='新闻的分析表';

CREATE TABLE `bond_master` (
  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_username` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `bond_code` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '债券代码',
  `bond_name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '债券名称',
  `bond_category` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '债券类别（复用组合分析的 9 类口径）',
  `bond_market` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '市场：CNSESH=上交所 / CNSESZ=深交所',
  `issuer` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '发行人',
  `rating` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '评级',
  `maturity_date` date DEFAULT NULL COMMENT '到期日',
  `coupon_rate` decimal(8,4) DEFAULT NULL COMMENT '票面利率(%)',
  `issue_year` varchar(8) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '发行年份',
  `issue_scale` decimal(20,4) DEFAULT NULL COMMENT '发行规模（亿元）',
  `industry` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '行业',
  `source` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'manual' COMMENT '数据来源：manual / excel / eastmoney',
  `source_updated_at` datetime(6) DEFAULT NULL COMMENT '数据源侧的更新时间',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `deleted_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_bond_master_owner_code` (`owner_username`,`bond_code`),
  KEY `idx_bond_master_filter` (`owner_username`,`deleted_at`,`bond_category`,`rating`),
  KEY `idx_bond_master_maturity` (`owner_username`,`deleted_at`,`maturity_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='债券档案（券池）';

CREATE TABLE `credit_curve` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `trade_date` date NOT NULL COMMENT '日期',
  `term` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '期限码：1Y/2Y/3Y/5Y/7Y/10Y/15Y/20Y/30Y',
  `value` decimal(10,4) NOT NULL COMMENT '中短期票据到期收益率(%)',
  `curve_type` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'medium_term_note' COMMENT '曲线类型',
  `source` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'chinabond',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_credit_curve` (`trade_date`,`term`),
  KEY `idx_credit_curve_date` (`trade_date`)
) ENGINE=InnoDB AUTO_INCREMENT=6670 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='中债中短期票据收益率曲线';

CREATE TABLE `daily_news_summary_tasks` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `owner_username` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `sources_json` json DEFAULT NULL,
  `focus` varchar(1000) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending',
  `news_count` int(10) unsigned NOT NULL DEFAULT '0',
  `source_stats_json` json DEFAULT NULL,
  `summary` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `references_json` json DEFAULT NULL,
  `error_message` varchar(1000) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `retry_of_id` bigint(20) unsigned DEFAULT NULL,
  `started_at` datetime(6) DEFAULT NULL,
  `completed_at` datetime(6) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `deleted_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_daily_news_summary_owner_updated` (`owner_username`,`updated_at`),
  KEY `idx_daily_news_summary_owner_status` (`owner_username`,`status`),
  KEY `idx_daily_news_summary_range` (`start_date`,`end_date`),
  KEY `idx_daily_news_summary_owner_deleted_updated` (`owner_username`,`deleted_at`,`updated_at`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `dashboard_metric_cache` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `calc_time` datetime NOT NULL COMMENT '指标计算时间',
  `cache_type` varchar(50) NOT NULL DEFAULT 'core',
  `metrics_json` longtext,
  `service_status` json NOT NULL COMMENT '底层服务状态',
  PRIMARY KEY (`id`),
  KEY `idx_calc_time` (`calc_time`),
  KEY `idx_cache_hit` (`cache_type`,`calc_time`)
) ENGINE=InnoDB AUTO_INCREMENT=467 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='每5分钟预计算A-F指标，前端直接读取缓存';

CREATE TABLE `dashboard_snapshot` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `snapshot_time` datetime NOT NULL COMMENT '快照时间',
  `metrics_json` json NOT NULL COMMENT '完整指标JSON',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_snapshot_time` (`snapshot_time`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='开发者看板历史快照 - 每小时保存一次';

CREATE TABLE `factor` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `code` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `name` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `category` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `factor_type` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  KEY `idx_factor_code` (`code`),
  KEY `idx_factor_category` (`category`(100))
) ENGINE=InnoDB AUTO_INCREMENT=382 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='因子表';

CREATE TABLE `factor_discovery_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `code` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '因子代码',
  `name` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '因子名称',
  `category` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '一级分类',
  `factor_type` enum('quantitative','conceptual') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '因子类型：量化/概念',
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '因子描述',
  `source_news_id` int(11) DEFAULT NULL COMMENT '来源新闻ID',
  `extracted_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '提取的原始文本',
  `created_by_model` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '创建该因子的模型名称',
  `max_similarity_score` float DEFAULT '0' COMMENT '最大相似度得分',
  `most_similar_factor_code` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '最相似因子代码',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_discovery_code` (`code`),
  KEY `idx_discovery_source_news_id` (`source_news_id`),
  KEY `idx_discovery_created_at` (`created_at`),
  KEY `idx_discovery_similarity` (`max_similarity_score`)
) ENGINE=InnoDB AUTO_INCREMENT=500 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='因子发现历史表';

CREATE TABLE `factor_event_study` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `factor_code` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '因子代码',
  `factor_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `holding_days` int(11) NOT NULL COMMENT '持有期（交易日）：1/5/20',
  `sample_size` int(11) NOT NULL DEFAULT '0' COMMENT '样本数',
  `hit_count` int(11) NOT NULL DEFAULT '0' COMMENT '方向命中数',
  `hit_rate` decimal(6,4) DEFAULT NULL COMMENT '方向命中率',
  `majority_base` decimal(6,4) DEFAULT NULL COMMENT '多数类基准（无脑猜多数方向的命中率）',
  `avg_move_bp` decimal(10,4) DEFAULT NULL COMMENT '平均变动(bp)',
  `median_move_bp` decimal(10,4) DEFAULT NULL COMMENT '中位数变动(bp)',
  `period_start` date DEFAULT NULL COMMENT '样本起始',
  `period_end` date DEFAULT NULL COMMENT '样本结束',
  `period_label` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'all' COMMENT '统计分组：all 或年度(如 2025)',
  `computed_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '计算时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_factor_event_study` (`factor_code`,`holding_days`,`period_label`),
  KEY `idx_factor_event_study_code` (`factor_code`,`holding_days`),
  KEY `idx_factor_event_study_hit` (`hit_rate`)
) ENGINE=InnoDB AUTO_INCREMENT=3334 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='因子事件研究结果';

CREATE TABLE `forecast_report` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `trade_date` date NOT NULL COMMENT '分析交易日',
  `model_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '使用的模型名称',
  `prompt_version` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Prompt版本',
  `forecast_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '预测类型: full_report/day/week/month',
  `prediction` json NOT NULL COMMENT '预测结果JSON',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_date_type` (`trade_date`,`forecast_type`),
  KEY `idx_trade_date` (`trade_date`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=131 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='市场预测报告表';

CREATE TABLE `futures_position` (
  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `trade_date` date NOT NULL COMMENT '交易日',
  `variety` varchar(8) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '品种：T/TF/TS/TL',
  `contract` varchar(24) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '合约代码，如 T2612',
  `rank_no` int(11) NOT NULL COMMENT '排名（1-20）',
  `volume_trader` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '成交量排名-会员简称',
  `volume` int(11) DEFAULT NULL COMMENT '成交量',
  `volume_change` int(11) DEFAULT NULL COMMENT '成交量较上一交易日增减',
  `long_trader` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '持买单量排名-会员简称',
  `long_position` int(11) DEFAULT NULL COMMENT '持买单量',
  `long_change` int(11) DEFAULT NULL COMMENT '持买单量增减',
  `short_trader` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '持卖单量排名-会员简称',
  `short_position` int(11) DEFAULT NULL COMMENT '持卖单量',
  `short_change` int(11) DEFAULT NULL COMMENT '持卖单量增减',
  `source` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'cffex',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_futures_position` (`trade_date`,`contract`,`rank_no`),
  KEY `idx_futures_position_variety` (`variety`,`trade_date`),
  KEY `idx_futures_position_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='国债期货持仓排名（中金所每日快照）';

CREATE TABLE `graph_augment_jobs` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `news_id` bigint(20) unsigned NOT NULL COMMENT '关联新闻ID',
  `run_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '图谱补全任务ID',
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'RUNNING' COMMENT 'RUNNING/WAITING_REVIEW/COMPLETED/FAILED/REJECTED',
  `stage` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '当前阶段',
  `result_json` json DEFAULT NULL COMMENT '补全结果JSON',
  `extract_json` json DEFAULT NULL COMMENT '抽取结果JSON',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_run_id` (`run_id`),
  KEY `idx_news_id` (`news_id`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_graph_augment_news_id` FOREIGN KEY (`news_id`) REFERENCES `news` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='图谱补全任务表';

CREATE TABLE `kronos_kline_prediction` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `variety_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '品种代码 TS/TF/T/TL',
  `request_params` json DEFAULT NULL COMMENT '请求参数',
  `input_kline_data` json DEFAULT NULL COMMENT '输入K线数据/json：预测使用的lookback条历史OHLCV样本',
  `prediction_result` json DEFAULT NULL COMMENT '预测结果/json：仅含预测N日OHLCV及展示用min-max区间',
  `trend` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT '平' COMMENT '趋势方向',
  `last_close` decimal(10,4) DEFAULT '0.0000' COMMENT '最新收盘价',
  `last_date` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT '' COMMENT '最新日期',
  `model_used` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'Kronos-small' COMMENT '模型',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_variety_code` (`variety_code`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Kronos K线预测记录表';

CREATE TABLE `llm_usage_log` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL DEFAULT '0' COMMENT '用户ID，系统调用为0',
  `username` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'system' COMMENT '用户名',
  `call_source` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '调用来源: chat/analysis/strategy/change',
  `model_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '模型名称，如 doubao/deepseek/qwen',
  `provider_model` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'provider完整模型名',
  `prompt_tokens` int(11) NOT NULL DEFAULT '0' COMMENT '输入Token数',
  `completion_tokens` int(11) NOT NULL DEFAULT '0' COMMENT '输出Token数',
  `total_tokens` int(11) NOT NULL DEFAULT '0' COMMENT '总Token数',
  `request_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '请求唯一ID，链路追踪',
  `success` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否成功',
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '失败原因',
  `latency_ms` int(10) unsigned DEFAULT NULL COMMENT '请求耗时(ms)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_username` (`username`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_call_source` (`call_source`),
  KEY `idx_model_name` (`model_name`),
  KEY `idx_user_date` (`user_id`,`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=2887 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='LLM调用Token消耗日志';

CREATE TABLE `macro_indicator_data` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `zbcode` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '指标代码',
  `name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '指标中文名称',
  `datestr` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '日期，格式 YYYYMM，如 202201',
  `value` double DEFAULT NULL COMMENT '指标数值',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_zbcode_date` (`zbcode`,`datestr`),
  KEY `idx_zbcode` (`zbcode`),
  KEY `idx_datestr` (`datestr`),
  KEY `idx_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=7093 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='宏观经济指标数据表';

CREATE TABLE `macro_signal_request_log` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID，自增',
  `request_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '请求唯一ID(UUID)，同一次API调用的多个因子共享同一ID',
  `factor_code` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '因子代码，每行记录一个因子，如 OMO_VOLUME_SIGNAL',
  `signal_type` enum('directional','presence') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '信号类型：presence=事件是否存在(0/1)，directional=方向性信号(-1/0/1)',
  `query_start_time` datetime DEFAULT NULL COMMENT '业务查询时间窗口起点（来自请求参数 start_time，解析失败时为空）',
  `query_end_time` datetime DEFAULT NULL COMMENT '业务查询时间窗口终点（来自请求参数 end_time，解析失败时为空）',
  `decay_lambda` decimal(4,2) DEFAULT NULL COMMENT '时间衰减系数，仅 directional 模式有效，默认 0.1',
  `signal_value` tinyint(4) DEFAULT NULL COMMENT '信号值：directional: -1(利空)/0(中性)/1(利多)；presence: 0(无)/1(有)',
  `confidence` decimal(6,4) DEFAULT NULL COMMENT '置信度[0,1]；presence 统一为NULL，directional 按时间衰减权重归一化',
  `news_count` int(11) NOT NULL DEFAULT '0' COMMENT '命中该因子的新闻数量（实际参与信号计算的条数，非扫描总数）',
  `queried_news` json DEFAULT NULL COMMENT '命中该因子的新闻ID列表，用于策略复盘，格式：[1, 2, 3]',
  `success` tinyint(1) NOT NULL DEFAULT '1' COMMENT '本次计算是否成功：1=成功，0=失败',
  `error_message` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '失败原因，success=0 时填写；参数校验失败或服务异常均记录',
  `started_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '请求进入路由的时间戳（含毫秒）',
  `finished_at` datetime(3) DEFAULT NULL COMMENT '请求处理完成的时间戳（含毫秒）',
  `latency_ms` int(10) unsigned DEFAULT NULL COMMENT '请求耗时（毫秒），finished_at - started_at',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_request_id_factor` (`request_id`,`factor_code`),
  KEY `idx_started_at` (`started_at`),
  KEY `idx_factor_signal_started` (`factor_code`,`signal_type`,`started_at`),
  KEY `idx_query_range` (`query_start_time`,`query_end_time`),
  KEY `idx_success_started` (`success`,`started_at`)
) ENGINE=InnoDB AUTO_INCREMENT=7902 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='宏观信号API请求日志表';

CREATE TABLE `news` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `source` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_news_id` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `title` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `author` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pub_time` datetime DEFAULT NULL,
  `url` varchar(1024) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `global_uid` char(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `content_structure` json DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `indexed` tinyint(1) DEFAULT '0' COMMENT '是否已建立向量索引',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_global_uid` (`global_uid`),
  KEY `idx_source` (`source`),
  KEY `idx_pub_time` (`pub_time`)
) ENGINE=InnoDB AUTO_INCREMENT=19426 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='新闻主表';

CREATE TABLE `news_content_blocks` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `news_id` bigint(20) unsigned NOT NULL,
  `block_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '内容块类型: text, quote, image, heading, table',
  `block_order` int(11) NOT NULL COMMENT '内容块顺序',
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '文本内容',
  `heading_level` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '标题级别: h1, h2, h3, h4, h5, h6',
  `image_url` varchar(2048) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '图片URL',
  `image_alt` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '图片描述',
  `image_width` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '图片宽度',
  `table_caption` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '表格标题',
  `table_unit` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '表格单位',
  `table_headers` json DEFAULT NULL COMMENT '表格表头数据 (数组格式)',
  `table_rows` json DEFAULT NULL COMMENT '表格行数据 (二维数组格式)',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_news_id` (`news_id`),
  KEY `idx_block_type` (`block_type`),
  KEY `idx_block_order` (`block_order`),
  CONSTRAINT `fk_news_content_blocks_news_id` FOREIGN KEY (`news_id`) REFERENCES `news` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=528836 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='新闻内容块表（用于前端渲染）';

CREATE TABLE `news_factor` (
  `news_id` bigint(20) unsigned NOT NULL,
  `factor_id` int(11) NOT NULL,
  `direction` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `driver` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `model` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `pub_time` datetime DEFAULT NULL COMMENT '冗余新闻发布时间，用于时间过滤',
  PRIMARY KEY (`news_id`,`factor_id`,`model`),
  KEY `idx_news_factor_factor_id` (`factor_id`),
  KEY `idx_news_factor_news_id` (`news_id`),
  KEY `idx_news_factor_pub_time` (`pub_time`),
  CONSTRAINT `fk_news_factor_factor_id` FOREIGN KEY (`factor_id`) REFERENCES `factor` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_news_factor_news_id` FOREIGN KEY (`news_id`) REFERENCES `news` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='新闻及其对应因子表';

CREATE TABLE `news_importance_score` (
  `news_id` bigint(20) unsigned NOT NULL COMMENT '新闻 ID（FK news.id）',
  `score_version` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'v1' COMMENT '打分公式版本',
  `importance_score` decimal(8,4) NOT NULL DEFAULT '0.0000' COMMENT '静态重要性分 I_news，0-100',
  `s_direction` decimal(6,4) DEFAULT NULL COMMENT '信号：最佳模型方向强度',
  `s_agreement` decimal(6,4) DEFAULT NULL COMMENT '信号：多模型方向一致性',
  `s_horizon` decimal(6,4) DEFAULT NULL COMMENT '信号：期限',
  `s_category` decimal(6,4) DEFAULT NULL COMMENT '信号：因子最高类别权重',
  `s_hit` decimal(6,4) DEFAULT NULL COMMENT '信号：因子命中率先验均值',
  `s_nfactor` decimal(6,4) DEFAULT NULL COMMENT '信号：关联因子数量（饱和归一）',
  `s_rich` decimal(6,4) DEFAULT NULL COMMENT '信号：内容丰富度（图/表/标题块）',
  `s_policy` tinyint(1) NOT NULL DEFAULT '0' COMMENT '信号：政策标记 0/1',
  `s_source` decimal(6,4) DEFAULT NULL COMMENT '信号：来源权重',
  `factor_count` int(11) NOT NULL DEFAULT '0' COMMENT 'DISTINCT 关联因子数',
  `top_category` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '权重最高的因子类别',
  `signals_json` json DEFAULT NULL COMMENT '全部信号子分与原始取值（解释/台账）',
  `computed_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '本次计算时间',
  PRIMARY KEY (`news_id`,`score_version`),
  KEY `idx_nis_version_score` (`score_version`,`importance_score`),
  KEY `idx_nis_computed` (`computed_at`),
  CONSTRAINT `fk_nis_news` FOREIGN KEY (`news_id`) REFERENCES `news` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='新闻重要性打分（静态分量预计算，时间衰减读时施加）';

CREATE TABLE `news_vectors` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `news_id` bigint(20) unsigned NOT NULL,
  `vector` blob NOT NULL,
  `vector_version` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_news_id_version` (`news_id`,`vector_version`),
  KEY `idx_vector_version` (`vector_version`),
  CONSTRAINT `fk_news_vectors_news_id` FOREIGN KEY (`news_id`) REFERENCES `news` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=70877 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='新闻文本向量存储表';

CREATE TABLE `policy_analysis` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `document_id` bigint(20) NOT NULL,
  `owner_username` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `summary` text COLLATE utf8mb4_unicode_ci COMMENT '政策要点摘要',
  `domains` json DEFAULT NULL COMMENT '涉及领域数组，如 ["货币政策","财政政策"]',
  `impact_direction` enum('bullish','bearish','neutral') COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '对债市影响方向',
  `impact_reason` text COLLATE utf8mb4_unicode_ci COMMENT '影响推理说明',
  `evidence` json DEFAULT NULL COMMENT '原文依据片段数组（方向判断必须附依据）',
  `key_points` json DEFAULT NULL COMMENT '分条要点',
  `model_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_policy_analysis_document` (`document_id`),
  KEY `idx_policy_analysis_owner` (`owner_username`,`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='政策文件 AI 分析结果';

CREATE TABLE `policy_document` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `owner_username` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_hash` char(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '文件 SHA-256，用于去重',
  `title` varchar(300) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '文件标题（解析或取文件名）',
  `original_filename` varchar(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '原始文件名',
  `issuer` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '发文机关',
  `document_no` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '文号，如 银发〔2026〕1号',
  `publish_date` date DEFAULT NULL COMMENT '发布日期',
  `full_text` mediumtext COLLATE utf8mb4_unicode_ci COMMENT '解析出的全文',
  `page_count` int(11) DEFAULT NULL COMMENT '页数',
  `status` enum('uploaded','analyzing','completed','failed') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'uploaded',
  `error_message` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `model_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '分析所用模型',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_policy_document_hash` (`owner_username`,`file_hash`),
  KEY `idx_policy_document_list` (`owner_username`,`created_at`,`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='政策文件（用户上传）';

CREATE TABLE `policy_event` (
  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_username` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `news_id` bigint(20) unsigned NOT NULL COMMENT '关联 news.id',
  `event_date` date NOT NULL COMMENT '事件日期（取新闻发布日期）',
  `title` varchar(300) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `policy_category` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '代表性 POLICY 因子 code',
  `scope` enum('domestic','overseas') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'domestic' COMMENT '国内 / 涉外',
  `status` enum('pending','confirmed','excluded') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT '待确认 / 已确认 / 已剔除',
  `note` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '剔除或确认备注',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_policy_event_owner_news` (`owner_username`,`news_id`),
  KEY `idx_policy_event_list` (`owner_username`,`status`,`event_date`),
  KEY `idx_policy_event_date` (`event_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='政策事件（人工确认态）';

CREATE TABLE `portfolio_strategy_analysis_cache` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID，自增',
  `cache_key` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '缓存唯一键，唯一标识一条缓存记录',
  `target_news_date` date DEFAULT NULL COMMENT '目标新闻日期',
  `model_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '模型名称',
  `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '执行状态：success-成功，fail-失败，running-执行中',
  `output_json` json DEFAULT NULL COMMENT '分析结果JSON数据',
  `news_count` int(11) DEFAULT NULL COMMENT '新闻数量',
  `news_ids_json` json DEFAULT NULL COMMENT '新闻ID列表JSON',
  `window_start` datetime DEFAULT NULL COMMENT '时间窗口开始时间',
  `window_end` datetime DEFAULT NULL COMMENT '时间窗口结束时间',
  `latest_news_pub_time` datetime DEFAULT NULL COMMENT '最新新闻发布时间',
  `request_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '请求唯一ID，链路追踪',
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '错误信息（失败时记录）',
  `started_at` datetime DEFAULT NULL COMMENT '任务开始执行时间',
  `finished_at` datetime DEFAULT NULL COMMENT '任务执行完成时间',
  `latency_ms` bigint(20) DEFAULT NULL COMMENT '执行耗时，单位：毫秒',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_cache_key` (`cache_key`),
  KEY `idx_target_news_date` (`target_news_date`),
  KEY `idx_status_created` (`status`,`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='组合策略分析结果缓存表';

CREATE TABLE `report_analysis` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `report_id` bigint(20) NOT NULL COMMENT '关联 research_report.id',
  `article_id` bigint(20) DEFAULT NULL COMMENT '关联 wechat_article.id',
  `model` varchar(32) NOT NULL COMMENT 'doubao/deepseek/glm/qwen',
  `market_view` enum('bullish','bearish','neutral') NOT NULL,
  `view_strength` decimal(4,3) DEFAULT '0.500' COMMENT '观点强度 0~1',
  `asset_class` enum('fixed_income','fx','commodity') NOT NULL,
  `target_products` varchar(512) DEFAULT NULL COMMENT '品种列表（逗号分隔）',
  `horizon` enum('短期','中期','长期') DEFAULT NULL,
  `key_logic` text COMMENT '核心逻辑链',
  `target_yield_change` varchar(128) DEFAULT NULL COMMENT '目标收益率变动预期',
  `summary` text COMMENT 'AI 摘要',
  `analyzed_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_report_model` (`report_id`,`model`),
  KEY `idx_market_view` (`market_view`),
  KEY `idx_asset_class` (`asset_class`),
  KEY `idx_analyzed_at` (`analyzed_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='研报AI分析结果';

CREATE TABLE `report_factor` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `report_id` bigint(20) NOT NULL COMMENT '关联 research_report.id',
  `factor_id` bigint(20) NOT NULL COMMENT '关联 factor.id',
  `direction` enum('positive','negative','neutral') NOT NULL COMMENT '方向',
  `driver` text COMMENT '作用机制',
  `pub_time` datetime DEFAULT NULL COMMENT '冗余研报发布时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_report_factor` (`report_id`,`factor_id`),
  KEY `idx_factor` (`factor_id`),
  KEY `idx_pub_time` (`pub_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='研报-因子关联';

CREATE TABLE `report_figure` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `report_id` bigint(20) NOT NULL,
  `page_number` int(11) DEFAULT NULL,
  `figure_order` int(11) DEFAULT NULL COMMENT '页内顺序1,2,3...',
  `figure_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'chart/table/image/decorative',
  `caption` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '图说',
  `image_path` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '相对data/的路径',
  `image_size_kb` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_report` (`report_id`),
  CONSTRAINT `report_figure_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `research_report` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=115 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='研报图表';

CREATE TABLE `report_generation_tasks` (
  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_username` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `requirement` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `date_start` date DEFAULT NULL,
  `date_end` date DEFAULT NULL,
  `report_ids_json` json NOT NULL,
  `source_snapshot_json` json NOT NULL,
  `version_no` int(11) NOT NULL DEFAULT '1' COMMENT '版本号，再生成递增',
  `parent_task_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '再生成来源任务',
  `status` varchar(24) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'queued',
  `model_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `result_markdown` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `retry_count` int(11) NOT NULL DEFAULT '0',
  `started_at` datetime(6) DEFAULT NULL,
  `finished_at` datetime(6) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `deleted_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_report_generation_owner_updated` (`owner_username`,`updated_at`),
  KEY `idx_report_generation_owner_status` (`owner_username`,`status`),
  KEY `idx_report_generation_owner_deleted_updated` (`owner_username`,`deleted_at`,`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `research_report` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `title` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `institution` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '券商/机构',
  `analyst` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '分析师',
  `publish_date` date DEFAULT NULL COMMENT '研报发布日期',
  `industry` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '行业',
  `symbols` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '股票代码',
  `report_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'company/industry/macro/strategy/morning/comment',
  `file_path` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '相对data/的路径',
  `file_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'SHA256用于去重',
  `file_size_kb` int(11) DEFAULT NULL,
  `page_count` int(11) DEFAULT NULL,
  `full_text` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT 'PDF全文文字',
  `ai_summary` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '5句话核心摘要',
  `ai_key_points` json DEFAULT NULL COMMENT '要点列表',
  `ai_symbols` json DEFAULT NULL COMMENT '标的列表',
  `ai_industries` json DEFAULT NULL COMMENT '行业列表',
  `ai_market_view` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'bullish/bearish/neutral',
  `ai_view_strength` decimal(3,2) DEFAULT NULL COMMENT '0-1',
  `ai_time_horizon` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'short/medium/long',
  `ai_analyzed_at` datetime DEFAULT NULL COMMENT 'AI分析时间',
  `ai_model` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '模型名',
  `ai_raw_response` json DEFAULT NULL COMMENT 'LLM原始返回',
  `ai_evidence` json DEFAULT NULL COMMENT 'AI分析溯源：原文摘录+推断',
  `ai_deep_markdown` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '深度拆解 Markdown（板块一）',
  `status` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'pending' COMMENT 'pending/parsing/parsed/analyzed/failed',
  `parse_error` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '解析失败原因',
  `retry_count` int(11) DEFAULT '0' COMMENT '分析重试次数',
  `source` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'eastmoney/sina/manual/arxiv',
  `uploaded_by` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '上传者',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `asset_class` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `target_products` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `analyst_name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `wechat_article_id` bigint(20) DEFAULT NULL,
  `report_factor_ids` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `file_hash` (`file_hash`),
  KEY `idx_publish_date` (`publish_date`),
  KEY `idx_institution` (`institution`),
  KEY `idx_status` (`status`),
  KEY `idx_market_view` (`ai_market_view`),
  KEY `idx_asset_class` (`asset_class`)
) ENGINE=InnoDB AUTO_INCREMENT=31 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='券商研报主表';

CREATE TABLE `strategy_change_snapshot` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `version_time` datetime NOT NULL COMMENT '版本整点时间',
  `window_start` datetime NOT NULL COMMENT '新闻窗口起始时间',
  `window_end` datetime NOT NULL COMMENT '新闻窗口结束时间',
  `news_total` int(11) NOT NULL DEFAULT '0' COMMENT '窗口内有效新闻总数',
  `news_added_count` int(11) NOT NULL DEFAULT '0' COMMENT '相比上一版本新增新闻数',
  `news_removed_count` int(11) NOT NULL DEFAULT '0' COMMENT '相比上一版本移出新闻数',
  `stock_recommend` json NOT NULL COMMENT '标的推荐全量列表',
  `strategy_recommend` json NOT NULL COMMENT '策略推荐全量列表',
  `summary_stats` json DEFAULT NULL COMMENT '窗口舆情总览统计',
  `generate_status` tinyint(4) NOT NULL DEFAULT '1' COMMENT '0=失败 1=成功 2=待确认',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_version_time` (`version_time`),
  KEY `idx_version_time` (`version_time`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='策略变动快照表-每小时版本';

CREATE TABLE `strategy_push_history` (
  `slot_time` datetime NOT NULL,
  `window_start` datetime NOT NULL,
  `window_end` datetime NOT NULL,
  `status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `strategy_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `news_count` int(11) NOT NULL DEFAULT '0',
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`slot_time`),
  KEY `idx_window_start` (`window_start`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `task_events` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `task_run_id` bigint(20) NOT NULL,
  `event_type` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `news_id` bigint(20) DEFAULT NULL,
  `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `message` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `payload_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_task_events_task_run_id` (`task_run_id`)
) ENGINE=InnoDB AUTO_INCREMENT=14147 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `task_runs` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `task_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `task_type` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `idempotency_key` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'running',
  `total_count` int(11) NOT NULL DEFAULT '0',
  `processed_count` int(11) NOT NULL DEFAULT '0',
  `payload_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `result_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `error_message` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `started_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `finished_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_runs_idempotency_key` (`idempotency_key`)
) ENGINE=InnoDB AUTO_INCREMENT=2219 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `treasury_yield` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `trade_date` date NOT NULL COMMENT '日期（美方交易日）',
  `term` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '期限码：2Y/10Y/30Y',
  `value` decimal(10,4) NOT NULL COMMENT '收益率(%)',
  `source` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'us_treasury',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_treasury_yield` (`trade_date`,`term`),
  KEY `idx_treasury_yield_date` (`trade_date`)
) ENGINE=InnoDB AUTO_INCREMENT=616 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='美债收益率（美国财政部）';

CREATE TABLE `user_behavior_profile` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `username` varchar(64) NOT NULL,
  `total_sessions` int(11) DEFAULT '0' COMMENT '累计会话数',
  `total_page_views` int(11) DEFAULT '0' COMMENT '累计页面访问',
  `total_active_sec` int(11) DEFAULT '0' COMMENT '累计活跃时长（秒）',
  `first_visit` date DEFAULT NULL COMMENT '首次访问日期',
  `last_visit` datetime DEFAULT NULL COMMENT '最近访问时间',
  `active_days_30d` int(11) DEFAULT '0' COMMENT '近30天活跃天数',
  `avg_session_sec` int(11) DEFAULT NULL COMMENT '平均会话时长',
  `avg_daily_pages_30d` decimal(8,2) DEFAULT NULL COMMENT '近30天日均访问页数',
  `page_affinity_json` json DEFAULT NULL COMMENT '页面偏好权重',
  `peak_hour` int(11) DEFAULT NULL COMMENT '最常活跃小时（0-23）',
  `hour_distribution_json` json DEFAULT NULL COMMENT '每小时访问次数分布',
  `distinct_pages_30d` int(11) DEFAULT '0' COMMENT '近30天访问的不同页面数',
  `advanced_feature_used` tinyint(1) DEFAULT '0' COMMENT '是否使用过高级功能',
  `is_power_user` tinyint(1) DEFAULT '0' COMMENT '重度用户',
  `is_report_focused` tinyint(1) DEFAULT '0' COMMENT '报告导向',
  `is_strategy_focused` tinyint(1) DEFAULT '0' COMMENT '策略导向',
  `churn_risk_score` decimal(3,2) DEFAULT NULL COMMENT '流失风险 0-1',
  `computed_at` datetime DEFAULT NULL COMMENT '画像计算时间',
  `profile_version` varchar(16) DEFAULT 'v1.0',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_last_visit` (`last_visit`),
  KEY `idx_power_user` (`is_power_user`)
) ENGINE=InnoDB AUTO_INCREMENT=44 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户行为画像 - 每日定时聚合，供看板和管理者查阅';

CREATE TABLE `user_page_view` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `session_id` bigint(20) NOT NULL COMMENT '关联 user_session.id',
  `user_id` int(11) NOT NULL,
  `username` varchar(64) NOT NULL,
  `page_route` varchar(256) NOT NULL COMMENT '前端路由，如 /prediction /strategies',
  `page_title` varchar(128) DEFAULT NULL COMMENT '页面标题',
  `enter_time` datetime(3) NOT NULL COMMENT '进入页面时间',
  `leave_time` datetime(3) DEFAULT NULL COMMENT '离开页面时间',
  `duration_sec` int(11) DEFAULT NULL COMMENT '页面停留秒数',
  `exit_type` varchar(32) DEFAULT NULL COMMENT '离开方式: navigation / close / idle_timeout',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `action_type` varchar(64) DEFAULT 'page_enter' COMMENT '行为类型: page_enter/page_leave/news_click/report_view等',
  `action_target` varchar(256) DEFAULT NULL COMMENT '操作目标: 新闻ID、报告日期、策略代码等',
  `action_detail` json DEFAULT NULL COMMENT '操作详情(结构化JSON)',
  `client_ts` datetime(3) DEFAULT NULL COMMENT '客户端时间戳',
  PRIMARY KEY (`id`),
  KEY `idx_session` (`session_id`),
  KEY `idx_user_route` (`user_id`,`page_route`),
  KEY `idx_enter_time` (`enter_time`),
  KEY `idx_user_enter` (`user_id`,`enter_time`),
  KEY `idx_action_type` (`action_type`),
  KEY `idx_action_target` (`action_target`(64)),
  KEY `idx_user_action` (`user_id`,`action_type`)
) ENGINE=InnoDB AUTO_INCREMENT=2538 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='页面访问日志 - 每次页面切换记录一条';

CREATE TABLE `user_session` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL COMMENT '关联 users.id',
  `username` varchar(64) NOT NULL,
  `login_time` datetime NOT NULL COMMENT '会话开始时间',
  `logout_time` datetime DEFAULT NULL COMMENT '会话结束时间',
  `duration_sec` int(11) DEFAULT NULL COMMENT '会话持续秒数',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_login_time` (`login_time`),
  KEY `idx_user_login` (`user_id`,`login_time`)
) ENGINE=InnoDB AUTO_INCREMENT=1476 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户会话记录 - 每次登录建立一条';

CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户名（登录用）',
  `password` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '密码（明文）',
  `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '手机号',
  `display_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '显示名称',
  `is_active` tinyint(1) DEFAULT '1' COMMENT '是否启用（1=启用，0=禁用）',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `is_admin` tinyint(1) DEFAULT '0' COMMENT '是否管理员',
  `role` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'user' COMMENT '角色: admin/manager/user',
  `department` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '部门（便于分组管理）',
  `company` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '公司',
  `employee_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '工号',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  UNIQUE KEY `uk_phone` (`phone`)
) ENGINE=InnoDB AUTO_INCREMENT=32 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';

CREATE TABLE `wechat_article` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `article_hash` varchar(64) NOT NULL COMMENT 'sha256(url+title+pub_time) 去重',
  `account_name` varchar(128) NOT NULL COMMENT '公众号名称',
  `account_id` varchar(128) DEFAULT NULL COMMENT '公众号 biz id',
  `title` varchar(512) NOT NULL,
  `author` varchar(128) DEFAULT NULL COMMENT '分析师姓名',
  `pub_time` datetime NOT NULL COMMENT '发布时间',
  `content` mediumtext COMMENT '纯文本正文',
  `content_html` mediumtext COMMENT '原始 HTML',
  `summary` varchar(1024) DEFAULT NULL COMMENT '摘要',
  `url` varchar(1024) DEFAULT NULL COMMENT '原文链接',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `article_hash` (`article_hash`),
  KEY `idx_account` (`account_name`),
  KEY `idx_pub_time` (`pub_time`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='公众号文章';

CREATE TABLE `workbench_conversations` (
  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_username` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `title` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `module_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'chat',
  `source` enum('home','sidebar','project') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('active','archived') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `last_message_at` datetime(6) DEFAULT NULL,
  `deleted_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_workbench_conversations_owner_recent` (`owner_username`,`project_id`,`status`,`last_message_at`,`id`),
  KEY `idx_workbench_conversations_project_recent` (`project_id`,`status`,`last_message_at`,`id`),
  CONSTRAINT `fk_workbench_conversation_project` FOREIGN KEY (`project_id`) REFERENCES `workbench_projects` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_feishu_connections` (
  `username` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `feishu_user_id` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tenant_key` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `scopes` json DEFAULT NULL,
  `access_token` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `refresh_token` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `expires_at` datetime NOT NULL,
  `connected_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_used_at` datetime DEFAULT NULL,
  PRIMARY KEY (`username`),
  KEY `idx_workbench_feishu_connections_expiry` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_feishu_mcp_audit_logs` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `username` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `tool_name` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `success` tinyint(1) NOT NULL,
  `detail` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_workbench_feishu_audit_user_created` (`username`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_feishu_oauth_states` (
  `state_hash` char(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `username` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `expires_at` datetime NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`state_hash`),
  KEY `idx_workbench_feishu_oauth_expiry` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_message_skills` (
  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `message_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `skill_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `skill_name` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_workbench_message_skills_message` (`message_id`,`created_at`),
  KEY `fk_workbench_message_skills_skill` (`skill_id`),
  CONSTRAINT `fk_workbench_message_skills_message` FOREIGN KEY (`message_id`) REFERENCES `workbench_messages` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_workbench_message_skills_skill` FOREIGN KEY (`skill_id`) REFERENCES `workbench_skills` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_messages` (
  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `conversation_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `parent_message_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `role` enum('user','assistant') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('streaming','completed','failed','interrupted') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `client_message_id` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `error_code` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `completed_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_workbench_user_message_client_id` (`conversation_id`,`client_message_id`),
  KEY `idx_workbench_messages_conversation` (`conversation_id`,`created_at`,`id`),
  KEY `fk_workbench_message_parent` (`parent_message_id`),
  CONSTRAINT `fk_workbench_message_conversation` FOREIGN KEY (`conversation_id`) REFERENCES `workbench_conversations` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_workbench_message_parent` FOREIGN KEY (`parent_message_id`) REFERENCES `workbench_messages` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_project_members` (
  `project_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `username` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `role` enum('manager','editor') COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`project_id`,`username`),
  KEY `idx_workbench_members_username` (`username`,`project_id`),
  CONSTRAINT `fk_workbench_member_project` FOREIGN KEY (`project_id`) REFERENCES `workbench_projects` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_project_memories` (
  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` enum('background','goal','constraint','preference','conclusion','other') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'other',
  `title` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_by` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_by` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_workbench_project_memories_list` (`project_id`,`is_active`,`updated_at`,`id`),
  CONSTRAINT `fk_workbench_memory_project` FOREIGN KEY (`project_id`) REFERENCES `workbench_projects` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_projects` (
  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_username` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(1000) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `visibility` enum('private','shared') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'private',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `deleted_at` datetime(6) DEFAULT NULL,
  `client_request_id` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_workbench_project_create_request` (`owner_username`,`client_request_id`),
  KEY `idx_workbench_projects_updated` (`updated_at`,`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_skill_attachment_chunks` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `attachment_id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `skill_id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_location` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `chunk_index` int(10) unsigned NOT NULL,
  `content` mediumtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_workbench_skill_attachment_chunk` (`attachment_id`,`chunk_index`),
  KEY `idx_workbench_skill_attachment_chunks_skill` (`skill_id`,`attachment_id`),
  CONSTRAINT `fk_workbench_skill_attachment_chunks_attachment` FOREIGN KEY (`attachment_id`) REFERENCES `workbench_skill_attachments` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_workbench_skill_attachment_chunks_skill` FOREIGN KEY (`skill_id`) REFERENCES `workbench_skills` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_skill_attachments` (
  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `skill_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `original_filename` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `stored_filename` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `size_bytes` bigint(20) unsigned NOT NULL,
  `parse_status` enum('stored','pending','parsing','ready','failed') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'stored',
  `parse_error` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `page_count` int(10) unsigned DEFAULT NULL,
  `parsed_at` datetime(6) DEFAULT NULL,
  `created_by` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_workbench_skill_attachments_skill` (`skill_id`,`created_at`),
  CONSTRAINT `fk_workbench_skill_attachments_skill` FOREIGN KEY (`skill_id`) REFERENCES `workbench_skills` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_skill_versions` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `skill_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `version_no` int(10) unsigned NOT NULL,
  `name` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `instructions` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `input_schema_json` json NOT NULL,
  `output_format` enum('markdown','text') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('draft','published','archived') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_by` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_workbench_skill_versions` (`skill_id`,`version_no`),
  CONSTRAINT `fk_workbench_skill_versions_skill` FOREIGN KEY (`skill_id`) REFERENCES `workbench_skills` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=317 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_skills` (
  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_username` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `owner_type` enum('system','user') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'user',
  `name` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `instructions` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `input_schema_json` json NOT NULL,
  `output_format` enum('markdown','text') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'markdown',
  `status` enum('draft','published','archived') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'draft',
  `version_no` int(10) unsigned NOT NULL DEFAULT '1',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `archived_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_workbench_skills_owner_updated` (`owner_username`,`status`,`updated_at`,`id`),
  KEY `idx_workbench_skills_system_updated` (`owner_type`,`status`,`updated_at`,`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_user_memories` (
  `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_username` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` enum('response_preference','user_background','long_term_interest','personal_constraint') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'response_preference',
  `normalized_key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_type` enum('manual','explicit_chat','inferred_chat') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'manual',
  `source_conversation_id` char(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `source_message_id` char(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` enum('pending','active','disabled','deleted') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
  `confidence` decimal(4,3) DEFAULT NULL,
  `is_pinned` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `last_used_at` datetime(6) DEFAULT NULL,
  `deleted_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_workbench_user_memory_source` (`owner_username`,`source_message_id`,`normalized_key`),
  KEY `idx_workbench_user_memories_list` (`owner_username`,`status`,`is_pinned`,`updated_at`,`id`),
  KEY `idx_workbench_user_memories_key` (`owner_username`,`normalized_key`,`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_user_memory_settings` (
  `owner_username` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `memory_enabled` tinyint(1) NOT NULL DEFAULT '1',
  `auto_extract_enabled` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`owner_username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_user_system_skills` (
  `username` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `skill_id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `enabled_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`username`,`skill_id`),
  KEY `idx_workbench_user_system_skills_skill` (`skill_id`,`username`),
  CONSTRAINT `fk_workbench_user_system_skills_skill` FOREIGN KEY (`skill_id`) REFERENCES `workbench_skills` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_users` (
  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `workspace_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `username` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `display_name` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `role` enum('admin','member') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'member',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `demo_password` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_workbench_users_username` (`username`),
  KEY `idx_workbench_users_workspace` (`workspace_id`,`role`),
  CONSTRAINT `fk_workbench_users_workspace` FOREIGN KEY (`workspace_id`) REFERENCES `workbench_workspaces` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_watchlist_items` (
  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_username` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `object_type` enum('news','factor','macro_signal') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `object_id` varchar(191) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(240) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_url` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `metadata_json` json NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `deleted_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_workbench_watchlist_owner_object` (`owner_username`,`object_type`,`object_id`),
  KEY `idx_workbench_watchlist_owner_updated` (`owner_username`,`deleted_at`,`updated_at`,`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workbench_workspaces` (
  `id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(120) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `yield_data` (
  `date` date NOT NULL,
  `period` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `value` decimal(10,4) NOT NULL,
  PRIMARY KEY (`date`,`period`),
  KEY `idx_yield_date` (`date`),
  KEY `idx_yield_period` (`period`),
  KEY `idx_yield_date_period` (`date`,`period`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='国债收益率数据表';

SET FOREIGN_KEY_CHECKS=1;
