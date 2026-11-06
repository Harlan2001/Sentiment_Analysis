/**
 * [TRADING_PARAMETERS] 块的结构化读写（S2-2）。
 *
 * 历史上前端硬编码过一组“假默认参数”，草稿缺块时也照显不误，让用户以为
 * 这些值被后端采纳。现在缺块一律返回 null，由界面显示“草稿生成后回填”。
 */
import { parsePromptSections, patchSection } from './promptSections'

export type ParameterRow = { label: string; value: string }

/** 从当前草稿解析参数行；草稿或块不存在时返回 null（不造默认值）。 */
export function parseParameterRows(prompt: string): ParameterRow[] | null {
  if (!prompt) return null
  const block = parsePromptSections(prompt).sections.tradingParameters
  if (block === null) return null
  const rows: ParameterRow[] = []
  for (const line of block.split('\n')) {
    const trimmed = line.replace(/^\s*-\s*/, '')
    if (!trimmed) continue
    const separator = trimmed.indexOf('：')
    if (separator < 0) continue
    const label = trimmed.slice(0, separator).trim()
    const value = trimmed.slice(separator + 1).trim()
    if (label) rows.push({ label, value })
  }
  return rows
}

/** 把结构化参数行写回草稿的 [TRADING_PARAMETERS] 块，其他块不动。 */
export function patchParameterRows(prompt: string, rows: ParameterRow[]): string {
  const body = rows.map(({ label, value }) => `- ${label}：${value.trim()}`).join('\n')
  return patchSection(prompt, 'tradingParameters', body)
}
