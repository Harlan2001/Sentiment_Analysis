CREATE TABLE IF NOT EXISTS workbench_skills (
    id CHAR(36) PRIMARY KEY,
    owner_username VARCHAR(191) NULL,
    owner_type ENUM('system', 'user') NOT NULL DEFAULT 'user',
    name VARCHAR(120) NOT NULL,
    description VARCHAR(500) NOT NULL,
    instructions TEXT NOT NULL,
    input_schema_json JSON NOT NULL,
    output_format ENUM('markdown', 'text') NOT NULL DEFAULT 'markdown',
    status ENUM('draft', 'published', 'archived') NOT NULL DEFAULT 'draft',
    version_no INT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    archived_at DATETIME(6) NULL,
    KEY idx_workbench_skills_owner_updated (owner_username, status, updated_at, id),
    KEY idx_workbench_skills_system_updated (owner_type, status, updated_at, id),
    CONSTRAINT chk_workbench_skills_owner CHECK (
        (owner_type = 'system' AND owner_username IS NULL) OR
        (owner_type = 'user' AND owner_username IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS workbench_skill_versions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    skill_id CHAR(36) NOT NULL,
    version_no INT UNSIGNED NOT NULL,
    name VARCHAR(120) NOT NULL,
    description VARCHAR(500) NOT NULL,
    instructions TEXT NOT NULL,
    input_schema_json JSON NOT NULL,
    output_format ENUM('markdown', 'text') NOT NULL,
    status ENUM('draft', 'published', 'archived') NOT NULL,
    created_by VARCHAR(191) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_workbench_skill_versions (skill_id, version_no),
    CONSTRAINT fk_workbench_skill_versions_skill
        FOREIGN KEY (skill_id) REFERENCES workbench_skills(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
