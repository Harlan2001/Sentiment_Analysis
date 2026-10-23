-- 研报分析改造（docs/PRD-研报分析功能细化.md）配套结构变更
-- 1) 综合研报任务：版本链（改需求再生成）
-- 2) 研报：板块一深度拆解 Markdown
-- 注意：MySQL 8 不支持 ADD COLUMN IF NOT EXISTS，仅可对缺少这些列的库执行一次。

ALTER TABLE `report_generation_tasks`
  ADD COLUMN `version_no` int(11) NOT NULL DEFAULT '1' COMMENT '版本号，再生成递增' AFTER `source_snapshot_json`,
  ADD COLUMN `parent_task_id` char(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '再生成来源任务' AFTER `version_no`;

ALTER TABLE `research_report`
  ADD COLUMN `ai_deep_markdown` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '深度拆解 Markdown（板块一）' AFTER `ai_evidence`;
