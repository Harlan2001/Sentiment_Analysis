CREATE TABLE IF NOT EXISTS workbench_watchlist_items (
    id CHAR(36) PRIMARY KEY,
    owner_username VARCHAR(191) NOT NULL,
    object_type ENUM('news', 'factor', 'macro_signal') NOT NULL,
    object_id VARCHAR(191) NOT NULL,
    title VARCHAR(240) NOT NULL,
    source_url VARCHAR(500) NULL,
    metadata_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    deleted_at DATETIME(6) NULL,
    UNIQUE KEY uq_workbench_watchlist_owner_object (owner_username, object_type, object_id),
    KEY idx_workbench_watchlist_owner_updated (owner_username, deleted_at, updated_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
