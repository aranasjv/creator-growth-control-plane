"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { formatDate, readAccounts, updateAccount, type AccountItem } from "@/lib/api";

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [editingAccount, setEditingAccount] = useState<AccountItem | null>(null);
  const [editTopic, setEditTopic] = useState("");
  const [editLanguage, setEditLanguage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    readAccounts().then((data) => {
      setAccounts(data);
      setIsLoading(false);
    });
  }, []);

  const handleEdit = (account: AccountItem) => {
    setEditingAccount(account);
    setEditTopic(account.topic ?? account.niche ?? "");
    setEditLanguage(account.language ?? "");
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAccount) return;
    
    setIsSaving(true);
    try {
      await updateAccount(editingAccount.id, {
        topic: editTopic,
        niche: editingAccount.provider === "youtube" ? editTopic : undefined,
        language: editLanguage,
      });
      const refreshed = await readAccounts();
      setAccounts(refreshed);
      setEditingAccount(null);
    } catch (err) {
      alert("Failed to update account");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <AppShell
      current="/accounts"
      eyebrow="Accounts"
      title="Every channel, every profile, every weak point"
      summary="This view keeps the social and niche accounts visible so you can see who is producing, who is stale, and who is failing before you queue more work."
    >
      <section className="card-grid module-scroll">
        {isLoading && <p className="empty-state">Loading accounts...</p>}
        {accounts.length === 0 && !isLoading ? <p className="empty-state">No accounts have been imported from the legacy cache yet.</p> : null}
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
            <div className="table-actions" style={{ marginTop: "0.85rem", borderTop: "1px solid var(--line)", paddingTop: "0.6rem" }}>
              <button 
                type="button" 
                className="shell__nav-link" 
                onClick={() => handleEdit(account)}
              >
                Edit Config
              </button>
            </div>
          </article>
        ))}
      </section>

      {editingAccount && (
        <div className="inspector-dialog" style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="inspector-dialog__surface" style={{ width: "min(32rem, 100%)", background: "var(--color-surface)", borderRadius: "12px", border: "1px solid var(--color-border)", padding: "1.5rem" }}>
            <div className="panel__header" style={{ marginBottom: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0 }}>Edit {editingAccount.provider} Profile</h3>
              <button 
                type="button" 
                className="shell__nav-link" 
                style={{ padding: "0.2rem 0.5rem" }} 
                onClick={() => setEditingAccount(null)}
              >
                Cancel
              </button>
            </div>
            <form onSubmit={handleSave} className="settings-form" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <label className="form-field" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <span style={{ fontWeight: 600 }}>Account Topic / Niche</span>
                <textarea 
                  className="form-input" 
                  style={{ width: "100%", padding: "0.75rem", borderRadius: "8px", background: "var(--color-surface)", color: "var(--color-text)", border: "1px solid var(--color-border)", minHeight: "100px", fontFamily: "inherit" }}
                  rows={3}
                  value={editTopic} 
                  onChange={(e) => setEditTopic(e.target.value)} 
                  placeholder="e.g. AI marketing and customer growth for pet shops..."
                />
              </label>
              <label className="form-field" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <span style={{ fontWeight: 600 }}>Language (Optional)</span>
                <input 
                  type="text" 
                  className="form-input" 
                  style={{ width: "100%", padding: "0.75rem", borderRadius: "8px", background: "var(--color-surface)", color: "var(--color-text)", border: "1px solid var(--color-border)", fontFamily: "inherit" }}
                  value={editLanguage} 
                  onChange={(e) => setEditLanguage(e.target.value)} 
                  placeholder="English"
                />
              </label>
              <div className="form-actions" style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.8rem", paddingTop: "0.8rem", borderTop: "1px solid var(--line)" }}>
                <button type="submit" className="shell__nav-link shell__nav-link--active" disabled={isSaving} style={{ padding: "0.5rem 1.25rem", borderRadius: "6px" }}>
                  {isSaving ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}
