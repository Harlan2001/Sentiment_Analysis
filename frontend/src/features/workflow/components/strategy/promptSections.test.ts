import { describe, expect, it } from 'vitest'
import {
  EDITABLE_END,
  EDITABLE_START,
  isSectionDirty,
  parsePromptSections,
  patchSection,
} from './promptSections'

const DRAFT = `【情报包受保护前缀】任务卡、市场块、纪律……
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
受保护后缀：审计与输出契约。`

describe('promptSections 提示词分段（S2-2）', () => {
  it('切出保护段与三个可编辑分段', () => {
    const parsed = parsePromptSections(DRAFT)
    expect(parsed.supported).toBe(true)
    expect(parsed.protectedPrefix).toContain('情报包受保护前缀')
    expect(parsed.protectedSuffix).toContain('审计与输出契约')
    expect(parsed.sections.tradingParameters).toContain('开仓规则：金叉')
    expect(parsed.sections.instrument).toContain('FCT_T_MAIN')
    expect(parsed.sections.requirement).toBe('做一个5/20双均线策略')
  })

  it('修改需求只替换内层块，保护段与标记原样保留', () => {
    const next = patchSection(DRAFT, 'requirement', '改成10/30均线，因子同向才开仓')
    const parsed = parsePromptSections(next)
    expect(parsed.sections.requirement).toBe('改成10/30均线，因子同向才开仓')
    expect(parsed.protectedPrefix).toContain('情报包受保护前缀')
    expect(parsed.protectedSuffix).toContain('审计与输出契约')
    expect(parsed.sections.tradingParameters).toContain('开仓规则：金叉')
    expect(next).toContain(EDITABLE_START)
    expect(next).toContain(EDITABLE_END)
    expect(next).toContain('[STRATEGY_REQUIREMENT]')
  })

  it('修改交易参数保留其他块', () => {
    const next = patchSection(DRAFT, 'tradingParameters', '- 开仓规则：死叉\n- 止损：2.0%')
    const parsed = parsePromptSections(next)
    expect(parsed.sections.tradingParameters).toBe('- 开仓规则：死叉\n- 止损：2.0%')
    expect(parsed.sections.requirement).toBe('做一个5/20双均线策略')
    expect(parsed.sections.instrument).toContain('bar')
  })

  it('脏检测：只有改动段报脏', () => {
    const changed = patchSection(DRAFT, 'requirement', '新需求')
    expect(isSectionDirty(changed, DRAFT, 'requirement')).toBe(true)
    expect(isSectionDirty(changed, DRAFT, 'tradingParameters')).toBe(false)
    expect(isSectionDirty(changed, DRAFT, 'instrument')).toBe(false)
  })

  it('无标记旧草稿：整段作为受保护只读，不支持 patch', () => {
    const legacy = '旧版自由文本提示词，没有任何分段标记'
    const parsed = parsePromptSections(legacy)
    expect(parsed.supported).toBe(false)
    expect(parsed.protectedPrefix).toBe(legacy)
    expect(patchSection(legacy, 'requirement', 'x')).toBe(legacy)
  })
})
