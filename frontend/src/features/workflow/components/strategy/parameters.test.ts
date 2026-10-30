import { describe, expect, it } from 'vitest'
import { EDITABLE_END, EDITABLE_START } from './promptSections'
import { parseParameterRows, patchParameterRows } from './parameters'

const DRAFT = `${EDITABLE_START}
[TRADING_PARAMETERS]
- 开仓规则：金叉
- 单笔仓位：20%资金
[/TRADING_PARAMETERS]

[STRATEGY_REQUIREMENT]
双均线
[/STRATEGY_REQUIREMENT]
${EDITABLE_END}`

describe('parameters 交易参数读写（S2-2）', () => {
  it('解析参数行（不再造假默认值）', () => {
    expect(parseParameterRows(DRAFT)).toEqual([
      { label: '开仓规则', value: '金叉' },
      { label: '单笔仓位', value: '20%资金' },
    ])
  })

  it('缺块/空草稿返回 null，由界面显示“草稿生成后回填”', () => {
    expect(parseParameterRows('')).toBeNull()
    expect(parseParameterRows('旧版自由文本')).toBeNull()
  })

  it('写回只动参数块，需求块与标记保留', () => {
    const next = patchParameterRows(DRAFT, [
      { label: '开仓规则', value: '死叉' },
      { label: '单笔仓位', value: '10%资金' },
    ])
    expect(parseParameterRows(next)).toEqual([
      { label: '开仓规则', value: '死叉' },
      { label: '单笔仓位', value: '10%资金' },
    ])
    expect(next).toContain('双均线')
    expect(next).toContain(EDITABLE_START)
    expect(next).toContain(EDITABLE_END)
  })
})
