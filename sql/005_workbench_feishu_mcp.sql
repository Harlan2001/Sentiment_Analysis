CREATE TABLE IF NOT EXISTS workbench_feishu_oauth_states (
    state_hash CHAR(64) PRIMARY KEY,
    username VARCHAR(191) NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_workbench_feishu_oauth_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS workbench_feishu_connections (
    username VARCHAR(191) PRIMARY KEY,
    feishu_user_id VARCHAR(191) NULL,
    tenant_key VARCHAR(191) NULL,
    scopes JSON NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at DATETIME NOT NULL,
    connected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME NULL,
    KEY idx_workbench_feishu_connections_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS workbench_feishu_mcp_audit_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(191) NOT NULL,
    tool_name VARCHAR(80) NOT NULL,
    success BOOLEAN NOT NULL,
    detail VARCHAR(500) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_workbench_feishu_audit_user_created (username, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
