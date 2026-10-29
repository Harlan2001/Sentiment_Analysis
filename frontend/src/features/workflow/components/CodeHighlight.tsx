import { useMemo } from 'react'

type Props = {
  code: string
}

type Token = { text: string; kind: TokenKind }
type TokenKind = 'plain' | 'comment' | 'string' | 'keyword' | 'number' | 'decorator' | 'builtin'

// Python 关键字。只做词法着色，不追求语法完整性——目的是让一段 500 行的策略代码
// 有可读的层次感，而不是做 IDE。
const KEYWORDS = new Set([
  'def', 'class', 'return', 'if', 'elif', 'else', 'for', 'while', 'in', 'not',
  'and', 'or', 'is', 'None', 'True', 'False', 'import', 'from', 'as', 'try',
  'except', 'finally', 'raise', 'with', 'pass', 'break', 'continue', 'lambda',
  'yield', 'global', 'nonlocal', 'assert', 'del', 'self',
])

const BUILTINS = new Set([
  'print', 'len', 'range', 'float', 'int', 'str', 'list', 'dict', 'set', 'tuple',
  'sum', 'min', 'max', 'abs', 'round', 'enumerate', 'zip', 'sorted', 'isinstance',
])

/**
 * 极简 Python 词法着色。
 *
 * 顺序很重要：注释和字符串必须先吃掉，否则字符串里的 `#` 会被误判为注释、
 * 关键字会被重复匹配。
 */
function tokenizePython(source: string): Token[][] {
  return source.split('\n').map((line) => tokenizeLine(line))
}

function tokenizeLine(line: string): Token[] {
  const tokens: Token[] = []
  let index = 0
  let plainStart = 0

  const pushPlain = (end: number) => {
    if (end > plainStart) {
      tokens.push({ text: line.slice(plainStart, end), kind: 'plain' })
    }
  }

  while (index < line.length) {
    const char = line[index]

    // 注释：到行尾
    if (char === '#') {
      pushPlain(index)
      tokens.push({ text: line.slice(index), kind: 'comment' })
      return tokens
    }

    // 字符串（含三引号）：不做跨行解析，单行内闭合即可
    if (char === '"' || char === "'") {
      const quote = char
      const triple = line.slice(index, index + 3)
      if (triple === quote.repeat(3)) {
        pushPlain(index)
        const end = line.indexOf(quote.repeat(3), index + 3)
        const stop = end === -1 ? line.length : end + 3
        tokens.push({ text: line.slice(index, stop), kind: 'string' })
        index = stop
        plainStart = index
        continue
      }
      pushPlain(index)
      let cursor = index + 1
      while (cursor < line.length) {
        if (line[cursor] === '\\') {
          cursor += 2
          continue
        }
        if (line[cursor] === quote) {
          cursor += 1
          break
        }
        cursor += 1
      }
      tokens.push({ text: line.slice(index, cursor), kind: 'string' })
      index = cursor
      plainStart = index
      continue
    }

    // 装饰器
    if (char === '@' && /[A-Za-z_]/.test(line[index + 1] || '')) {
      pushPlain(index)
      let cursor = index + 1
      while (cursor < line.length && /[\w.]/.test(line[cursor])) cursor += 1
      tokens.push({ text: line.slice(index, cursor), kind: 'decorator' })
      index = cursor
      plainStart = index
      continue
    }

    // 数字
    if (/\d/.test(char) && !/[\w]/.test(line[index - 1] || '')) {
      pushPlain(index)
      let cursor = index
      while (cursor < line.length && /[\d._eExXa-fA-F]/.test(line[cursor])) cursor += 1
      tokens.push({ text: line.slice(index, cursor), kind: 'number' })
      index = cursor
      plainStart = index
      continue
    }

    // 标识符：关键字 / 内置函数 / 普通名字
    if (/[A-Za-z_]/.test(char)) {
      pushPlain(index)
      let cursor = index
      while (cursor < line.length && /[\w]/.test(line[cursor])) cursor += 1
      const word = line.slice(index, cursor)
      const kind: TokenKind = KEYWORDS.has(word)
        ? 'keyword'
        : BUILTINS.has(word)
          ? 'builtin'
          : 'plain'
      tokens.push({ text: word, kind })
      index = cursor
      plainStart = index
      continue
    }

    index += 1
  }

  pushPlain(line.length)
  return tokens
}

/**
 * 只读代码块，带行号与 Python 词法着色。
 *
 * 没有引入 highlight.js / shiki：本项目只需要 Python 一种语言的粗粒度着色，
 * 引一个 200KB 的库不划算。
 */
export function CodeHighlight({ code }: Props) {
  const lines = useMemo(() => tokenizePython(code || ''), [code])

  return (
    <div className="sf-code">
      <pre className="sf-code-pre">
        {lines.map((tokens, lineNo) => (
          <div className="sf-code-line" key={lineNo}>
            <span className="sf-code-ln">{lineNo + 1}</span>
            <code className="sf-code-content">
              {tokens.map((token, i) =>
                token.kind === 'plain' ? (
                  <span key={i}>{token.text}</span>
                ) : (
                  <span key={i} className={`sf-tk sf-tk-${token.kind}`}>
                    {token.text}
                  </span>
                ),
              )}
              {'\n'}
            </code>
          </div>
        ))}
      </pre>
    </div>
  )
}