// 策略生成演示：纯前端写死数据 + 状态机。
// 命中演示标的（含「金融科技」）时，由 workbench.ts 的策略 API 拦截并返回这里的写死内容，
// 模拟「输入标的 → 展示提示词 → 确认 → 约 10s → 出结果」的真实交互，全程不调后端、不调模型。
// 说明：本文件只 `import type`（编译期擦除，不产生运行时循环依赖），供 workbench.ts 反向引用。

import type { StrategyConversation, StrategyConversationDetail, StrategyDraft } from '@/api/workbench'

// ── 演示标的 ──────────────────────────────────────────────
export const DEMO_INSTRUMENT = {
  name: '中证金融科技主题指数',
  code: '930986',
  etf: '金融科技ETF',
  asOf: '2026-08-25',
  current: '1823.50',
}

/** 哨兵会话 id，避开真实自增 id，仅在前端内存中存在 */
export const DEMO_CONVERSATION_ID = -999001

/** 命中演示标的：覆盖「中证金融科技主题指数 / 金融科技ETF / 金融科技指数」等写法 */
export function isDemoInstrument(title: string): boolean {
  return !!title && (title.includes('金融科技') || title.includes('中证金融'))
}

// ── 演示状态机（Date.now() 计时，模拟约 10s 异步生成） ────
type DemoPhase = 'draft' | 'running'
let phase: DemoPhase = 'draft'
let runningStartedAt = 0
let demoTitle = DEMO_INSTRUMENT.name
let demoCreatedIso: string | null = null
const GENERATION_DELAY_MS = 10000

/** 新建会话时复位到草稿态 */
export function resetDemo(): void {
  phase = 'draft'
  runningStartedAt = 0
}

/** 确认生成时进入 running 态并计时 */
export function markRunning(): void {
  phase = 'running'
  runningStartedAt = Date.now()
}

function isDone(): boolean {
  return phase === 'running' && Date.now() - runningStartedAt >= GENERATION_DELAY_MS
}

// ── 写死：提示词草稿（须含 [TRADING_PARAMETERS] 块供 extractTradingParameters 解析） ──
const DEMO_PROMPT_DRAFT = `交易规则与策略需求

标的：中证金融科技主题指数（金融科技ETF）
策略需求：构建「均线趋势 + 新闻情绪」双因子择时策略，用新闻情感分析对趋势信号做方向确认与仓位调节，在控制回撤的前提下捕捉 AI 金融科技主线的波段机会。

交易参数
1. 开仓规则：5日均线上穿20日均线，且收盘价站上20日均线
2. 平仓规则：5日均线跌破20日均线，或触发止盈止损
3. 单笔仓位：20%资金
4. 止损：1.5%
5. 止盈：3.0%
6. 回测区间：最近2年
7. 信号频率：日频

策略要求
在中证金融科技主题指数上，以 5 日均线与 20 日均线交叉决定多空方向，叠加新闻情绪得分做方向确认与仓位调节。情绪偏多且均线金叉时做多，情绪转负或均线死叉时离场；情绪强正面时提高仓位，情绪中性时降低仓位，情绪转负时清仓离场。

正式结果契约
本轮将生成正式策略版本，包含策略概要、回测代码、回测指标与回测日志，并在策略中体现对新闻情绪的分析。

当前市场情况
市场口径为中证金融科技主题指数，频率为日频；技术状态震荡偏强，5 日均线与 20 日均线趋于多头排列，短中期趋势向好。

本轮新闻情绪分析
近 7 日方向性事件共 12 条，其中正面 9 条、负面 3 条，情绪得分 +0.5，整体偏多。正面事件集中于大模型金融应用落地与金融科技 ETF 获资金净流入，负面事件主要为估值波动与监管问询。结论：AI 金融科技主线情绪偏暖，可作为多头方向的确认信号。

请生成策略`

