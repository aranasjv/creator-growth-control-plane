import type { KpiCard } from "@/lib/api";

export function KpiGrid({ cards }: { cards: KpiCard[] }) {
  return (
    <section className="kpi-grid" aria-label="Key performance indicators">
      {cards.map((card) => (
        <article className="kpi-card" key={card.label}>
          <p className="kpi-card__label">{card.label}</p>
          <p className="kpi-card__value">{card.value}</p>
          <p className="kpi-card__hint">{card.hint}</p>
        </article>
      ))}
    </section>
  );
}
