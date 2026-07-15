-- ============================================================
-- 用户行为增强迁移脚本 (MySQL 8.0 兼容版)
-- 1. user_page_view 合并 user_action_log 功能（增加操作字段）
-- 2. 创建 user_behavior_profile 用户画像表
-- ============================================================

-- Step 1: user_page_view 增加操作行为字段（兼容8.0，用INFORMATION_SCHEMA检查）
SET @exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_page_view' AND COLUMN_NAME = 'action_type');
SET @sql = IF(@exist=0, 'ALTER TABLE user_page_view ADD COLUMN action_type VARCHAR(64) DEFAULT ''page_enter'' COMMENT ''行为类型: page_enter/page_leave/news_click/report_view等'';', 'SELECT ''action_type已存在'';');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_page_view' AND COLUMN_NAME = 'action_target');
SET @sql = IF(@exist=0, 'ALTER TABLE user_page_view ADD COLUMN action_target VARCHAR(256) DEFAULT NULL COMMENT ''操作目标: 新闻ID、报告日期、策略代码等'';', 'SELECT ''action_target已存在'';');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_page_view' AND COLUMN_NAME = 'action_detail');
SET @sql = IF(@exist=0, 'ALTER TABLE user_page_view ADD COLUMN action_detail JSON DEFAULT NULL COMMENT ''操作详情(结构化JSON)'';', 'SELECT ''action_detail已存在'';');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exist = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_page_view' AND COLUMN_NAME = 'client_ts');
SET @sql = IF(@exist=0, 'ALTER TABLE user_page_view ADD COLUMN client_ts DATETIME(3) DEFAULT NULL COMMENT ''客户端时间戳'';', 'SELECT ''client_ts已存在'';');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 为已有数据回填 action_type
UPDATE user_page_view SET action_type = 'page_enter' WHERE action_type IS NULL;
UPDATE user_page_view SET action_type = 'page_leave' WHERE action_type IS NULL AND leave_time IS NOT NULL;

-- ========== 创建索引（兼容8.0，检查是否已存在）==========

SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_page_view' AND INDEX_NAME = 'idx_action_type');
SET @sql_idx = IF(@idx_exists = 0,
    'ALTER TABLE user_page_view ADD INDEX idx_action_type (action_type);',
    'SELECT ''索引 idx_action_type 已存在，跳过'';');
PREPARE stmt FROM @sql_idx; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_page_view' AND INDEX_NAME = 'idx_action_target');
SET @sql_idx = IF(@idx_exists = 0,
    'ALTER TABLE user_page_view ADD INDEX idx_action_target (action_target(64));',
    'SELECT ''索引 idx_action_target 已存在，跳过'';');
PREPARE stmt FROM @sql_idx; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_page_view' AND INDEX_NAME = 'idx_user_action');
SET @sql_idx = IF(@idx_exists = 0,
    'ALTER TABLE user_page_view ADD INDEX idx_user_action (user_id, action_type);',
    'SELECT ''索引 idx_user_action 已存在，跳过'';');
PREPARE stmt FROM @sql_idx; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Step 2: 创建 user_behavior_profile 用户画像表（如不存在）
CREATE TABLE IF NOT EXISTS user_behavior_profile (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    user_id               INT NOT NULL UNIQUE,
    username              VARCHAR(64) NOT NULL,
    -- 活跃概览
    total_sessions        INT DEFAULT 0 COMMENT '累计会话数',
    total_page_views      INT DEFAULT 0 COMMENT '累计页面访问',
    total_active_sec      INT DEFAULT 0 COMMENT '累计活跃时长（秒）',
    first_visit           DATE DEFAULT NULL COMMENT '首次访问日期',
    last_visit            DATETIME DEFAULT NULL COMMENT '最近访问时间',
    active_days_30d       INT DEFAULT 0 COMMENT '近30天活跃天数',
    avg_session_sec       INT DEFAULT NULL COMMENT '平均会话时长',
    avg_daily_pages_30d   DECIMAL(8,2) DEFAULT NULL COMMENT '近30天日均访问页数',
    -- 页面偏好
    page_affinity_json    JSON DEFAULT NULL COMMENT '页面偏好权重',
    -- 时间段偏好
    peak_hour             INT DEFAULT NULL COMMENT '最常活跃小时（0-23）',
    hour_distribution_json JSON DEFAULT NULL COMMENT '每小时访问次数分布',
    -- 功能覆盖
    distinct_pages_30d    INT DEFAULT 0 COMMENT '近30天访问的不同页面数',
    advanced_feature_used BOOLEAN DEFAULT FALSE COMMENT '是否使用过高级功能',
    -- 行为特征
    is_power_user         BOOLEAN DEFAULT FALSE COMMENT '重度用户',
    is_report_focused     BOOLEAN DEFAULT FALSE COMMENT '报告导向',
    is_strategy_focused   BOOLEAN DEFAULT FALSE COMMENT '策略导向',
    churn_risk_score      DECIMAL(3,2) DEFAULT NULL COMMENT '流失风险 0-1',
    -- 元数据
    computed_at           DATETIME DEFAULT NULL COMMENT '画像计算时间',
    profile_version       VARCHAR(16) DEFAULT 'v1.0',
    updated_at            DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_last_visit (last_visit),
    INDEX idx_power_user (is_power_user)
) COMMENT '用户行为画像 - 每日定时聚合，供看板和管理者查阅';
