import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/strategy', () => ({
  getStrategyConversation: vi.fn(),
  getSupportedInstruments: vi.fn(),
  createStrategyDraft: vi.fn(),
  confirmStrategyDraft: vi.fn(),
  cancelWaitStrategyGeneration: vi.fn(),
}))

import * as api from '@/api/strategy'
import type {
  StrategyConversation,
  StrategyConversationDetail,
  StrategyMessage,
  StrategyVersion,
} from '@/api/strategy'
import { EDITABLE_END, EDITABLE_START } from '../components/strategy/promptSections'
import { StrategyPromptPage } from './StrategyPromptPage'

const SYSTEM_DRAFT = `情报包前缀（受保护）
${EDITABLE_START}
[TRADING_PARAMETERS]
- 开仓规则：金叉
- 止损：1.5%
[/TRADING_PARAMETERS]

[INSTRUMENT]
- 交易标的：FCT_T_MAIN（中金所10年期国债期货）
- 回测模式：bar
- K线周期：1d
[/INSTRUMENT]

[STRATEGY_REQUIREMENT]
做一个5/20双均线策略
[/STRATEGY_REQUIREMENT]
${EDITABLE_END}
输出契约后缀。`

const INSTRUMENTS = {
  default: 'FCT_T_MAIN',
  instruments: [
    { code: 'FCT_T_MAIN', label: '中金所10年期国债期货（默认）' },
    { code: 'FCT_TL_MAIN', label: '中金所30年期国债期货' },
  ],
  excluded: [],
}

function makeConversation(title = '双均线策略'): StrategyConversation {
  return {
    id: 7,
    title,
    instrument: null,
    status: 'active',
    current_local_version_no: 0,
    last_message_at: null,
    created_at: '2026-10-30T14:00:00+08:00',
    updated_at: '2026-10-30T14:00:00+08:00',
    summary: {
      turn_status: 'idle', verdict: null, verdict_passed: false, failure_reason: null,
      instrument: null, instrument_code: null, backtest_mode: null,
      candle_interval: null, trade_count: null, annual_return: null,
    },
  }
}

function makeAssistant(overrides: Partial<StrategyMessage> = {}): StrategyMessage {
  return {
    id: 2,
    sequence_no: 2,
    role: 'assistant',
    content: '',
    status: 'pending_confirmation',
    system_draft_prompt: SYSTEM_DRAFT,
    user_edited_prompt: undefined,
    final_sent_prompt: undefined,
    references_json: [],
    context_json: { instrument_code: 'FCT_T_MAIN', token_used: 1200, token_budget: 6000 },
    validation_json: null,
    public_error_message: null,
    remote_message_id: null,
    elapsed_seconds: null,
    created_at: '2026-10-30T14:01:00+08:00',
    updated_at: '2026-10-30T14:01:00+08:00',
    ...overrides,
  }
}

function makeDetail(messages: StrategyMessage[], versions: StrategyVersion[] = []): StrategyConversationDetail {
  return { conversation: makeConversation(), messages, versions }
}

