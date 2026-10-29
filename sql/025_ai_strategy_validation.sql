-- 策略生成验收结论落库
--
-- 背景：DreamStrategy 平台的判定口径是"回测进程正常退出"，0 成交也算通过
-- （源码注释 total_trade_count=0 is OK）。实测 25 个历史模板里 21 个 0 成交却
-- 全部 passed，其中我们正在用的那个甚至只打印信号日志、从未下单。
-- 因此我方验收门的结论必须落库，并有独立字段，不能被 backtest_passed 覆盖语义。
--
-- verdict 取值：
--   passed          回测正常结束、解析到成交笔数、且成交 > 0
--   no_trade        回测正常结束但成交 0 笔（可带原因重生）
--   backtest_failed 回测未正常结束
--   backtest_error  回测结束但结果不可用（无成交行 / 标的不符 / 下单类型错配）

ALTER TABLE `ai_strategy_messages`
  ADD COLUMN `validation_json` JSON DEFAULT NULL
  COMMENT '我方验收门结论：verdict/steps/trade_count/reason 等' AFTER `context_json`;