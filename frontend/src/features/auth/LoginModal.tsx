import React, { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import Modal from '@/components/ui/Modal'
import Button from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

type LoginMode = 'phone' | 'password'

interface LoginModalProps {
  isOpen: boolean
  onClose: () => void
  /** 登录成功回调（如刷新侧边栏） */
  onLoggedIn?: () => void
}

/**
 * 登录弹窗：替代原全屏登录页。
 * 未登录时左下角账户区点击打开，登录成功后关闭并回填账户状态。
 */
const LoginModal: React.FC<LoginModalProps> = ({ isOpen, onClose, onLoggedIn }) => {
  const { login, loginByPhone } = useAuth()
  const [mode, setMode] = useState<LoginMode>('phone')
  const [phone, setPhone] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const resetForm = () => {
    setPhone('')
    setUsername('')
    setPassword('')
    setError('')
  }

  const handleSwitchMode = (newMode: LoginMode) => {
    setMode(newMode)
    resetForm()
  }

  const handleSuccess = () => {
    onLoggedIn?.()
    onClose()
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (mode === 'phone') {
      if (!phone.trim()) {
        setError('请输入手机号')
        return
      }
      if (!/^1[3-9]\d{9}$/.test(phone.trim())) {
        setError('请输入正确的手机号')
        return
      }

      setLoading(true)
      try {
        const result = await loginByPhone(phone.trim())
        if (!result.success) {
          setError(result.message)
        } else {
          handleSuccess()
        }
      } catch {
        setError('登录失败，请重试')
      } finally {
        setLoading(false)
      }
    } else {
      if (!username.trim()) {
        setError('请输入用户名')
        return
      }
      if (!password) {
        setError('请输入密码')
        return
      }

      setLoading(true)
      try {
        const result = await login(username.trim(), password)
        if (!result.success) {
          setError(result.message)
        } else {
          handleSuccess()
        }
      } catch {
        setError('登录失败，请重试')
      } finally {
        setLoading(false)
      }
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="登录"
      size="sm"
      panelClassName="max-w-[430px] !bg-[#181818] !border-[#414141] shadow-black/60 text-left"
      contentClassName="px-6 pb-6 pt-5 sm:px-7 sm:pb-7"
    >
      {/* 品牌行 */}
      <div className="flex items-center gap-3 mb-5">
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-[#4a90d9] via-[#5b6cf0] to-[#7c4dff] text-[15px] font-extrabold text-[#f0f4ff] shadow-[0_0_0_1px_rgba(90,130,240,.35),0_5px_20px_rgba(90,110,235,.3)]">
          B
        </span>
        <div>
          <div className="text-[15px] font-semibold tracking-tight text-[#ededed]">债券市场智能分析</div>
          <div className="mt-0.5 text-xs text-[#8e8e8e]">登录后即可使用个人工作台</div>
        </div>
      </div>

      {/* 模式切换 Tab */}
      <div className="grid grid-cols-2 mb-5 rounded-lg bg-[#202020] border border-[#373737] p-1">
        <button
          type="button"
          onClick={() => handleSwitchMode('phone')}
          className={`min-h-9 px-2 py-2 text-sm font-medium rounded-md transition-all duration-200 ${
            mode === 'phone'
              ? 'bg-[#303030] text-white shadow-sm shadow-black/30'
              : 'text-[#929292] hover:bg-[#292929] hover:text-[#e5e5e5]'
          }`}
        >
          手机号登录
        </button>
        <button
          type="button"
          onClick={() => handleSwitchMode('password')}
          className={`min-h-9 px-2 py-2 text-sm font-medium rounded-md transition-all duration-200 ${
            mode === 'password'
              ? 'bg-[#303030] text-white shadow-sm shadow-black/30'
              : 'text-[#929292] hover:bg-[#292929] hover:text-[#e5e5e5]'
          }`}
        >
          账号密码登录
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {mode === 'phone' ? (
          <Input
            label="手机号"
            type="tel"
            placeholder="请输入手机号"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            autoComplete="tel"
            autoFocus
            maxLength={11}
            className="!border-[#424242] !bg-[#191919] py-2.5 placeholder:text-[#717171] focus:!border-[#686868]"
            icon={
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
                />
              </svg>
            }
          />
        ) : (
          <>
            <Input
              label="用户名"
              type="text"
              placeholder="请输入用户名"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              className="!border-[#424242] !bg-[#191919] py-2.5 placeholder:text-[#717171] focus:!border-[#686868]"
              icon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                  />
                </svg>
              }
            />

            <Input
              label="密码"
              type="password"
              placeholder="请输入密码"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="!border-[#424242] !bg-[#191919] py-2.5 placeholder:text-[#717171] focus:!border-[#686868]"
              icon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                  />
                </svg>
              }
            />
          </>
        )}

        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-red-400/10 border border-red-400/30 text-red-400 text-sm">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span>{error}</span>
          </div>
        )}

        <Button type="submit" loading={loading} className="w-full min-h-10 mt-1 rounded-lg shadow-none" size="md">
          登 录
        </Button>

        <p className="pt-0.5 text-center text-[#777] text-xs leading-5">仅供授权用户使用 · 如有问题请联系管理员</p>
      </form>
    </Modal>
  )
}

export default LoginModal
