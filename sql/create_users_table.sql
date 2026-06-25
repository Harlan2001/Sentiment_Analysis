-- =============================================================================
-- 用户表创建脚本（明文密码版，适用内部试用场景）
-- =============================================================================

CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    `username` VARCHAR(100) NOT NULL COMMENT '用户名（登录用）',
    `password` VARCHAR(255) NOT NULL COMMENT '密码（明文）',
    `display_name` VARCHAR(200) DEFAULT NULL COMMENT '显示名称',
    `is_active` TINYINT(1) DEFAULT 1 COMMENT '是否启用（1=启用，0=禁用）',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';

-- =============================================================================
-- 手动添加用户（直接写明文密码）
-- =============================================================================

-- 示例：添加试用用户
INSERT INTO `users` (`username`, `password`, `display_name`) VALUES ('test', '123456', '试用用户');
INSERT INTO `users` (`username`, `password`, `display_name`) VALUES ('admin', '123456', '管理员');
