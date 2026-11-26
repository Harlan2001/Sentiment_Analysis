-- 手工执行的结构迁移：为工作台助手消息持久化思维链内容。
ALTER TABLE `workbench_messages`
  ADD COLUMN `thinking` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL AFTER `content`;
