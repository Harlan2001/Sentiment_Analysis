ALTER TABLE workbench_projects ADD COLUMN client_request_id VARCHAR(191) NULL;
CREATE UNIQUE INDEX uq_workbench_project_create_request
    ON workbench_projects (owner_username, client_request_id);
