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