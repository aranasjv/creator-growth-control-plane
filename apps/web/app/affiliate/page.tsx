import { AppShell } from "@/components/app-shell";
import { formatDate, formatMoney, readAffiliateOverview, readProfit } from "@/lib/api";

export default async function AffiliatePage() {
  const [affiliate, profit] = await Promise.all([readAffiliateOverview(), readProfit()]);

  return (
    <AppShell
      current="/affiliate"
      eyebrow="Affiliate"
      title="Revenue, cost, and the truth behind the pitch"
      summary="Affiliate performance only becomes useful once clicks, conversions, commission, and cost are visible in the same place. This page is shaped for that transition."
    >
      <section className="panel-grid module-scroll">
        <article className="panel panel--compact">
          <div className="panel__header">
            <h3>Profit snapshot</h3>
            <span>control plane totals</span>
          </div>
          <div className="mini-kpis">
            <div><span>Revenue</span><strong>{formatMoney(profit.totals.revenue)}</strong></div>
            <div><span>Cost</span><strong>{formatMoney(profit.totals.cost)}</strong></div>
            <div><span>Net</span><strong>{formatMoney(profit.totals.profit)}</strong></div>
          </div>
        </article>
        <article className="panel panel--table">
          <div className="panel__header">
            <h3>Tracked products</h3>
            <span>{affiliate.products.length} items</span>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Account</th>
                  <th>Created</th>
                  <th>Link</th>
                </tr>
              </thead>
              <tbody>
                {affiliate.products.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="empty-state">No affiliate products have been imported yet.</td>
                  </tr>
                ) : null}
                {affiliate.products.map((product) => (
                  <tr key={product.id}>
                    <td>{product.name ?? product.id}</td>
                    <td>{product.accountNickname ?? product.accountId ?? "-"}</td>
                    <td>{formatDate(product.createdAt)}</td>
                    <td><a href={product.affiliateLink} target="_blank" rel="noreferrer">Open link</a></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </AppShell>
  );
}
