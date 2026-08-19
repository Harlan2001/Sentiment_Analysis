CREATE TABLE IF NOT EXISTS workbench_project_memories (
    id CHAR(36) PRIMARY KEY,
    project_id CHAR(36) NOT NULL,
    category ENUM('background', 'goal', 'constraint', 'preference', 'conclusion', 'other') NOT NULL DEFAULT 'other',
    title VARCHAR(120) NOT NULL,
    content TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by VARCHAR(191) NOT NULL,
    updated_by VARCHAR(191) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_workbench_project_memories_list (project_id, is_active, updated_at, id),
    CONSTRAINT fk_workbench_memory_project
        FOREIGN KEY (project_id) REFERENCES workbench_projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE workbench_project_members ADD COLUMN updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6);
