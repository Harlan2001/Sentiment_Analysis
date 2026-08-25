CREATE TABLE IF NOT EXISTS workbench_message_skills (
    id CHAR(36) PRIMARY KEY,
    message_id CHAR(36) NOT NULL,
    skill_id CHAR(36) NULL,
    skill_name VARCHAR(120) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_workbench_message_skills_message (message_id, created_at),
    CONSTRAINT fk_workbench_message_skills_message
        FOREIGN KEY (message_id) REFERENCES workbench_messages(id) ON DELETE CASCADE,
    CONSTRAINT fk_workbench_message_skills_skill
        FOREIGN KEY (skill_id) REFERENCES workbench_skills(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
