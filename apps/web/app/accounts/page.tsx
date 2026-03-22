import { AppShell } from "@/components/app-shell";
import { formatDate, readAccounts } from "@/lib/api";

export default async function AccountsPage() {
  const accounts = await readAccounts();

  return (
    <AppShell
      current="/accounts"
      eyebrow="Accounts"
      title="Every channel, every profile, every weak point"
      summary="This view keeps the social and niche accounts visible so you can see who is producing, who is stale, and who is failing before you queue more work."
    >
      <section className="card-grid module-scroll">
        {accounts.length === 0 ? <p className="empty-state">No accounts have been imported from the legacy cache yet.</p> : null}
        {accounts.map((account) => (
          <article className="profile-card" key={account.id}>
            <div className="profile-card__header">
              <p className="profile-card__provider">{account.provider}</p>
              <span className={account.lastError ? "status-pill status-pill--failed" : "status-pill status-pill--succeeded"}>
                {account.lastError ? "needs attention" : "ready"}
              </span>
            </div>
            <h3>{account.nickname}</h3>
            <dl className="profile-card__meta">
              <div><dt>Topic</dt><dd>{account.topic ?? account.niche ?? "Not set"}</dd></div>
              <div><dt>Language</dt><dd>{account.language ?? "Not set"}</dd></div>
              <div><dt>Assets</dt><dd>{account.assetCount}</dd></div>
              <div><dt>Last active</dt><dd>{formatDate(account.lastActiveAt)}</dd></div>
            </dl>
            {account.lastError ? <p className="profile-card__error">{account.lastError}</p> : null}
          </article>
        ))}
      </section>
    </AppShell>
  );
}
