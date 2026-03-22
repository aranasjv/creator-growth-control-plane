import { AppShell } from "@/components/app-shell";
import { formatDate, formatMoney, readContent } from "@/lib/api";

export default async function ContentPage() {
  const assets = await readContent();

  return (
    <AppShell
      current="/content"
      eyebrow="Content"
      title="Generated outputs, not just job records"
      summary="Use this gallery-table hybrid to monitor what was actually produced: posts, short-form videos, and the money or engagement data attached to them."
    >
      <section className="card-grid module-scroll">
        {assets.length === 0 ? <p className="empty-state">No content assets have been synced yet.</p> : null}
        {assets.map((asset) => (
          <article className="content-card" key={asset.id}>
            <div className="content-card__header">
              <span className="status-pill status-pill--running">{asset.kind}</span>
              <span>{asset.provider}</span>
            </div>
            <h3>{asset.title}</h3>
            <p className="content-card__description">{asset.description ?? "No description captured."}</p>
            <dl className="content-card__stats">
              <div><dt>Published</dt><dd>{formatDate(asset.publishedAt)}</dd></div>
              <div><dt>Revenue</dt><dd>{formatMoney(asset.revenue ?? 0)}</dd></div>
              <div><dt>Cost</dt><dd>{formatMoney(asset.cost ?? 0)}</dd></div>
            </dl>
            {asset.url ? <a className="content-card__link" href={asset.url} target="_blank" rel="noreferrer">Open published asset</a> : null}
          </article>
        ))}
      </section>
    </AppShell>
  );
}
