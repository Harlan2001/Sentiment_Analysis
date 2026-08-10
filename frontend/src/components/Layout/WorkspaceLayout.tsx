import React, { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

/**
 * 新工作台「壳」
 * - 左侧工具栏 240px：新建 / computer / 工件 / 自定义 + 项目 / 绘画 分组
 * - 顶栏 920×60：项目名 + 搜索 + 分享
 * - 板块标签条：市场 / 收益 / 预测 / 关注列表 / 投资组合 / 工作流
 * - 内容区：<Outlet/> 渲染当前板块页
 */

interface IconProps {
  className?: string
}

const PlusIcon: React.FC<IconProps> = ({ className = 'w-3.5 h-3.5' }) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2.2} viewBox="0 0 24 24">
    <path strokeLinecap="round" d="M12 5v14M5 12h14" />
  </svg>
)

const ChevronIcon: React.FC<IconProps> = ({ className = 'w-3.5 h-3.5' }) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M10 6l6 6-6 6" />
  </svg>
)

const ComputerIcon: React.FC<IconProps> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <rect x="2" y="4" width="20" height="13" rx="2" />
    <path strokeLinecap="round" d="M8 21h8m-4-4v4" />
  </svg>
)

const ArtifactIcon: React.FC<IconProps> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" d="M12 3v18M3 12h18" />
    <circle cx="12" cy="12" r="9.5" />
  </svg>
)

const CustomIcon: React.FC<IconProps> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M12 2l2.2 6.6L21 11l-6.8 2.4L12 20l-2.2-6.6L3 11l6.8-2.4L12 2z"
    />
  </svg>
)

const SearchIcon: React.FC<IconProps> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <circle cx="11" cy="11" r="8" />
    <path strokeLinecap="round" d="M21 21l-4.35-4.35" />
  </svg>
)

const ShareIcon: React.FC<IconProps> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <circle cx="18" cy="5" r="3" />
    <circle cx="6" cy="12" r="3" />
    <circle cx="18" cy="19" r="3" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" />
  </svg>
)

const SettingsIcon: React.FC<IconProps> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <circle cx="12" cy="8" r="4" />
    <path strokeLinecap="round" d="M4 21v-1a4 4 0 014-4h8a4 4 0 014 4v1" />
  </svg>
)

const HelpIcon: React.FC<IconProps> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M22 12h-4l-3 9L9 3l-3 9H2" />
  </svg>
)

/** 板块标签配置：标签 → 路由 */
const SECTIONS = [
  { name: '市场', to: '/market', emoji: '📈' },
  { name: '收益', to: '/returns', emoji: '💰' },
  { name: '预测', to: '/forecast', emoji: '✨' },
  { name: '关注列表', to: '/watchlist', emoji: '⭐' },
  { name: '投资组合', to: '/portfolio', emoji: '💼' },
  { name: '工作流', to: '/workflow', emoji: '⚙️' },
]

/** 可展开分组的假数据 */
const PROJECTS = [
  { name: '国债策略分析', icon: '📊' },
  { name: '信用债研究', icon: '📈' },
  { name: '组合回测', icon: '🛡️' },
]
const DRAWINGS = [
  { name: '收益率曲线图', icon: '🖼️' },
  { name: '组合构成示意', icon: '🎨' },
]

