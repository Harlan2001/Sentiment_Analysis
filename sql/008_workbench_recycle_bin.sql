-- 工作流产物回收站：任务本身可恢复，原始新闻与上传研报不受影响。
ALTER TABLE report_generation_tasks
    ADD COLUMN deleted_at DATETIME(6) NULL,
    ADD KEY idx_report_generation_owner_deleted_updated (owner_username, deleted_at, updated_at);

ALTER TABLE daily_news_summary_tasks
    ADD COLUMN deleted_at DATETIME(6) NULL,
    ADD KEY idx_daily_news_summary_owner_deleted_updated (owner_username, deleted_at, updated_at);
