-- ============================================================
-- 公司/部门体系扩展 & 测试用户 — 数据库迁移
-- 执行方式：在 Sentiment_analysis 库中执行此 SQL
-- 依赖：已执行 migration_token_usage.sql
-- ============================================================

-- 1. 扩展 users 表：添加 company 字段
DELIMITER //
CREATE PROCEDURE add_company_col()
BEGIN
    DECLARE cnt INT;
    SELECT COUNT(*) INTO cnt FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'company';
    IF cnt = 0 THEN
        ALTER TABLE `users` ADD COLUMN `company` varchar(100) DEFAULT NULL COMMENT '公司' AFTER `department`;
    END IF;
END //
DELIMITER ;

CALL add_company_col();
DROP PROCEDURE IF EXISTS add_company_col;

-- 2. 为现有用户设置公司（华泰证券）
UPDATE users SET company = '华泰证券' WHERE username = 'user';
UPDATE users SET company = '华泰证券' WHERE username = 'manager';
UPDATE users SET company = '华泰证券' WHERE username = 'user1';
UPDATE users SET company = '华泰证券' WHERE username = 'user2';

-- 3. 中信建投 — 研究部
INSERT IGNORE INTO users (username, password, display_name, is_active, is_admin, role, department, company, employee_no)
VALUES ('manager_citic', '123456', '中信经理王', 1, 0, 'manager', '研究部', '中信建投', 'CITIC001');

INSERT IGNORE INTO users (username, password, display_name, is_active, is_admin, role, department, company, employee_no)
VALUES ('user_citic1', '123456', '研究员赵', 1, 0, 'user', '研究部', '中信建投', 'CITIC002');

-- 4. 中信建投 — 投资部
INSERT IGNORE INTO users (username, password, display_name, is_active, is_admin, role, department, company, employee_no)
VALUES ('user_citic2', '123456', '投资经理钱', 1, 0, 'user', '投资部', '中信建投', 'CITIC003');

INSERT IGNORE INTO users (username, password, display_name, is_active, is_admin, role, department, company, employee_no)
VALUES ('manager_citic2', '123456', '投资总监孙', 1, 0, 'manager', '投资部', '中信建投', 'CITIC004');

-- 5. 额外：华泰证券 — 增加一个经理到技术部（方便测试同一公司多部门多经理场景）
INSERT IGNORE INTO users (username, password, display_name, is_active, is_admin, role, department, company, employee_no)
VALUES ('manager_ht2', '123456', '技术经理陈', 1, 0, 'manager', '技术部', '华泰证券', 'HT001');