function renderPage(entry = '/strategy/prompt?id=7') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <StrategyPromptPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.mocked(api.getSupportedInstruments).mockResolvedValue(INSTRUMENTS)
  vi.mocked(api.confirmStrategyDraft).mockResolvedValue({})
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('StrategyPromptPage 五步向导（S2-2）', () => {
  it('待确认草稿：默认落在③确认发送，④⑤锁定不可点', async () => {
    vi.mocked(api.getStrategyConversation).mockResolvedValue(makeDetail([makeAssistant()]))
    renderPage()

    await screen.findByRole('heading', { name: '确认发送' })
    expect(screen.getByText('做一个5/20双均线策略')).toBeTruthy()

    const railGeneration = screen.getByRole('button', { name: /生成与回测/ })
    const railResult = screen.getByRole('button', { name: /结果报告/ })
    expect(railGeneration).toBeDisabled()
    expect(railResult).toBeDisabled()

    // ①需求参数已解锁可回看
    fireEvent.click(screen.getByRole('button', { name: /需求与参数/ }))
    expect(await screen.findByRole('heading', { name: '需求与参数' })).toBeTruthy()
  })

  it('②情报步骤展示 token 用量条与因子面板占位，受保护段只读折叠', async () => {
    vi.mocked(api.getStrategyConversation).mockResolvedValue(makeDetail([makeAssistant()]))
    renderPage('/strategy/prompt?id=7&step=intel')

    expect(await screen.findByText('情报包 token 用量')).toBeTruthy()
    expect(screen.getByText('1200 / 6000')).toBeTruthy()
    expect(screen.getByText('情报包 / 任务卡 / 纪律条款（受保护，只读）')).toBeTruthy()
    expect(screen.getByText('相关新闻')).toBeTruthy()
  })

  it('③确认发送：只有交易参数/用户需求可编辑，确认后跳到④并调用 confirm 接口', async () => {
    vi.mocked(api.getStrategyConversation).mockResolvedValue(makeDetail([makeAssistant()]))
    renderPage()

    const requirementBox = await screen.findByPlaceholderText(/写明你要的策略逻辑/)
    fireEvent.change(requirementBox, { target: { value: '改成10/30均线' } })

    fireEvent.click(screen.getByRole('button', { name: '确认并生成' }))
    await waitFor(() => expect(api.confirmStrategyDraft).toHaveBeenCalledTimes(1))
    const [, messageId, editedPrompt] = vi.mocked(api.confirmStrategyDraft).mock.calls[0]
    expect(messageId).toBe(2)
    expect(editedPrompt).toContain('改成10/30均线')
    expect(editedPrompt).toContain(EDITABLE_START)

    expect(await screen.findByRole('heading', { name: '生成与回测' })).toBeTruthy()
  })

  it('生成中：默认落在④，⑤仍锁定，显示阶段/计时/日志尾部', async () => {
    vi.mocked(api.getStrategyConversation).mockResolvedValue(
      makeDetail([makeAssistant({
        status: 'running',
        final_sent_prompt: SYSTEM_DRAFT,
        stage: 'backtest_checking',
        stage_updated_at: new Date(Date.now() - 4000).toISOString(),
        run_started_at: new Date(Date.now() - 42_000).toISOString(),
        log_tail: 'starting trade\nSTATISTICS:: Total Orders 3',
      })]),
    )
    renderPage()

    expect(await screen.findByRole('heading', { name: '生成与回测' })).toBeTruthy()
    expect(screen.getByText(/正在生成策略并运行回测/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /结果报告/ })).toBeDisabled()
    // B1：真实阶段同时出现在页头徽章与阶段行。
    expect((await screen.findAllByText(/检查回测中/)).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText(/STATISTICS:: Total Orders 3/)).toBeTruthy()
    expect(screen.getByText(/上限 16:00/)).toBeTruthy()
    expect(screen.getByRole('button', { name: '放弃等待' })).toBeTruthy()
  })

  it('放弃等待：二次确认后调 cancel-wait，返回后呈现已放弃面板', async () => {
    const runningDetail = makeDetail([makeAssistant({
      status: 'running',
      final_sent_prompt: SYSTEM_DRAFT,
      stage: 'generating',
      run_started_at: new Date(Date.now() - 5000).toISOString(),
    })])
    const cancelledDetail = makeDetail([makeAssistant({
      status: 'cancelled',
      final_sent_prompt: SYSTEM_DRAFT,
      stage: 'cancelled',
      content: '已放弃等待：对端仍会跑完本轮生成，但结果不再回收。',
      public_error_message: '已放弃等待：对端仍会跑完本轮生成，但结果不再回收。',
    })])
    vi.mocked(api.getStrategyConversation)
      .mockResolvedValueOnce(runningDetail)
      .mockResolvedValueOnce(cancelledDetail)
      .mockResolvedValue(cancelledDetail)
    vi.mocked(api.cancelWaitStrategyGeneration).mockResolvedValue({
      status: 'cancelled',
      note: '对端仍会跑完本轮生成，但结果不再回收。',
    })
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: '放弃等待' }))
    // 明确告知：协议没有取消命令，对端照样跑完。
    expect(screen.getByText(/对端仍会跑完本轮生成，但结果不再回收/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '确认放弃' }))

    await waitFor(() =>
      expect(api.cancelWaitStrategyGeneration).toHaveBeenCalledWith(7, 2),
    )
    // 徽章与失败面板标题都会显示「已放弃等待」。
    expect((await screen.findAllByText('已放弃等待')).length).toBeGreaterThanOrEqual(2)
  })

  it('超过 16 分钟轮询上限：停止自动刷新并显示超时态与手动操作', async () => {
    vi.mocked(api.getStrategyConversation).mockResolvedValue(
      makeDetail([makeAssistant({
        status: 'running',
        final_sent_prompt: SYSTEM_DRAFT,
        stage: 'backtest_checking',
        run_started_at: new Date(Date.now() - 17 * 60_000).toISOString(),
      })]),
    )
    renderPage()

    expect(await screen.findByText(/已等待超过 16 分钟，已停止自动刷新/)).toBeTruthy()
    expect(screen.getByRole('button', { name: '刷新状态' })).toBeTruthy()
    // 超时态不再显示「放弃等待」入口。
    expect(screen.queryByRole('button', { name: '放弃等待' })).toBeNull()
  })

  it('有版本：默认落在⑤结果报告，显示验收徽章与指标', async () => {
    const version: StrategyVersion = {
      id: 11,
      source_message_id: 2,
      local_version_no: 1,
      name: 'v1',
      description: '均线策略',
      code: 'def initialize(ctx):\n    pass\n',
      backtest_passed: true,
      backtest_exit_code: '0',
      backtest_summary: 'STATISTICS: ...',
      backtest_metrics_json: [{ label: 'Total Orders', value: '29' }],
      created_at: '2026-10-30T14:22:00+08:00',
    }
    vi.mocked(api.getStrategyConversation).mockResolvedValue(
      makeDetail([makeAssistant({
        status: 'succeeded',
        final_sent_prompt: SYSTEM_DRAFT,
        validation_json: {
          verdict: 'passed', passed: true, retryable: false, steps: [],
          trade_count: 29, raw_trade_line: null, symbol_whitelisted: true, reason: 'ok',
        },
      })], [version]),
    )
    renderPage()

    expect(await screen.findByText('验收通过')).toBeTruthy()
    expect(screen.getByText('总订单数')).toBeTruthy()
  })

  it('结果报告：核心大字进英雄区，风险指标除式爆炸显⚠且不洗绿', async () => {
    const version: StrategyVersion = {
      id: 12,
      source_message_id: 2,
      local_version_no: 1,
      name: 'v1',
      description: '',
      code: 'def initialize(ctx):\n    pass\n',
      backtest_passed: false,
      backtest_exit_code: '0',
      backtest_summary: 'STATISTICS: ...',
      backtest_metrics_json: [
        { key: 'total_orders', label: 'Total Orders', value: '29', tier: 'core', numeric: 29 },
        { key: 'compounding_annual_return', label: 'Compounding Annual Return', value: '0.000%', tier: 'core', numeric: 0 },
        { key: 'drawdown', label: 'Drawdown', value: '0.000%', tier: 'core', numeric: 0 },
        { key: 'win_rate', label: 'Win Rate', value: '0%', tier: 'core', numeric: 0 },
        { key: 'net_profit', label: 'Net Profit', value: '0.000%', tier: 'core', numeric: 0 },
        {
          key: 'sharpe_ratio', label: 'Sharpe Ratio', value: '-42182.563', tier: 'risk',
          numeric: -42182.563, anomaly: '数值 -42182.563 绝对值超过 10，疑似除式爆炸，不能据此评价风险收益',
        },
        { key: 'annual_standard_deviation', label: 'Annual Standard Deviation', value: '0', tier: 'risk', numeric: 0 },
        { key: 'order_list_hash', label: 'OrderListHash', value: '83ab', tier: 'other', numeric: null },
      ],
      created_at: '2026-10-30T14:22:00+08:00',
    }
    vi.mocked(api.getStrategyConversation).mockResolvedValue(
      makeDetail([makeAssistant({
        status: 'succeeded',
        final_sent_prompt: SYSTEM_DRAFT,
        validation_json: {
          verdict: 'backtest_failed', passed: false, retryable: true, steps: [],
          trade_count: 29, raw_trade_line: null, symbol_whitelisted: true, reason: 'ghost orders',
        },
      })], [version]),
    )
    renderPage()

    // 英雄区：5 个核心大字，成交笔数与缺失占位都在
    expect(await screen.findByText('29')).toBeTruthy()
    expect(screen.getByText('净利润')).toBeTruthy()
    // 异常横幅：显式原因
    expect(screen.getByText(/⚠ 计算异常（1）/)).toBeTruthy()
    expect(screen.getByText(/绝对值超过 10/)).toBeTruthy()
    // 风险分层存在；异常卡是警告色，不是涨跌色（不洗绿）
    expect(screen.getByText('风险', { selector: 'h4' })).toBeTruthy()
    const anomalyCard = document.querySelector('.sw-metric--anomaly')
    expect(anomalyCard).toBeTruthy()
    expect(anomalyCard?.querySelector('.sw-metric-anomaly')?.textContent).toContain('计算异常')
    // 其他指标默认折叠（details 不带 open）
    const otherFold = screen.getByText(/其他指标（1 项）/).closest('details')
    expect(otherFold).toBeTruthy()
    expect(otherFold?.open).toBe(false)
  })

  it('旧 ?view=code 深链映射到⑤结果步骤', async () => {
    const version: StrategyVersion = {
      id: 11, source_message_id: 2, local_version_no: 2, name: 'v2', description: '',
      code: 'x = 1', backtest_passed: false, backtest_exit_code: '1',
      backtest_summary: '', backtest_metrics_json: [],
      created_at: '2026-10-30T14:22:00+08:00',
    }
    vi.mocked(api.getStrategyConversation).mockResolvedValue(
      makeDetail([makeAssistant({ status: 'failed', final_sent_prompt: SYSTEM_DRAFT })], [version]),
    )
    renderPage('/strategy/prompt?id=7&view=code')

    expect(await screen.findByRole('heading', { name: '结果报告' })).toBeTruthy()
  })

  it('空会话自动生成首轮草稿后进入②情报步骤', async () => {
    vi.mocked(api.getStrategyConversation).mockResolvedValue(makeDetail([], []))
    vi.mocked(api.createStrategyDraft).mockResolvedValue({
      user_message_id: 1,
      assistant_message_id: 2,
      status: 'pending_confirmation',
      system_draft_prompt: SYSTEM_DRAFT,
      context: { instrument_code: 'FCT_T_MAIN' },
    })
    renderPage()

    await waitFor(() => expect(api.createStrategyDraft).toHaveBeenCalledTimes(1))
    expect(await screen.findByRole('heading', { name: '情报与因子' })).toBeTruthy()
  })
})