// ── 写死：策略概要 ────────────────────────────────────────
const DEMO_SUMMARY = `策略名称：中证金融科技主题指数 · 均线趋势 + 新闻情绪 择时策略
标的：中证金融科技主题指数（金融科技ETF）
策略类型：日频双因子择时，技术面趋势 + 新闻情绪共振

一、策略背景与目标
本策略面向 AI 金融科技主题的中期波段机会。该板块波动较大、受消息面驱动明显，单纯依赖价格均线容易在震荡期反复止损，因此引入新闻情绪作为第二因子，在趋势信号之上做方向确认与仓位调节。目标是：趋势明确且情绪共振时提高暴露，情绪退潮或趋势破坏时降低回撤。

二、因子构成
1. 技术面趋势因子：以 5 日均线与 20 日均线的交叉判断多空方向，金叉视为趋势转多、死叉视为趋势转空，并要求收盘价站上 20 日均线以确认有效性。
2. 新闻情绪因子：对每日新闻做情感分析，聚合方向性事件数量、正负面事件占比与情绪得分，得分归一化到 -1 至 +1 区间。高于 +0.3 视为偏多，低于 -0.3 视为偏空，之间视为中性。

三、信号规则
1. 开仓条件：5 日均线上穿 20 日均线，收盘价站上 20 日均线，且当日情绪得分高于 -0.3，即情绪非空头。
2. 仓位调节：情绪得分高于 +0.5 时加仓至 30% 仓位；中性情绪降仓至 10%；情绪转负（低于 -0.3）清仓离场。
3. 平仓条件：5 日均线跌破 20 日均线，或触发 1.5% 止损、3.0% 止盈，或情绪得分急转负面（低于 -0.3）。

四、回测结果（最近 2 年，日频）
1. 均线交叉共触发 48 次信号，经新闻情绪过滤后实际成交 36 次，过滤约 25% 的伪信号。
2. 累计收益 +18.6%，复合年化收益率 +8.9%。
3. 最大回撤 9.8%，年化波动 11.0%，夏普比率 0.63。
4. 胜率 41.0%，盈亏比 2.0，对应止损 1.5% 与止盈 3.0% 的 2:1 结构。

五、策略结论
新闻情绪因子有效提升了信号质量，使策略在 AI 金融科技主线上的胜率与回撤表现优于纯均线策略，适合作为主题机会的择时框架。需要注意的风险：情绪因子在极端行情下可能存在滞后，建议结合资金面与政策信号动态调整仓位与止盈止损参数。`

