-- 修复 user_page_view 表中 action_detail 为 NULL 的记录，替换为 JSON 空对象
UPDATE user_page_view
SET action_detail = '{}'
WHERE action_detail IS NULL;