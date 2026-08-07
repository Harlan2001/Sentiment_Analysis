CREATE TABLE IF NOT EXISTS workbench_projects (
    id CHAR(36) PRIMARY KEY,
    owner_username VARCHAR(191) NOT NULL,
    name VARCHAR(80) NOT NULL,
    description VARCHAR(1000) NULL,
    visibility ENUM('private', 'shared') NOT NULL DEFAULT 'private',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_workbench_projects_updated (updated_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS workbench_project_members (
    project_id CHAR(36) NOT NULL,
    username VARCHAR(191) NOT NULL,
    role ENUM('owner', 'editor', 'viewer') NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (project_id, username),
    KEY idx_workbench_members_username (username, project_id),
    CONSTRAINT fk_workbench_member_project
        FOREIGN KEY (project_id) REFERENCES workbench_projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS workbench_conversations (
    id CHAR(36) PRIMARY KEY,
    owner_username VARCHAR(191) NOT NULL,
    project_id CHAR(36) NULL,
    title VARCHAR(120) NULL,
    module_type VARCHAR(32) NOT NULL DEFAULT 'chat',
    source ENUM('home', 'sidebar', 'project') NOT NULL,
    status ENUM('active', 'archived') NOT NULL DEFAULT 'active',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    last_message_at DATETIME(6) NULL,
    KEY idx_workbench_conversations_owner_recent
        (owner_username, project_id, status, last_message_at, id),
    KEY idx_workbench_conversations_project_recent
        (project_id, status, last_message_at, id),
    CONSTRAINT fk_workbench_conversation_project
        FOREIGN KEY (project_id) REFERENCES workbench_projects(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS workbench_messages (
    id CHAR(36) PRIMARY KEY,
    conversation_id CHAR(36) NOT NULL,
    parent_message_id CHAR(36) NULL,
    role ENUM('user', 'assistant') NOT NULL,
    content LONGTEXT NOT NULL,
    status ENUM('streaming', 'completed', 'failed', 'interrupted') NOT NULL,
    client_message_id VARCHAR(191) NULL,
    error_code VARCHAR(80) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    completed_at DATETIME(6) NULL,
    UNIQUE KEY uq_workbench_user_message_client_id
        (conversation_id, client_message_id),
    KEY idx_workbench_messages_conversation (conversation_id, created_at, id),
    CONSTRAINT fk_workbench_message_conversation
        FOREIGN KEY (conversation_id) REFERENCES workbench_conversations(id) ON DELETE CASCADE,
    CONSTRAINT fk_workbench_message_parent
        FOREIGN KEY (parent_message_id) REFERENCES workbench_messages(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

