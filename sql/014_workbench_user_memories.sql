CREATE TABLE IF NOT EXISTS workbench_user_memories (
  id CHAR(36) NOT NULL,
  owner_username VARCHAR(191) NOT NULL,
  category ENUM('response_preference','user_background','long_term_interest','personal_constraint') NOT NULL DEFAULT 'response_preference',
  normalized_key VARCHAR(64) NOT NULL,
  title VARCHAR(120) NOT NULL,
  content TEXT NOT NULL,
  source_type ENUM('manual','explicit_chat','inferred_chat') NOT NULL DEFAULT 'manual',
  source_conversation_id CHAR(36) NULL,
  source_message_id CHAR(36) NULL,
  status ENUM('pending','active','disabled','deleted') NOT NULL DEFAULT 'active',
  confidence DECIMAL(4,3) NULL,
  is_pinned TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  last_used_at DATETIME(6) NULL,
  deleted_at DATETIME(6) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_workbench_user_memory_source (owner_username, source_message_id, normalized_key),
  KEY idx_workbench_user_memories_list (owner_username, status, is_pinned, updated_at, id),
  KEY idx_workbench_user_memories_key (owner_username, normalized_key, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS workbench_user_memory_settings (
  owner_username VARCHAR(191) NOT NULL,
  memory_enabled TINYINT(1) NOT NULL DEFAULT 1,
  auto_extract_enabled TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (owner_username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
