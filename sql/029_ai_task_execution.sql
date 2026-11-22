-- 029：统一 AI 任务的持久化执行元数据
--
-- 不建立第二套任务状态表。四类领域任务仍拥有各自业务状态与结果，
-- 本迁移只补充排队时间、执行租约、真实阶段和执行日志关联。
-- queued/pending 在重启后继续；running/processing/analyzing 只在无租约或
-- 租约过期时由启动恢复标记“服务中断”，绝不自动重跑。

ALTER TABLE `research_report`
  ADD COLUMN `queued_at` datetime(6) DEFAULT NULL COMMENT '最近一次进入分析队列的时间' AFTER `status`,
  ADD COLUMN `lease_token` char(36) DEFAULT NULL,
  ADD COLUMN `lease_expires_at` datetime(6) DEFAULT NULL,
  ADD COLUMN `stage` varchar(48) DEFAULT NULL,
  ADD COLUMN `active_run_id` bigint(20) DEFAULT NULL,
  ADD COLUMN `requested_model` varchar(128) DEFAULT NULL,
  ADD KEY `idx_research_task_queue` (`status`, `queued_at`, `id`),
  ADD KEY `idx_research_task_lease` (`lease_token`);

ALTER TABLE `policy_document`
  MODIFY COLUMN `status` enum('uploaded','queued','analyzing','completed','failed') NOT NULL DEFAULT 'uploaded',
  ADD COLUMN `queued_at` datetime(6) DEFAULT NULL,
  ADD COLUMN `lease_token` char(36) DEFAULT NULL,
  ADD COLUMN `lease_expires_at` datetime(6) DEFAULT NULL,
  ADD COLUMN `stage` varchar(48) DEFAULT NULL,
  ADD COLUMN `active_run_id` bigint(20) DEFAULT NULL,
  ADD COLUMN `retry_count` int(11) NOT NULL DEFAULT 0,
  ADD COLUMN `focus_title` varchar(255) DEFAULT NULL COMMENT '用户指定的分析主题',
  ADD COLUMN `analysis_requirement` text COMMENT '用户指定的分析要求',
  ADD KEY `idx_policy_task_queue` (`status`, `queued_at`, `id`),
  ADD KEY `idx_policy_task_lease` (`lease_token`),
  ADD KEY `idx_policy_task_owner_status` (`owner_username`, `status`, `updated_at`, `id`);

ALTER TABLE `report_generation_tasks`
  ADD COLUMN `queued_at` datetime(6) DEFAULT NULL,
  ADD COLUMN `lease_token` char(36) DEFAULT NULL,
  ADD COLUMN `lease_expires_at` datetime(6) DEFAULT NULL,
  ADD COLUMN `stage` varchar(48) DEFAULT NULL,
  ADD COLUMN `active_run_id` bigint(20) DEFAULT NULL,
  ADD COLUMN `requested_model` varchar(128) DEFAULT NULL,
  ADD KEY `idx_report_task_queue` (`status`, `queued_at`, `created_at`),
  ADD KEY `idx_report_task_lease` (`lease_token`);

ALTER TABLE `daily_news_summary_tasks`
  ADD COLUMN `queued_at` datetime(6) DEFAULT NULL,
  ADD COLUMN `lease_token` char(36) DEFAULT NULL,
  ADD COLUMN `lease_expires_at` datetime(6) DEFAULT NULL,
  ADD COLUMN `stage` varchar(48) DEFAULT NULL,
  ADD COLUMN `active_run_id` bigint(20) DEFAULT NULL,
  ADD COLUMN `retry_count` int(11) NOT NULL DEFAULT 0,
  ADD KEY `idx_daily_news_task_queue` (`status`, `queued_at`, `id`),
  ADD KEY `idx_daily_news_task_lease` (`lease_token`);

UPDATE `research_report` SET `queued_at` = `created_at` WHERE `status` = 'queued' AND `queued_at` IS NULL;
UPDATE `report_generation_tasks` SET `queued_at` = `created_at` WHERE `status` = 'queued' AND `queued_at` IS NULL;
UPDATE `daily_news_summary_tasks` SET `queued_at` = `created_at` WHERE `status` = 'pending' AND `queued_at` IS NULL;
