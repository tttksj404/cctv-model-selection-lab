export function SummaryCard({ card }) {
  const Icon = card.icon;

  return (
    <article className="summary-card">
      <div className="summary-icon"><Icon size={20} /></div>
      <div>
        <p>{card.title}</p>
        <strong>{card.value.toLocaleString()}</strong>
        <span className={card.trend}>{card.delta} 전일 대비</span>
      </div>
    </article>
  );
}
