-- Execute only in AI_STRATEGY_HISTORY_MYSQL_DATABASE after the base history migration.
ALTER TABLE ai_strategy_versions ADD COLUMN backtest_metrics_json JSON NULL AFTER backtest_summary;
