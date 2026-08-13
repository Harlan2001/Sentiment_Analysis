-- Execute only after 20260728_ai_strategy_history_up.sql in AI_STRATEGY_HISTORY_MYSQL_DATABASE.
ALTER TABLE ai_strategy_messages ADD COLUMN system_draft_prompt MEDIUMTEXT NULL AFTER generated_prompt;
ALTER TABLE ai_strategy_messages ADD COLUMN user_edited_prompt MEDIUMTEXT NULL AFTER system_draft_prompt;
ALTER TABLE ai_strategy_messages ADD COLUMN final_sent_prompt MEDIUMTEXT NULL AFTER user_edited_prompt;
ALTER TABLE ai_strategy_messages ADD COLUMN context_json JSON NULL AFTER references_json;
