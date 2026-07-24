-- 宏观经济指标数据表
-- 使用数据库: Sentiment_analysis
-- 长格式存储，(zbcode, datestr) 联合唯一

CREATE TABLE IF NOT EXISTS macro_indicator_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    zbcode VARCHAR(20) NOT NULL COMMENT '指标代码，如 A010101',
    name VARCHAR(200) NOT NULL COMMENT '指标中文名称',
    datestr VARCHAR(10) NOT NULL COMMENT '日期，格式 YYYYMM，如 202201',
    value DOUBLE DEFAULT NULL COMMENT '指标数值',
    category VARCHAR(20) DEFAULT NULL COMMENT '分类: strong/medium/weak/precious/bond/general',
    description VARCHAR(200) DEFAULT NULL COMMENT '指标描述',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_zbcode_date (zbcode, datestr),
    INDEX idx_zbcode (zbcode),
    INDEX idx_datestr (datestr),
    INDEX idx_name (name),
    INDEX idx_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='宏观经济指标数据表';

-- 如果表已存在但没有 category/description 列，执行以下 ALTER：
-- ALTER TABLE macro_indicator_data ADD COLUMN IF NOT EXISTS category VARCHAR(20) DEFAULT NULL COMMENT '分类' AFTER value;
-- ALTER TABLE macro_indicator_data ADD COLUMN IF NOT EXISTS description VARCHAR(200) DEFAULT NULL COMMENT '指标描述' AFTER category;
-- ALTER TABLE macro_indicator_data ADD INDEX IF NOT EXISTS idx_category (category);

-- 注意：MySQL 5.7 不支持 ADD COLUMN IF NOT EXISTS，需先检查列是否存在：
-- SET @dbname = 'Sentiment_analysis';
-- SET @exists = (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME='macro_indicator_data' AND COLUMN_NAME='category');
-- SET @sql = IF(@exists=0, 'ALTER TABLE macro_indicator_data ADD COLUMN category VARCHAR(20) DEFAULT NULL COMMENT ''分类'' AFTER value', 'SELECT ''column exists''');
-- PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 示例：为已导入数据手动标注分类
-- UPDATE macro_indicator_data SET category = 'strong' WHERE zbcode IN ('A010101', 'A010301');
-- UPDATE macro_indicator_data SET category = 'medium' WHERE zbcode IN ('A010401', 'A010601');
