import { AppShell } from "@/components/app-shell";
import { formatDate, readOutreachLeads } from "@/lib/api";

export default async function OutreachPage() {
  const leads = await readOutreachLeads();

  return (
    <AppShell
      current="/outreach"
      eyebrow="Outreach"
      title="Lead readiness and contact quality"
      summary="See exactly which scraped businesses are contact-ready, which still need email extraction, and where outreach quality drops before a live send."
    >
      <section className="module-stack">
        <section className="panel panel--compact">
          <div className="panel__header">
            <h3>Outreach lead health</h3>
            <span>Updated {formatDate(leads.generatedAt)}</span>
          </div>
          <div className="mini-kpis">
            <div>
              <span>Total leads</span>
              <strong>{leads.leadCount}</strong>
            </div>
            <div>
              <span>Ready to send</span>
              <strong>{leads.readyCount}</strong>
            </div>
            <div>
              <span>Website only</span>
              <strong>{leads.websiteOnlyCount}</strong>
            </div>
          </div>
          <p className="stack-list__meta">Missing contact: {leads.missingContactCount} | Source {leads.sourcePath || "No file loaded yet"}</p>
        </section>

        <section className="panel panel--table">
          <div className="panel__header">
            <h3>Recent lead rows</h3>
            <span>{leads.rows.length} rows</span>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Business</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Email</th>
                  <th>Website</th>
                  <th>Phone</th>
                </tr>
              </thead>
              <tbody>
                {leads.rows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="empty-state">No outreach leads found yet. Run outreach dry-run or live to populate this table.</td>
                  </tr>
                ) : null}
                {leads.rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.title || "Unknown business"}</strong>
                      <p className="stack-list__meta">{row.address || "No address found"}</p>
                    </td>
                    <td>{row.category || "-"}</td>
                    <td>
                      <span className={`status-pill status-pill--${row.status}`}>{row.status.replace("_", " ")}</span>
                    </td>
                    <td>{row.email || "-"}</td>
                    <td>
                      {row.website ? (
                        <a className="content-card__link" href={row.website} target="_blank" rel="noreferrer">
                          open
                        </a>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td>{row.phone || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </section>
    </AppShell>
  );
}
