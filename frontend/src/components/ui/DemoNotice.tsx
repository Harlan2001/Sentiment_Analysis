type DemoNoticeProps = {
  description?: string
  title?: string
}

export function DemoNotice({
  title = '演示功能',
  description = '当前页面展示的内容为演示数据，实际功能尚在开发中。',
}: DemoNoticeProps) {
  return (
    <aside className="demo-notice" role="status" aria-label="演示功能提示">
      <span className="demo-notice-icon" aria-hidden="true">!</span>
      <div className="demo-notice-copy">
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
      <span className="demo-notice-badge" aria-hidden="true">DEMO</span>
    </aside>
  )
}
