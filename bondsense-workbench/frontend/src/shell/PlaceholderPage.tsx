interface PlaceholderPageProps {
  title: string
  description: string
}

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <section className="placeholder-page">
      <div className="placeholder-kicker">BondSense · 第一期骨架</div>
      <h1>{title}</h1>
      <p>{description}</p>
      <div className="placeholder-grid" aria-hidden="true">
        <div />
        <div />
        <div />
      </div>
    </section>
  )
}
