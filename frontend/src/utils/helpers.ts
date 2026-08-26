// 本地存储工具
export const storage = {
  set: (key: string, value: any): void => {
    try {
      localStorage.setItem(key, JSON.stringify(value))
    } catch {
      // 静默失败
    }
  },

  get: <T>(key: string, defaultValue?: T): T | null => {
    try {
      const item = localStorage.getItem(key)
      return item ? JSON.parse(item) : defaultValue || null
    } catch {
      return defaultValue || null
    }
  },

  remove: (key: string): void => {
    try {
      localStorage.removeItem(key)
    } catch {
      // 静默失败
    }
  },

  clear: (): void => {
    try {
      localStorage.clear()
    } catch {
      // 静默失败
    }
  },
}

/**
 * 生成 UUID v4。开发与生产统一只用这一条实现。
 * 基于 crypto.getRandomValues —— 与 crypto.randomUUID 同源（同一个安全随机源），
 * 且不受 HTTPS / localhost 限制，明文 HTTP 的内网部署同样可用。
 */
export function uuid(): string {
  const bytes = new Uint8Array(16)
  if (typeof crypto === 'undefined' || !crypto.getRandomValues) {
    // 极端环境兜底（无密码学随机源的旧 WebView / 非浏览器上下文）：
    // 用 Math.random 拼出合法 UUID，保证任何环境都不抛错
    for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256)
  } else {
    crypto.getRandomValues(bytes)
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40 // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80 // variant 10
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}