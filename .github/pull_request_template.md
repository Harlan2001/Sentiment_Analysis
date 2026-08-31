## 变更说明

<!-- 这个 PR 解决什么问题、为什么这么改、改了哪些模块/页面。一句话能说清最好。 -->

## 测试清单(DoD,评审前逐项自打勾;不满足的项先写清楚原因)

- [ ] 新增/修改的核心逻辑写了对应单测(pure 函数一律优先;LLM/DB 依赖已 mock,未调用真实 Kingstar/数据库)
- [ ] `uv run ruff check backend` 通过
- [ ] `npm run typecheck` 通过
- [ ] `npm run test`(vitest)通过
- [ ] `uv run pytest -m "not slow"` 通过
- [ ] 涉及数据库字段/迁移时,已同步更新对应 SQL 说明
- [ ] 本地自测走通关键路径(接口返回 / 页面交互)

> CI(github actions)会替你跑一遍上述检查,红则合并按钮不可用。

## 影响范围

- 后端模块：<!-- 例如 backend/macrosignal、backend/routers/daily_news_summary.py -->
- 前端页面：<!-- 例如 NewsPage、SkillsPage -->
- 数据库：无 / 有(说明变更)

## 补充说明

<!-- 截图、测试账号、已知限制、灰度注意事项等,没有可删掉本节 -->