const WorkspaceLayout: React.FC = () => {
  const { displayName, username, authEnabled, logout } = useAuth()
  const [projectOpen, setProjectOpen] = useState(true)
  const [drawOpen, setDrawOpen] = useState(false)

  return (
    <div className="flex h-screen bg-black text-white">
      {/* ===== 左侧工具栏 240px ===== */}
      <aside className="w-[240px] flex-shrink-0 bg-[#111111] border-r border-gray-800 flex flex-col p-3">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-2 pb-4">
          <div className="w-7 h-7 bg-white rounded-lg flex items-center justify-center text-sm font-bold">📊</div>
          <div>
            <div className="text-sm font-semibold leading-tight">债券信号</div>
            <div className="text-[10px] text-gray-500 leading-tight">BondSense</div>
          </div>
        </div>

        {/* 顶部四个工具按钮 */}
        <div className="flex flex-col gap-1.5 pb-3 border-b border-gray-800">
          <button
            data-track="shell-new"
            className="flex items-center gap-2 w-full px-3 py-2 bg-white text-black rounded-lg text-[13px] font-semibold hover:opacity-85 transition-opacity"
          >
            <PlusIcon />
            新建
          </button>
          <div className="flex gap-1.5">
            <button
              data-track="shell-computer"
              className="flex-1 flex flex-col items-center gap-1 py-2 rounded-lg text-gray-400 hover:bg-gray-800/60 hover:text-white transition-colors text-[10px]"
            >
              <ComputerIcon />
              computer
            </button>
            <button
              data-track="shell-artifact"
              className="flex-1 flex flex-col items-center gap-1 py-2 rounded-lg text-gray-400 hover:bg-gray-800/60 hover:text-white transition-colors text-[10px]"
            >
              <ArtifactIcon />
              工件
            </button>
            <button
              data-track="shell-custom"
              className="flex-1 flex flex-col items-center gap-1 py-2 rounded-lg text-gray-400 hover:bg-gray-800/60 hover:text-white transition-colors text-[10px]"
            >
              <CustomIcon />
              自定义
            </button>
          </div>
        </div>

        {/* 项目 分组 */}
        <div className="flex items-center gap-1 pt-4 pb-1 px-1">
          <span className="flex-1 text-xs font-semibold text-gray-300">项目</span>
          <span className="text-[10px] text-gray-500">{PROJECTS.length}</span>
          <button
            data-track="shell-project-add"
            className="w-5 h-5 flex items-center justify-center rounded text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
          >
            <PlusIcon className="w-3.5 h-3.5" />
          </button>
          <button
            data-track="shell-project-toggle"
            onClick={() => setProjectOpen(!projectOpen)}
            className={`w-5 h-5 flex items-center justify-center rounded text-gray-400 hover:bg-gray-800 hover:text-white transition-colors ${projectOpen ? 'rotate-90' : ''}`}
          >
            <ChevronIcon />
          </button>
        </div>
        {projectOpen && (
          <div className="flex flex-col gap-0.5 px-0.5">
            {PROJECTS.map((p) => (
              <div
                key={p.name}
                className="flex items-center gap-2 px-2 py-1.5 rounded text-gray-400 hover:bg-gray-800/60 hover:text-white cursor-pointer transition-colors text-xs"
              >
                <span className="text-[13px]">{p.icon}</span>
                <span className="truncate">{p.name}</span>
              </div>
            ))}
          </div>
        )}

        {/* 绘画 分组 */}
        <div className="flex items-center gap-1 pt-4 pb-1 px-1">
          <span className="flex-1 text-xs font-semibold text-gray-300">绘画</span>
          <span className="text-[10px] text-gray-500">{DRAWINGS.length}</span>
          <button
            data-track="shell-draw-add"
            className="w-5 h-5 flex items-center justify-center rounded text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
          >
            <PlusIcon className="w-3.5 h-3.5" />
          </button>
          <button
            data-track="shell-draw-toggle"
            onClick={() => setDrawOpen(!drawOpen)}
            className={`w-5 h-5 flex items-center justify-center rounded text-gray-400 hover:bg-gray-800 hover:text-white transition-colors ${drawOpen ? 'rotate-90' : ''}`}
          >
            <ChevronIcon />
          </button>
        </div>
        {drawOpen && (
          <div className="flex flex-col gap-0.5 px-0.5">
            {DRAWINGS.map((p) => (
              <div
                key={p.name}
                className="flex items-center gap-2 px-2 py-1.5 rounded text-gray-400 hover:bg-gray-800/60 hover:text-white cursor-pointer transition-colors text-xs"
              >
                <span className="text-[13px]">{p.icon}</span>
                <span className="truncate">{p.name}</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex-1" />

        {/* 底部 */}
        <div className="flex flex-col gap-0.5 border-t border-gray-800 pt-2">
          <button
            data-track="shell-settings"
            className="flex items-center gap-2 px-2 py-1.5 rounded text-gray-400 hover:bg-gray-800/60 hover:text-white transition-colors text-xs"
          >
            <SettingsIcon className="w-4 h-4" />
            设置
          </button>
          <button
            data-track="shell-help"
            className="flex items-center gap-2 px-2 py-1.5 rounded text-gray-400 hover:bg-gray-800/60 hover:text-white transition-colors text-xs"
          >
            <HelpIcon className="w-4 h-4" />
            帮助
          </button>
          {authEnabled && (
            <div className="flex items-center gap-2 px-2 py-1.5 text-[10px] text-gray-500">
              <span>👤 {displayName || username || '未登录'}</span>
              <button
                onClick={() => {
                  logout()
                  window.location.href = import.meta.env.BASE_URL + 'login'
                }}
                data-track="shell-logout"
                className="ml-auto text-red-400 hover:text-red-300 transition-colors"
              >
                登出
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* ===== 右侧主区 ===== */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* 顶栏 920×60 */}
        <header className="h-[60px] flex-shrink-0 bg-[#111111] border-b border-gray-800 flex items-center gap-4 px-5">
          <div className="flex-shrink-0">
            <div className="text-[15px] font-semibold leading-tight">债券市场智能分析</div>
            <div className="text-[10px] text-gray-500 leading-tight">Bond Market Intelligence</div>
          </div>

          <div className="flex-1 max-w-[520px] flex items-center gap-2 bg-[#161616] border border-gray-800 rounded-lg px-3 py-2 text-gray-400">
            <SearchIcon className="w-4 h-4" />
            <input
              placeholder="搜索债券、新闻、策略…"
              className="flex-1 bg-transparent outline-none text-[13px] text-white placeholder-gray-500"
            />
          </div>

          <button
            data-track="shell-share"
            className="ml-auto flex items-center gap-1.5 bg-white text-black rounded-lg px-4 py-2 text-[13px] font-medium hover:opacity-85 transition-opacity"
          >
            <ShareIcon className="w-4 h-4" />
            分享
          </button>
        </header>

        {/* 板块标签条 */}
        <nav className="h-[46px] flex-shrink-0 flex items-center gap-1 px-5 border-b border-gray-800 bg-black">
          {SECTIONS.map((s) => (
            <NavLink
              key={s.to}
              to={s.to}
              data-track={`shell-tab-${s.to.slice(1)}`}
              className={({ isActive }) =>
                `px-3.5 py-1.5 rounded-lg text-[13px] transition-colors relative ${
                  isActive ? 'text-white font-medium' : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {s.name}
                  {isActive && (
                    <span className="absolute left-3.5 right-3.5 -bottom-[1px] h-0.5 bg-blue-500 rounded-full" />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* 内容区：当前板块页 */}
        <main className="flex-1 min-h-0 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default WorkspaceLayout
