ALTER TABLE workbench_projects ADD COLUMN deleted_at DATETIME(6) NULL;
ALTER TABLE workbench_conversations ADD COLUMN deleted_at DATETIME(6) NULL;
