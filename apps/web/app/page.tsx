import { AppShell } from "@/components/app-shell";
import { KpiGrid } from "@/components/kpi-grid";
import { formatDate, readOverview } from "@/lib/api";

export default async function DashboardPage() {
  const overview = await readOverview();

  return (
    <AppShell
      current="/"
      eyebrow="Dashboard"
      title="The whole automation business, in one glance"
      summary="Track job volume, success, revenue, cost, and the last thing every account touched without jumping between the old CLI, cache files, and browser sessions."
    >
      <KpiGrid cards={overview.kpis} />
      <section className="panel-grid module-scroll">
        <article className="panel">
          <div className="panel__header">
            <h3>Recent jobs</h3>
            <span>{overview.recentJobs.length} visible</span>
          </div>
          <div className="stack-list stack-list--scroll">
            {overview.recentJobs.length === 0 ? <p className="empty-state">No jobs yet. Queue work from the API once the worker stack is running.</p> : null}
            {overview.recentJobs.map((job) => (
              <div className="stack-list__item" key={job.id}>
                <div>
                  <p className="stack-list__title">{job.type}</p>
                  <p className="stack-list__meta">{job.provider} | created {formatDate(job.createdAt)}</p>
                </div>
                <span className={`status-pill status-pill--${job.status}`}>{job.status}</span>
              </div>
            ))}
          </div>
        </article>
        <article className="panel">
          <div className="panel__header">
            <h3>Active accounts</h3>
            <span>{overview.activeAccounts.length} highlighted</span>
          </div>
          <div className="stack-list stack-list--scroll">
            {overview.activeAccounts.length === 0 ? <p className="empty-state">Legacy cache import has not populated any accounts yet.</p> : null}
            {overview.activeAccounts.map((account) => (
              <div className="stack-list__item" key={account.id}>
                <div>
                  <p className="stack-list__title">{account.nickname}</p>
                  <p className="stack-list__meta">{account.provider} | last active {formatDate(account.lastActiveAt)}</p>
                </div>
                {account.lastError ? <span className="status-pill status-pill--failed">attention</span> : <span className="status-pill status-pill--succeeded">healthy</span>}
              </div>
            ))}
          </div>
        </article>
      </section>
    </AppShell>
  );
}
