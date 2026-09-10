DELETE FROM workbench_skills
WHERE owner_type = 'system'
  AND id IN (
      '00000000-0000-4000-8000-000000000001',
      '00000000-0000-4000-8000-000000000002',
      '00000000-0000-4000-8000-000000000003',
      '00000000-0000-4000-8000-000000000004',
      '00000000-0000-4000-8000-000000000005'
  );

INSERT INTO workbench_skills
    (id, owner_username, owner_type, name, description, instructions, input_schema_json, output_format, status, version_no)
VALUES
    (
        '00000000-0000-4000-8000-000000000101', NULL, 'system',
        '策略变化复盘',
        '对比策略快照与推荐历史，解释策略变化及其依据。',
        '适用于复盘策略或推荐结果的近期变化。先调用策略快照、AI策略推荐、推荐历史或变动监控工具取得真实数据，并说明数据时间。比较新增、删除、方向调整和重要参数变化，解释变化与新闻或因子证据的关系。按“变化摘要、变化明细、原因解释、主要风险、下一步观察”输出。工具无数据或时间范围不足时如实说明，不编造变化，不作确定性收益承诺。',
        JSON_ARRAY(), 'markdown', 'published', 1
    ),
    (
        '00000000-0000-4000-8000-000000000102', NULL, 'system',
        '重大新闻冲击评估',
        '结合新闻原文、历史事件和收益率变化评估事件影响。',
        '适用于判断一条新闻或事件对债券市场的影响。先调用新闻搜索或详情工具核对原文和时间，再根据可用信息查询相似历史新闻、新闻分析和事件前后收益率。区分已确认事实与分析判断，说明影响方向、传导路径、可能持续时间和证据强弱。按“事件摘要、影响链条、受影响对象、历史参考、不确定性”输出。工具无数据时明确列出缺失项，不得补造新闻、行情或结论。',
        JSON_ARRAY(), 'markdown', 'published', 1
    ),
    (
        '00000000-0000-4000-8000-000000000103', NULL, 'system',
        '因子异动与驱动溯源',
        '结合因子、关联新闻和宏观信号解释近期异动。',
        '适用于解释某个因子或某类因子的近期变化。先调用因子列表或分类因子工具确认因子定义和当前状态，再查询关联新闻与可用宏观方向性信号。区分政策、宏观、流动性、风险、情绪和行业驱动，识别一致证据与矛盾信号。按“异动结论、主要证据、驱动分类、矛盾信号、待验证事项”输出并说明数据时间。没有足够数据时降低结论强度，不编造因子数值或新闻。',
        JSON_ARRAY(), 'markdown', 'published', 1
    )
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    description = VALUES(description),
    instructions = VALUES(instructions),
    input_schema_json = VALUES(input_schema_json),
    output_format = VALUES(output_format),
    status = VALUES(status),
    archived_at = NULL,
    updated_at = CURRENT_TIMESTAMP(6);

INSERT IGNORE INTO workbench_skill_versions
    (skill_id, version_no, name, description, instructions, input_schema_json, output_format, status, created_by)
SELECT id, version_no, name, description, instructions, input_schema_json, output_format, status, 'system'
FROM workbench_skills
WHERE id IN (
    '00000000-0000-4000-8000-000000000101',
    '00000000-0000-4000-8000-000000000102',
    '00000000-0000-4000-8000-000000000103'
);
