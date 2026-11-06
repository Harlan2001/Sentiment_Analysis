-- 策略生成进度回写（B1 / S2-3）
--
-- 背景：确认后到结果返回之间最长约 15 分钟，前端只有一根静态"生成中"灰条。
-- service 接收循环其实能收到对端 strategy_generation_status（1 生成中 /
-- 2 检查回测中 / 3 重生中）与分批 backtest_log，但此前不透传。
--
-- stage 取值（我方内部口径；不展示对端内部重试次数）：
--   preparing          已确认、正在提交远端
--   generating         对端生成中（status=1）
--   backtest_checking  对端检查回测中（status=2）
--   regenerating       对端内部重生中（status=3）
--   revising           我方验收门未过，带原因发起新一轮修正（第 N 轮在前端按消息计数）
--   validating         结果已回收，我方验收门判定中
--   succeeded/failed/timed_out/cancelled 终态
-- log_tail：回测日志尾部（最近约 28 行），仅 running 期间更新。
-- run_started_at：点「确认并生成」的时刻（created_at 是更早的草稿创建时间）。
--   前端已用时长与 16 分钟轮询上限都以它为锚点，刷新页面也不重置。

ALTER TABLE `ai_strategy_messages`
  ADD COLUMN `stage` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL
    COMMENT '生成阶段（preparing/generating/backtest_checking/regenerating/revising/validating/终态）' AFTER `status`,
  ADD COLUMN `stage_updated_at` datetime DEFAULT NULL
    COMMENT '阶段最近更新时间，前端据此显示阶段新鲜度' AFTER `stage`,
  ADD COLUMN `run_started_at` datetime DEFAULT NULL
    COMMENT '本轮运行开始（确认）时间，前端计时与轮询上限锚点' AFTER `stage_updated_at`,
  ADD COLUMN `log_tail` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    COMMENT '回测日志尾部快照（最近约28行）' AFTER `validation_json`;
