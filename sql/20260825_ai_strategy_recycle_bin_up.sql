-- Execute in AI_STRATEGY_HISTORY_MYSQL_DATABASE (or the business database when no
-- separate strategy history database is configured).
ALTER TABLE ai_strategy_conversations
    ADD COLUMN deleted_at DATETIME NULL,
    ADD KEY idx_ai_strategy_conversations_owner_deleted_updated (owner_username, deleted_at, updated_at);
