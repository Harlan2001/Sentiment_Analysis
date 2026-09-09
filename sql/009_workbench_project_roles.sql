ALTER TABLE workbench_project_members
    MODIFY COLUMN role ENUM('owner', 'manager', 'editor', 'viewer') NOT NULL;

UPDATE workbench_project_members SET role = 'manager' WHERE role = 'owner';

UPDATE workbench_project_members SET role = 'editor' WHERE role = 'viewer';

ALTER TABLE workbench_project_members
    MODIFY COLUMN role ENUM('manager', 'editor') NOT NULL;
