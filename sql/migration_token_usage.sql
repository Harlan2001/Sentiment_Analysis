-- ============================================================
-- Token 使用统计 & 权限体系 — 数据库迁移
-- 执行方式：在 Sentiment_analysis 库中执行此 SQL
-- ============================================================

-- 1. LLM 调用日志表（记录每次大模型调用的 Token 消耗）
CREATE TABLE IF NOT EXISTS `llm_usage_log` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL DEFAULT 0 COMMENT '用户ID，系统调用为0',
  `username` varchar(100) NOT NULL DEFAULT 'system' COMMENT '用户名',
  `call_source` varchar(50) NOT NULL COMMENT '调用来源: chat/analysis/strategy/change',
  `model_name` varchar(128) NOT NULL COMMENT '模型名称，如 glm/deepseek/qwen',
  `provider_model` varchar(255) DEFAULT NULL COMMENT 'provider完整模型名',
  `prompt_tokens` int(11) NOT NULL DEFAULT 0 COMMENT '输入Token数',
  `completion_tokens` int(11) NOT NULL DEFAULT 0 COMMENT '输出Token数',
  `total_tokens` int(11) NOT NULL DEFAULT 0 COMMENT '总Token数',
  `request_id` varchar(128) DEFAULT NULL COMMENT '请求唯一ID，链路追踪',
  `success` tinyint(1) NOT NULL DEFAULT 1 COMMENT '是否成功',
  `error_message` text COMMENT '失败原因',
  `latency_ms` int(10) unsigned DEFAULT NULL COMMENT '请求耗时(ms)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_username` (`username`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_call_source` (`call_source`),
  KEY `idx_model_name` (`model_name`),
  KEY `idx_user_date` (`user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='LLM调用Token消耗日志';

-- 2. 扩展 users 表：添加角色、部门、工号字段
DELIMITER //
CREATE PROCEDURE add_user_cols()
BEGIN
    DECLARE cnt INT;

    -- role
    SELECT COUNT(*) INTO cnt FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'role';
    IF cnt = 0 THEN
        ALTER TABLE `users` ADD COLUMN `role` varchar(20) DEFAULT 'user' COMMENT '角色: admin/manager/user';
    END IF;

    -- department
    SELECT COUNT(*) INTO cnt FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'department';
    IF cnt = 0 THEN
        ALTER TABLE `users` ADD COLUMN `department` varchar(100) DEFAULT NULL COMMENT '部门（便于分组管理）';
    END IF;

    -- employee_no
    SELECT COUNT(*) INTO cnt FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'employee_no';
    IF cnt = 0 THEN
        ALTER TABLE `users` ADD COLUMN `employee_no` varchar(50) DEFAULT NULL COMMENT '工号';
    END IF;
END //
DELIMITER ;

CALL add_user_cols();
DROP PROCEDURE IF EXISTS add_user_cols;
-- 3. 将现有 is_admin=1 的用户角色更新为 admin
UPDATE users SET role = 'admin' WHERE is_admin = 1 AND (role IS NULL OR role = 'user');

-- 4. 创建系统用户（用于系统级 LLM 调用的 token 归属）
INSERT IGNORE INTO users (id, username, password, display_name, is_active, is_admin, role)
VALUES (0, 'system', '', '系统', 1, 0, 'user');

-- 5. 创建测试角色用户（不指定 id，自动递增）
INSERT IGNORE INTO users (username, password, display_name, is_active, is_admin, role, department)
VALUES ('manager', '123456', '经理', 1, 0, 'manager', '销售部');

INSERT IGNORE INTO users (username, password, display_name, is_active, is_admin, role, department)
VALUES ('user1', '123456', '员工张三', 1, 0, 'user', '销售部');

INSERT IGNORE INTO users (username, password, display_name, is_active, is_admin, role, department)
VALUES ('user2', '123456', '员工李四', 1, 0, 'user', '技术部');

INSERT IGNORE INTO users (username, password, display_name, is_active, is_admin, role, department)
VALUES ('admin', '123456', '管理员', 1, 1, 'admin', '');

-- 6. 看板指标缓存表（支持多种缓存类型：core / token / behavior 等）
CREATE TABLE IF NOT EXISTS `dashboard_metric_cache` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `calc_time` datetime NOT NULL COMMENT '计算时间',
  `cache_type` varchar(50) NOT NULL DEFAULT 'core' COMMENT '缓存类型: core/token_{dept}_{company}/behavior_{days}',
  `metrics_json` longtext COMMENT '指标JSON快照',
  `service_status` longtext COMMENT '服务状态JSON',
  PRIMARY KEY (`id`),
  KEY `idx_cache_hit` (`cache_type`, `calc_time` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='看板指标缓存';

-- 7. 兼容旧表结构：若有旧表（无cache_type列），自动添加
DELIMITER //
CREATE PROCEDURE migrate_cache_table()
BEGIN
    DECLARE cnt INT;
    DECLARE has_old_col INT DEFAULT 0;
    SELECT COUNT(*) INTO cnt FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'dashboard_metric_cache' AND COLUMN_NAME = 'cache_type';
    IF cnt = 0 THEN
        ALTER TABLE `dashboard_metric_cache` ADD COLUMN `cache_type` varchar(50) NOT NULL DEFAULT 'core' AFTER `calc_time`;
        ALTER TABLE `dashboard_metric_cache` ADD KEY `idx_cache_hit` (`cache_type`, `calc_time` DESC);
    END IF;
    SELECT COUNT(*) INTO has_old_col FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'dashboard_metric_cache' AND COLUMN_NAME = 'core_metrics';
    IF has_old_col > 0 THEN
        ALTER TABLE `dashboard_metric_cache` CHANGE COLUMN `core_metrics` `metrics_json` longtext;
    END IF;
END //
DELIMITER ;
CALL migrate_cache_table();
DROP PROCEDURE IF EXISTS migrate_cache_table;
