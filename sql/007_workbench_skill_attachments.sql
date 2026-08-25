CREATE TABLE IF NOT EXISTS workbench_skill_attachments (
    id CHAR(36) PRIMARY KEY,
    skill_id CHAR(36) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(120) NULL,
    size_bytes BIGINT UNSIGNED NOT NULL,
    created_by VARCHAR(191) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_workbench_skill_attachments_skill (skill_id, created_at),
    CONSTRAINT fk_workbench_skill_attachments_skill
        FOREIGN KEY (skill_id) REFERENCES workbench_skills(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
