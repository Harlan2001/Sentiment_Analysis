import { useMemo } from 'react'
import type { StrategyWizardApi } from './useStrategyWizard'
import { parseParameterRows, patchParameterRows } from './parameters'

const BACKTEST_MODE_OPTIONS = [
  { code: 'bar', label: 'bar（K线）' },
  { code: 'tick', label: 'tick（逐笔）' },
]

const CANDLE_INTERVAL_OPTIONS = [
  { code: '1d', label: '1d（日频）' },
  { code: '1h', label: '1h（小时）' },
  { code: '30m', label: '30m（30分钟）' },
  { code: '5m', label: '5m（5分钟）' },
  { code: '1m', label: '1m（1分钟）' },
]

/**
 * 步骤①：需求与参数。
 * 标的/模式/周期必须由用户显式选择——历史上“模型自己选标的”的事故正源于
 * 这三个输入藏在提示词里。交易参数不再造假默认值：草稿缺块时只提示回填。
 */
export function RequirementStep({ wizard }: { wizard: StrategyWizardApi }) {
  const {
    instruments, instrumentCode, backtestMode, candleInterval,
    setInstrumentCode, setBacktestMode, setCandleInterval,
    draft, patchDraft, hasDraft, isDraftReady, isRunning, submitting,
  } = wizard

  const rows = useMemo(() => parseParameterRows(draft), [draft])
  const instrumentOptions = instruments?.instruments ?? (
    instrumentCode ? [{ code: instrumentCode, label: instrumentCode }] : []
  )
  const selectDisabled = submitting || isRunning
  const paramsEditable = isDraftReady && !submitting

  function updateRow(index: number, value: string) {
    if (!rows) return
    const next = rows.map((row, i) => (i === index ? { ...row, value } : row))
    patchDraft(patchParameterRows(draft, next))
  }

  return (
    <section className="sw-panel" aria-label="需求与参数">
      <header className="sw-panel-head">
        <div>
          <h2>需求与参数</h2>
          <p>先显式选定标的与回测口径，再在底部输入框写一句话需求生成草稿；草稿生成后可调整交易参数。</p>
        </div>
      </header>

      <div className="sw-req-grid">
        <label className="sw-field">
          <span>交易标的</span>
          <select value={instrumentCode} disabled={selectDisabled} onChange={(e) => setInstrumentCode(e.target.value)}>
            {instruments === null && !instrumentOptions.length && <option value="">标的白名单不可用</option>}
            {!instrumentCode && <option value="">加载标的白名单…</option>}
            {instrumentOptions.map((option) => (
              <option key={option.code} value={option.code}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="sw-field">
          <span>策略模式</span>
          <select value={backtestMode} disabled={selectDisabled} onChange={(e) => setBacktestMode(e.target.value)}>
            {BACKTEST_MODE_OPTIONS.map((option) => (
              <option key={option.code} value={option.code}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="sw-field">
          <span>K线周期</span>
          <select value={candleInterval} disabled={selectDisabled} onChange={(e) => setCandleInterval(e.target.value)}>
            {CANDLE_INTERVAL_OPTIONS.map((option) => (
              <option key={option.code} value={option.code}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="sw-req-note">
        标的限定为利率债口径品种（白名单由后端下发）；黄金等需另做方向映射，本期不支持。
        修改标的/模式/周期后需重新生成草稿。
      </p>

      <div className="sw-req-params">
        <div className="sw-req-params-head">
          <h3>开平仓与风控参数</h3>
          {hasDraft && rows && <span className="sw-badge sw-badge--neutral">{rows.length} 项</span>}
        </div>
        {rows === null
          ? <div className="sw-empty-hint">草稿生成后回填：开仓/平仓规则、仓位、止损止盈、回测区间等。</div>
          : (
            <div className="sw-req-params-grid">
              {rows.map((row, index) => (
                <label className="sw-field" key={`${row.label}-${index}`}>
                  <span>{row.label}</span>
                  <input
                    value={row.value}
                    disabled={!paramsEditable}
                    onChange={(e) => updateRow(index, e.target.value)}
                  />
                </label>
              ))}
            </div>
          )}
        {hasDraft && !isDraftReady && (
          <p className="sw-req-note">提示词已确认；如需调整参数，请在底部发送新需求开启新一轮。</p>
        )}
      </div>
    </section>
  )
}
