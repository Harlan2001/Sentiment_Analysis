import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/strategy', () => ({
  getStrategyConversation: vi.fn(),
  getSupportedInstruments: vi.fn(),
  createStrategyDraft: vi.fn(),
  confirmStrategyDraft: vi.fn(),
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

  it('生成中：默认落在④，⑤仍锁定，显示进度与计时', async () => {
    vi.mocked(api.getStrategyConversation).mockResolvedValue(
      makeDetail([makeAssistant({
        status: 'running',
        final_sent_prompt: SYSTEM_DRAFT,
      })]),
    )
    renderPage()

    expect(await screen.findByRole('heading', { name: '生成与回测' })).toBeTruthy()
    expect(screen.getByText(/正在生成策略并运行回测/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /结果报告/ })).toBeDisabled()
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
