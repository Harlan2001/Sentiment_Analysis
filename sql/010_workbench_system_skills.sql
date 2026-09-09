CREATE TABLE IF NOT EXISTS workbench_user_system_skills (
    username VARCHAR(191) NOT NULL,
    skill_id CHAR(36) NOT NULL,
    enabled_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (username, skill_id),
    KEY idx_workbench_user_system_skills_skill (skill_id, username),
    CONSTRAINT fk_workbench_user_system_skills_skill
        FOREIGN KEY (skill_id) REFERENCES workbench_skills(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
