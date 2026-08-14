import { FormEvent, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

type HomeChatDockProps = {
  placeholder: string
  className?: string
}

/** Shared entry point from every home section into the existing Agent chat. */
export function HomeChatDock({ placeholder, className = '' }: HomeChatDockProps) {
  const navigate = useNavigate()
  const formRef = useRef<HTMLFormElement>(null)
  const [question, setQuestion] = useState('')

  function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const draft = question.trim()
    navigate(draft ? `/chat?draft=${encodeURIComponent(draft)}` : '/chat')
  }

  return (
    <form className={`market-chat-dock ${className}`.trim()} onSubmit={submitQuestion} ref={formRef}>
      <textarea
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            formRef.current?.requestSubmit()
          }
        }}
        placeholder={placeholder}
        rows={2}
      />
      <div className="market-chat-actions">
        <span>{'BondSense \u00b7 Agent \u5bf9\u8bdd'}</span>
        <span className="market-chat-hint">{'Enter \u53d1\u9001\uff0cShift + Enter \u6362\u884c'}</span>
        <button type="submit" disabled={!question.trim()} aria-label={'\u8fdb\u5165\u65b0\u4f1a\u8bdd'}>&uarr;</button>
      </div>
    </form>
  )
}