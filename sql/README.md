# sql/

此目录是**测试库 schema 的权威来源**，只有一个文件：

- `schema_full.sql` —— 生产库 `Sentiment_analysis` 表结构的**只读导出快照**
  （由 `scripts/export_prod_schema.py` 生成，已提交进仓库；`scripts/migrate_test_db.py`
  据此重建测试库 `Sentiment_analysis_test`，保证集成测试与生产结构一致）。

## 如何更新

生产 schema 演进后，在可信内网环境重新导出并提交：

```bash
uv run python scripts/export_prod_schema.py --db Sentiment_analysis --confirm-prod --output sql/schema_full.sql
git add sql/schema_full.sql && git commit -m "schema: 同步生产表结构"
```
