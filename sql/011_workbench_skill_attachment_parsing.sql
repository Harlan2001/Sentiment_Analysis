ALTER TABLE workbench_skill_attachments
    ADD COLUMN parse_status ENUM('stored', 'pending', 'parsing', 'ready', 'failed') NOT NULL DEFAULT 'stored' AFTER size_bytes;

ALTER TABLE workbench_skill_attachments
    ADD COLUMN parse_error VARCHAR(1000) NULL AFTER parse_status;

ALTER TABLE workbench_skill_attachments
    ADD COLUMN page_count INT UNSIGNED NULL AFTER parse_error;

ALTER TABLE workbench_skill_attachments
    ADD COLUMN parsed_at DATETIME(6) NULL AFTER page_count;

CREATE TABLE IF NOT EXISTS workbench_skill_attachment_chunks (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    attachment_id CHAR(36) NOT NULL,
    skill_id CHAR(36) NOT NULL,
    source_location VARCHAR(255) NOT NULL,
    chunk_index INT UNSIGNED NOT NULL,
    content MEDIUMTEXT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_workbench_skill_attachment_chunk (attachment_id, chunk_index),
    KEY idx_workbench_skill_attachment_chunks_skill (skill_id, attachment_id),
    CONSTRAINT fk_workbench_skill_attachment_chunks_attachment
        FOREIGN KEY (attachment_id) REFERENCES workbench_skill_attachments(id) ON DELETE CASCADE,
    CONSTRAINT fk_workbench_skill_attachment_chunks_skill
        FOREIGN KEY (skill_id) REFERENCES workbench_skills(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
