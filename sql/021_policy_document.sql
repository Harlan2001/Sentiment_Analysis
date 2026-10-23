-- 017：政策文件分析（工作流内，用户上传）
--
-- 定位：用户上传政策文件 PDF → 解析 → LLM 提取要点与对债市影响方向。
-- 与研报分析（research_report）同类，但输出结构不同（政策字段 vs 券商观点）。
--
-- 多租户沿用项目惯例：owner_username 字段。
-- 上传文件按哈希去重（同一文件重复上传不重复分析）。

CREATE TABLE IF NOT EXISTS policy_document (
  id BIGINT(20) NOT NULL AUTO_INCREMENT,
  owner_username VARCHAR(191) NOT NULL,
  file_hash CHAR(64) NOT NULL COMMENT '文件 SHA-256，用于去重',
  title VARCHAR(300) NOT NULL DEFAULT '' COMMENT '文件标题（解析或取文件名）',
  original_filename VARCHAR(300) NULL COMMENT '原始文件名',
  issuer VARCHAR(191) NULL COMMENT '发文机关',
  document_no VARCHAR(120) NULL COMMENT '文号，如 银发〔2026〕1号',
  publish_date DATE NULL COMMENT '发布日期',
  full_text MEDIUMTEXT NULL COMMENT '解析出的全文',
  page_count INT NULL COMMENT '页数',
  status ENUM('uploaded','analyzing','completed','failed') NOT NULL DEFAULT 'uploaded',
  error_message VARCHAR(500) NULL,
  model_name VARCHAR(50) NULL COMMENT '分析所用模型',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_policy_document_hash (owner_username, file_hash),
  KEY idx_policy_document_list (owner_username, created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='政策文件（用户上传）';

CREATE TABLE IF NOT EXISTS policy_analysis (
  id BIGINT(20) NOT NULL AUTO_INCREMENT,
  document_id BIGINT(20) NOT NULL,
  owner_username VARCHAR(191) NOT NULL,
  summary TEXT NULL COMMENT '政策要点摘要',
  domains JSON NULL COMMENT '涉及领域数组，如 ["货币政策","财政政策"]',
  impact_direction ENUM('bullish','bearish','neutral') NULL COMMENT '对债市影响方向',
  impact_reason TEXT NULL COMMENT '影响推理说明',
  evidence JSON NULL COMMENT '原文依据片段数组（方向判断必须附依据）',
  key_points JSON NULL COMMENT '分条要点',
  model_name VARCHAR(50) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_policy_analysis_document (document_id),
  KEY idx_policy_analysis_owner (owner_username, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='政策文件 AI 分析结果';