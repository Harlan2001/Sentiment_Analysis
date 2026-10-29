import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type Props = {
  /** 对端返回的原始 description（Markdown） */
  markdown: string
}

type Section = { title: string; lines: string[] }
type Parsed = {
  sections: Section[]
  /** 没有任何可识别结构时为 false，前端降级为 Markdown 视图 */
  structured: boolean
}

const HEADING = /^\s*#{1,6}\s*(.+?)\s*$/
const BULLET = /^\s*(?:[-*•]|\d+[.、)])\s+/

/** 这些标题与页面模块名重复，渲染时跳过 */
const REDUNDANT_TITLES = new Set(['策略概要', '策略概述', '策略说明', '概要', '总结', '策略总结'])

/**
 * 把模型给的 Markdown 概要切成「小节 + 条目」。
 *
 * 对端输出的是自由 Markdown，标题层级和字段名每次都可能不同，所以这里只做
 * 最小结构化：按标题切小节，小节内的列表项保留为条目，正文段落保留为条目。
 * 不能识别的部分原样留在所属小节里，绝不丢弃——用户要能看到模型原话。
 */
function parseSections(markdown: string): Parsed {
  const sections: Section[] = []
  let current: Section | null = null

  for (const raw of markdown.split('\n')) {
    const line = raw.trimEnd()
    if (!line.trim()) continue

    const heading = line.match(HEADING)
    if (heading) {
      const title = heading[1].replace(/\*\*/g, '').trim()
      // 与页面模块名重复的标题不单独成节，其内容并入相邻小节
      if (REDUNDANT_TITLES.has(title)) {
        current = null
        continue
      }
      current = { title, lines: [] }
      sections.push(current)
      continue
    }

    // 加粗整行但没有列表符号，也当作小标题（模型常用 **标的**：xxx 这种写法）
    const bold = line.match(/^\*\*(.+?)\*\*\s*[：:]?\s*(.*)$/)
    if (bold && !BULLET.test(line)) {
      const title = bold[1].trim()
      const rest = bold[2].trim()
      if (REDUNDANT_TITLES.has(title)) {
        current = null
        if (rest) {
          current = { title: '', lines: [rest] }
          sections.push(current)
        }
        continue
      }
      current = { title, lines: rest ? [rest] : [] }
      sections.push(current)
      continue
    }

    const bullet = line.match(BULLET)
    if (bullet) {
      const content = line.replace(BULLET, '').trim()
      if (current) current.lines.push(content)
      else {
        current = { title: '', lines: [content] }
        sections.push(current)
      }
      continue
    }

    if (current) current.lines.push(line.trim())
    else {
      current = { title: '', lines: [line.trim()] }
      sections.push(current)
    }
  }

  // 去掉只有标题没有内容的空小节、以及完全空白的结果
  const cleaned = sections.filter((s) => s.title || s.lines.length > 0)
  const hasTitled = cleaned.some((s) => Boolean(s.title))
  return { sections: cleaned, structured: hasTitled }
}

/** 行内 Markdown 记为纯文本，用于结构化视图里不显示 ** 之类的符号 */
function stripInline(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .trim()
}

/** 「开仓：xxx」这类行拆成 标签 + 内容，渲染成键值对更易扫读 */
function splitLabel(text: string): { label: string; value: string } | null {
  const match = text.match(/^([^：:]{1,10})[：:]\s*(.+)$/)
  if (!match) return null
  return { label: match[1].trim(), value: match[2].trim() }
}

/**
 * 策略概要的结构化展示。
 *
 * 只提供结构化视图：对端返回的是自由 Markdown，直接展示原文既难读也难比对，
 * 这里统一拆成「小节 + 键值行」。解析不出结构时降级为 Markdown 渲染兜底，
 * 保证内容不会丢失。
 */
export function StrategySummary({ markdown }: Props) {
  const parsed = useMemo(() => parseSections(markdown || ''), [markdown])

  if (!markdown.trim()) {
    return <p className="strategy-empty-state">本次生成未返回策略概要。</p>
  }

  if (!parsed.structured) {
    return (
      <div className="sf-summary-markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
      </div>
    )
  }

  return (
    <div className="sf-summary">
      {parsed.sections.map((section, index) => {
        const items = section.lines.map(stripInline).filter(Boolean)
        // 条目里能拆出「标签：内容」的，渲染成键值行；拆不出的按普通条目
        const keyed = items.map(splitLabel)
        const allKeyed = keyed.length > 0 && keyed.every(Boolean)
        return (
          <section className="sf-summary-section" key={`${section.title}-${index}`}>
            {section.title && <h4>{section.title}</h4>}
            {allKeyed ? (
              <dl className="sf-summary-kv">
                {keyed.map((item, i) => (
                  <div key={i}>
                    <dt>{item!.label}</dt>
                    <dd>{item!.value}</dd>
                  </div>
                ))}
              </dl>
            ) : items.length === 1 ? (
              <p>{items[0]}</p>
            ) : (
              <ul>
                {items.map((line, i) => {
                  const pair = keyed[i]
                  return (
                    <li key={i}>
                      {pair ? (
                        <>
                          <b>{pair.label}</b>
                          <span>{pair.value}</span>
                        </>
                      ) : (
                        line
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </section>
        )
      })}
    </div>
  )
}