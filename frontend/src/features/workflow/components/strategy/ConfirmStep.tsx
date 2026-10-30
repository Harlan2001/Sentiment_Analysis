import { useMemo } from 'react'
import type { StrategyWizardApi } from './useStrategyWizard'
import { Fold } from './Fold'
import {
  isSectionDirty,
  parsePromptSections,
  patchSection,
  type SectionKey,
} from './promptSections'

/**
 * 步骤③：确认发送。只有【交易参数】【用户需求】两个内层块可编辑；
 * 【标的与模式】与标记外的情报/契约段只读。编辑仍只改受保护段内文本，
 * 后端 apply_user_edited_requirement 会拒绝标记外的任何改动。
 */
export function ConfirmStep({ wizard }: { wizard: StrategyWizardApi }) {
  const {
    draft, systemDraft, patchDraft, resetDraft, confirm, regenerate,
    isDraftReady, submitting, isRunning, hasDraft, loading,
  } = wizard

  const parsed = useMemo(() => parsePromptSections(draft), [draft])
  const editable = isDraftReady && !submitting

  function editSection(key: SectionKey, value: string) {
    patchDraft(patchSection(draft, key, value))
  }

  if (!hasDraft) {
    return (
      <section className="sw-panel" aria-label="确认发送">
        <header className="sw-panel-head">
          <div><h2>确认发送</h2><p>草稿生成后在此分段核对并确认。</p></div>
        </header>
        <div className="sw-empty-hint">{loading ? '正在读取策略会话…' : '在底部输入一句话策略需求以生成提示词草稿。'}</div>
      </section>
    )
  }

  return (
    <section className="sw-panel" aria-label="确认发送">
      <header className="sw-panel-head">
        <div>
          <h2>确认发送</h2>
          <p>只有「交易参数」「用户需求」可编辑；标记外的情报包与契约受保护，改动会被后端拒绝。</p>
        </div>
        {isDraftReady
          ? <span className="sw-badge sw-badge--warning">待确认</span>
          : <span className="sw-badge sw-badge--neutral">{isRunning ? '已确认·生成中' : '已确认'}</span>}
      </header>

      {!parsed.supported
        ? (
          <div className="sw-confirm-legacy">
            <p className="sw-req-note">旧版草稿不含分段标记，不支持在线分段编辑；可直接「重新生成」得到新版草稿。</p>
            <pre className="sw-protected-text">{draft}</pre>
          </div>
        )
        : (
          <div className="sw-confirm-folds">
            <Fold title="交易参数" defaultOpen dirty={isSectionDirty(draft, systemDraft, 'tradingParameters')} readOnly={!editable}>
              <textarea
                className="sw-section-text"
                value={parsed.sections.tradingParameters ?? ''}
                readOnly={!editable}
                onChange={(e) => editSection('tradingParameters', e.target.value)}
              />
            </Fold>
            <Fold title="标的与模式" readOnly meta={<span className="sw-fold-meta-text">如需更换请回①修改后重新生成</span>}>
              <textarea
                className="sw-section-text"
                value={parsed.sections.instrument ?? ''}
                readOnly
                tabIndex={-1}
              />
            </Fold>
            <Fold title="用户需求" defaultOpen dirty={isSectionDirty(draft, systemDraft, 'requirement')} readOnly={!editable}>
              <textarea
                className="sw-section-text"
                value={parsed.sections.requirement ?? ''}
                readOnly={!editable}
                placeholder="写明你要的策略逻辑（一句话需求会被大模型扩写为正式任务卡）"
                onChange={(e) => editSection('requirement', e.target.value)}
              />
            </Fold>
            {parsed.protectedPrefix && (
              <Fold title="情报包 / 任务卡 / 纪律条款（受保护，只读）" readOnly>
                <pre className="sw-protected-text">{parsed.protectedPrefix}</pre>
              </Fold>
            )}
            {parsed.protectedSuffix && (
              <Fold title="输出与审计契约（受保护，只读）" readOnly>
                <pre className="sw-protected-text">{parsed.protectedSuffix}</pre>
              </Fold>
            )}
          </div>
        )}

      <footer className="sw-actions">
        <button type="button" className="sw-ghost-button" onClick={resetDraft} disabled={!editable}>
          还原系统草稿
        </button>
        <button type="button" className="sw-ghost-button" onClick={() => void regenerate()} disabled={submitting || isRunning}>
          重新生成
        </button>
        <span className="sw-actions-spacer" />
        <button type="button" className="sw-primary-button" onClick={() => void confirm()} disabled={!editable}>
          {isDraftReady ? '确认并生成' : isRunning ? '策略生成中…' : '已确认'}
        </button>
      </footer>
    </section>
  )
}
