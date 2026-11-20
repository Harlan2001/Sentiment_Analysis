# sql/

此目录保留**测试库 schema 的权威来源**和仍需独立执行的系统技能数据脚本：

- `schema_full.sql` —— 生产库 `Sentiment_analysis` 表结构的**只读导出快照**
  （由 `scripts/export_prod_schema.py` 生成，已提交进仓库；`scripts/migrate_test_db.py`
  据此重建测试库 `Sentiment_analysis_test`，保证集成测试与生产结构一致）。
- `012_workbench_system_skills_v2.sql`、`013_workbench_system_skills_research_suite.sql`
  —— 8 个系统技能的初始化/升级数据脚本。结构快照不含业务数据，需要系统技能的
  环境应按编号顺序执行；`migrate_test_db.py` 只重建表结构，不会自动执行这两个脚本。
- 已合并进快照的历史结构迁移不再保留。后续新增结构迁移使用 `NNN_*.sql`，
  生产执行并重新导出 `schema_full.sql` 后，可在后续变更中清理已合并的迁移文件。

## 如何更新

生产 schema 演进后，在可信内网环境重新导出并提交：

```bash
uv run python scripts/export_prod_schema.py --db Sentiment_analysis --confirm-prod --output sql/schema_full.sql
git add sql/schema_full.sql && git commit -m "schema: 同步生产表结构"
```