// ── 写死：回测代码（Python 风格伪代码，形如 Dream 回传） ──
const DEMO_CODE = `"""
中证金融科技主题指数 · 均线趋势 + 新闻情绪 择时策略
技术面（5 日与 20 日均线交叉）给出多空方向，新闻情感分析给出方向确认与仓位调节。
"""
import numpy as np
import pandas as pd


class FinTechSentimentTrend:
    """趋势与情绪双因子择时策略"""

    # 均线与风控参数
    FAST = 5
    SLOW = 20
    STOP_LOSS = 0.015
    TAKE_PROFIT = 0.03

    # 仓位参数
    BASE_POSITION = 0.20        # 单笔基础仓位
    MAX_POSITION = 0.30         # 强正面情绪时的加仓上限
    NEUTRAL_POSITION = 0.10     # 中性情绪时的降仓水平

    # 情绪阈值
    SENT_LONG = 0.3             # 情绪偏多阈值
    SENT_SHORT = -0.3           # 情绪偏空阈值
    SENT_STRONG = 0.5           # 强正面加仓阈值

    # 1. 数据准备：价格序列与新闻情绪按日期对齐
    def prepare(self, prices, sentiment):
        df = prices[['close']].copy()
        sent = sentiment.set_index('date')[['pos_events', 'neg_events']]
        df = df.join(sent, how='left')
        df[['pos_events', 'neg_events']] = df[['pos_events', 'neg_events']].fillna(0)
        df['score'] = self.sentiment_score(df['pos_events'], df['neg_events'])
        return df

    # 2. 情绪打分：由正负面事件占比映射到 -1 至 +1 区间
    def sentiment_score(self, pos, neg):
        total = pos + neg
        # 正面事件多则得分接近 +1，负面事件多则接近 -1，无事件时为中性 0
        return np.where(total > 0, (pos - neg) / total, 0.0)

    # 3. 技术面信号：5 日与 20 日均线交叉
    def trend_signal(self, df):
        ma_fast = df['close'].rolling(self.FAST).mean()
        ma_slow = df['close'].rolling(self.SLOW).mean()
        golden = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))
        dead = (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))
        trend = pd.Series(0, index=df.index)
        trend[golden] = 1
        trend[dead] = -1
        return trend.replace(0, np.nan).ffill().fillna(0)

    # 4. 情绪状态划分
    def sentiment_state(self, score):
        if score >= self.SENT_STRONG:
            return 'strong_positive'
        if score >= self.SENT_LONG:
            return 'positive'
        if score <= self.SENT_SHORT:
            return 'negative'
        return 'neutral'

    # 5. 情绪状态对应的仓位系数
    def position_factor(self, state):
        mapping = {
            'strong_positive': self.MAX_POSITION,
            'positive': self.BASE_POSITION,
            'neutral': self.NEUTRAL_POSITION,
            'negative': 0.0,
        }
        return mapping[state]

    # 6. 组合信号与回测
    def backtest(self, df):
        df = df.copy()
        df['trend'] = self.trend_signal(df)
        df['state'] = df['score'].apply(self.sentiment_state)

        # 方向：均线多头且情绪非空头时才持有
        df['direction'] = np.where(df['trend'] > 0, 1, 0)
        df['direction'] = np.where(df['state'] == 'negative', 0, df['direction'])

        # 仓位：方向乘以情绪仓位系数
        df['position'] = df['direction'] * df['state'].apply(self.position_factor)

        # 收益：次日收益乘以当日仓位（信号次日生效）
        df['ret'] = df['close'].pct_change()
        df['strat_ret'] = df['ret'] * df['position'].shift(1)
        df['strat_ret'] = self.apply_stop_take_profit(df)

        df['equity'] = (1 + df['strat_ret']).cumprod()
        return df

    # 7. 止损止盈：持仓期间触发 1.5% 止损或 3.0% 止盈即离场
    def apply_stop_take_profit(self, df):
        strat_ret = df['strat_ret'].copy()
        in_position = df['position'].shift(1).fillna(0) > 0
        entry = df['close'].where(in_position & ~in_position.shift(1).fillna(False)).ffill()
        pnl = df['close'] / entry - 1
        exit_long = in_position & ((pnl >= self.TAKE_PROFIT) | (pnl <= -self.STOP_LOSS))
        strat_ret[exit_long] = 0.0
        return strat_ret

    # 8. 绩效统计
    def report(self, df):
        equity = df['equity']
        years = len(df) / 252
        cagr = equity.iloc[-1] ** (1 / years) - 1
        max_drawdown = (equity / equity.cummax() - 1).min()
        annual_vol = df['strat_ret'].std() * np.sqrt(252)
        sharpe = (cagr - 0.02) / annual_vol
        return {
            'compounding_annual_return': cagr,
            'max_drawdown': max_drawdown,
            'annual_volatility': annual_vol,
            'sharpe_ratio': sharpe,
        }


if __name__ == '__main__':
    # 中证金融科技主题指数日线行情与新闻情绪打分（由新闻情感分析模块产出）
    prices = pd.read_parquet('fintech_index_daily.parquet')
    sentiment = pd.read_parquet('fintech_news_sentiment_daily.parquet')

    strategy = FinTechSentimentTrend()
    data = strategy.prepare(prices, sentiment)
    result = strategy.backtest(data)
    print(strategy.report(result))`

// ── 写死：回测日志（STATISTICS:: 格式，与真实 Dream 产物一致） ──
const DEMO_LOG = `[Strategy] 中证金融科技主题指数 · 均线趋势 + 新闻情绪 择时策略
[Data] prices=fintech_index_daily, sentiment=fintech_news_sentiment_daily
[Sentiment] 近7日方向性事件=12, 正面=9, 负面=3, 情绪得分=+0.5
[Backtest] period=最近2年, freq=日频, fast=5, slow=20, stop_loss=1.5%, take_profit=3.0%
[Signal] 均线交叉触发=48, 新闻情绪过滤后成交=36
STATISTICS:: Start Equity                1,000,000
STATISTICS:: End Equity                  1,186,000
STATISTICS:: Net Profit                  186,000
STATISTICS:: Compounding Annual Return   8.9%
STATISTICS:: Drawdown                    9.8%
STATISTICS:: Sharpe Ratio                0.63
STATISTICS:: Annual Standard Deviation   11.0%
STATISTICS:: Win Rate                    41.0%
STATISTICS:: Profit-Loss Ratio           2.0
STATISTICS:: Total Orders                36
[Backtest] exit_code=0, passed=True`

