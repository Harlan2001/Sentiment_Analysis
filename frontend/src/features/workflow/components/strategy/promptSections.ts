/**
 * 提示词分段（S2-2）。后端把可编辑区夹在 [USER_EDITABLE_REQUIREMENT]
 * 标记之间（见 backend/strategy/dream_strategy_prompt.py），标记外的情报/
 * 任务卡/纪律段落受保护，浏览器改了会被 apply_user_edited_requirement 拒绝。
 *
 * 前端只切分、不重新拼装保护段；patch 时只替换三个内层块，标记与受保护
 * 文本原样保留。
 */

export const EDITABLE_START = '[USER_EDITABLE_REQUIREMENT]'
export const EDITABLE_END = '[/USER_EDITABLE_REQUIREMENT]'

export type SectionKey = 'tradingParameters' | 'instrument' | 'requirement'

export const SECTION_LABELS: Record<SectionKey, string> = {
  tradingParameters: '交易参数',
  instrument: '标的与模式',
  requirement: '用户需求',
}

const BLOCK_MARKERS: Record<SectionKey, [string, string]> = {
  tradingParameters: ['[TRADING_PARAMETERS]', '[/TRADING_PARAMETERS]'],
  instrument: ['[INSTRUMENT]', '[/INSTRUMENT]'],
  requirement: ['[STRATEGY_REQUIREMENT]', '[/STRATEGY_REQUIREMENT]'],
}

export type PromptSections = {
  /** 草稿是否含后端约定的可编辑区；不含则整段只读展示 */
  supported: boolean
  protectedPrefix: string
  protectedSuffix: string
  sections: Record<SectionKey, string | null>
}

function extractBlock(text: string, [start, end]: [string, string]): string | null {
  const begin = text.indexOf(start)
  const finish = text.indexOf(end)
  if (begin < 0 || finish < 0 || finish < begin) return null
  const inner = text.slice(begin + start.length, finish)
  return inner.replace(/^\r?\n/, '').replace(/\r?\n$/, '')
}

export function parsePromptSections(prompt: string): PromptSections {
  const startIndex = prompt.indexOf(EDITABLE_START)
  const endIndex = prompt.indexOf(EDITABLE_END)
  const supported = startIndex >= 0 && endIndex > startIndex
  if (!supported) {
    return {
      supported: false,
      protectedPrefix: prompt,
      protectedSuffix: '',
      sections: { tradingParameters: null, instrument: null, requirement: null },
    }
  }
  const editable = prompt.slice(startIndex + EDITABLE_START.length, endIndex)
  return {
    supported: true,
    protectedPrefix: prompt.slice(0, startIndex).trim(),
    protectedSuffix: prompt.slice(endIndex + EDITABLE_END.length).trim(),
    sections: {
      tradingParameters: extractBlock(editable, BLOCK_MARKERS.tradingParameters),
      instrument: extractBlock(editable, BLOCK_MARKERS.instrument),
      requirement: extractBlock(editable, BLOCK_MARKERS.requirement),
    },
  }
}

/** 替换某一分段内容；标记缺失时原样返回（调用方应让该段只读）。 */
export function patchSection(prompt: string, key: SectionKey, value: string): string {
  const [start, end] = BLOCK_MARKERS[key]
  const begin = prompt.indexOf(start)
  const finish = begin >= 0 ? prompt.indexOf(end, begin) : -1
  if (begin < 0 || finish < 0) return prompt
  const next = `${start}\n${value.replace(/\s+$/, '')}\n${end}`
  return prompt.slice(0, begin) + next + prompt.slice(finish + end.length)
}

/** 与系统草稿相比，某段是否被用户改过（用于段首色条）。 */
export function isSectionDirty(
  draft: string,
  baseline: string,
  key: SectionKey,
): boolean {
  const current = parsePromptSections(draft).sections[key]
  const original = parsePromptSections(baseline).sections[key]
  if (current === null || original === null) return false
  return current.trim() !== original.trim()
}
