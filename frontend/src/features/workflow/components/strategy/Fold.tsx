import type { ReactNode } from 'react'

type FoldProps = {
  title: string
  defaultOpen?: boolean
  /** 用户改过的段标色条 + “已修改”角标 */
  dirty?: boolean
  readOnly?: boolean
  meta?: ReactNode
  children: ReactNode
}

/** 分段折叠卡：情报原文/提示词分段统一用它，只读段不提供编辑 affordance。 */
export function Fold({ title, defaultOpen = false, dirty = false, readOnly = false, meta, children }: FoldProps) {
  return (
    <details
      className={['sw-fold', dirty ? 'is-dirty' : '', readOnly ? 'is-readonly' : ''].filter(Boolean).join(' ')}
      open={defaultOpen ? true : undefined}
    >
      <summary>
        <span className="sw-fold-caret" aria-hidden="true" />
        <span className="sw-fold-title">{title}</span>
        {dirty && <span className="sw-fold-tag">已修改</span>}
        {meta && <span className="sw-fold-meta">{meta}</span>}
      </summary>
      <div className="sw-fold-body">{children}</div>
    </details>
  )
}