// ── 写死：回测指标（英文 key，对齐 BACKTEST_METRIC_LABELS 与 metricTone） ──
// 内部严格自洽：净利润=期末-初始；年化=(1.186)^(1/2)-1=8.9%；夏普=(8.9%-2%)/11%=0.63；盈亏比=止盈/止损=2.0
const DEMO_METRICS = [
  { label: 'Start Equity', value: '1,000,000' },
  { label: 'End Equity', value: '1,186,000' },
  { label: 'Net Profit', value: '186,000' },
  { label: 'Compounding Annual Return', value: '8.9%' },
  { label: 'Drawdown', value: '9.8%' },
  { label: 'Sharpe Ratio', value: '0.63' },
  { label: 'Annual Standard Deviation', value: '11.0%' },
  { label: 'Win Rate', value: '41.0%' },
  { label: 'Profit-Loss Ratio', value: '2.0' },
  { label: 'Total Orders', value: '36' },
]

// ── 写死：相关新闻（AI 金融科技主题，演示用） ──────────────
const DEMO_NEWS = [
  { news_id: 10001, title: 'AI 金融科技板块午后走强，金融科技指数涨逾 2%', source: '财联社', publish_time: '2026-08-25 14:30' },
  { news_id: 10002, title: '多家券商研报：大模型金融应用进入落地期，智能投研与风控率先受益', source: '证券时报', publish_time: '2026-08-24 09:10' },
  { news_id: 10003, title: '金融科技ETF获资金净流入，机构加仓 AI 金融主题', source: '中国证券报', publish_time: '2026-08-23 16:45' },
  { news_id: 10004, title: '机构调研：金融科技板块情绪回暖，大模型投研应用成关注焦点', source: '上海证券报', publish_time: '2026-08-22 11:20' },
]

// ── 构造：会话 / 草稿 / 详情 ──────────────────────────────

export function buildDemoConversation(title: string): StrategyConversation {
  demoTitle = title || DEMO_INSTRUMENT.name
  demoCreatedIso = new Date().toISOString()
  return {
    id: DEMO_CONVERSATION_ID,
    title: demoTitle,
    instrument: DEMO_INSTRUMENT.name,
    status: 'active',
    current_local_version_no: 0,
    last_message_at: demoCreatedIso,
    created_at: demoCreatedIso,
    updated_at: demoCreatedIso,
  }
}

/** 列表页读取：返回当前演示会话（已创建时），用于在历史记录中展示并可点击进入 */
export function getDemoConversation(): StrategyConversation | null {
  if (!demoCreatedIso) return null
  const now = new Date().toISOString()
  return {
    id: DEMO_CONVERSATION_ID,
    title: demoTitle,
    instrument: DEMO_INSTRUMENT.name,
    status: 'active',
    current_local_version_no: isDone() ? 1 : 0,
    last_message_at: now,
    created_at: demoCreatedIso,
    updated_at: now,
  }
}

/** 从列表中删除演示会话（仅清除内存态） */
export function clearDemo(): void {
  demoCreatedIso = null
  phase = 'draft'
  runningStartedAt = 0
}

export function buildDemoDraft(): StrategyDraft {
  return {
    user_message_id: 1,
    assistant_message_id: 2,
    status: 'pending_confirmation',
    system_draft_prompt: DEMO_PROMPT_DRAFT,
    context: {},
  }
}

export function buildDemoDetail(): StrategyConversationDetail {
  const done = isDone()
  const assistantStatus = done ? 'succeeded' : phase === 'running' ? 'running' : 'pending_confirmation'
  const now = new Date().toISOString()

  const version = done
    ? {
        id: 1,
        source_message_id: 2,
        local_version_no: 1,
        name: `${DEMO_INSTRUMENT.name} · 趋势跟随策略`,
        description: DEMO_SUMMARY,
        code: DEMO_CODE,
        backtest_passed: true,
        backtest_exit_code: '0',
        backtest_summary: DEMO_LOG,
        backtest_metrics_json: DEMO_METRICS,
        created_at: now,
      }
    : null

  return {
    conversation: {
      id: DEMO_CONVERSATION_ID,
      title: demoTitle,
      instrument: DEMO_INSTRUMENT.name,
      status: 'active',
      current_local_version_no: done ? 1 : 0,
      last_message_at: now,
      created_at: now,
      updated_at: now,
    },
    messages: [
      {
        id: 1,
        sequence_no: 1,
        role: 'user',
        content: demoTitle,
        status: 'succeeded',
        created_at: now,
        updated_at: now,
      },
      {
        id: 2,
        sequence_no: 2,
        role: 'assistant',
        content: '',
        status: assistantStatus,
        system_draft_prompt: DEMO_PROMPT_DRAFT,
        references_json: DEMO_NEWS,
        context_json: {},
        created_at: now,
        updated_at: now,
      },
    ],
    versions: version ? [version] : [],
  }
}
