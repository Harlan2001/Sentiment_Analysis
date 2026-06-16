import { create } from 'zustand'

interface AppState {
  // 当前页面状态
  currentPage: string
  setCurrentPage: (page: string) => void
  
  // 全局加载状态
  isLoading: boolean
  setIsLoading: (loading: boolean) => void
  
  // 主题设置
  theme: 'dark'
  
  // 错误状态
  error: string | null
  setError: (error: string | null) => void
  
  // 新闻相关状态
  selectedNewsId: number | null
  setSelectedNewsId: (id: number | null) => void
  
  // 因子相关状态
  selectedFactorCode: string | null
  setSelectedFactorCode: (code: string | null) => void
  
  // 聊天相关状态
  isChatOpen: boolean
  setIsChatOpen: (open: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  // 初始状态
  currentPage: 'news',
  isLoading: false,
  theme: 'dark',
  error: null,
  selectedNewsId: null,
  selectedFactorCode: null,
  isChatOpen: false,
  
  // Action creators
  setCurrentPage: (page) => set({ currentPage: page }),
  setIsLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setSelectedNewsId: (id) => set({ selectedNewsId: id }),
  setSelectedFactorCode: (code) => set({ selectedFactorCode: code }),
  setIsChatOpen: (open) => set({ isChatOpen: open }),
}))

// 类型导出
export type { AppState }