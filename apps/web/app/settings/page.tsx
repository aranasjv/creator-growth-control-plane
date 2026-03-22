"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { readSettings, saveSettings, readPrompts, savePrompt, createPrompt, deletePrompt, type GlobalSettings, type SystemPrompt } from "@/lib/api";

type ModelProvider = "ollama" | "openai" | "gemini";

const PROVIDER_MODEL_FALLBACKS: Record<ModelProvider, string[]> = {
  ollama: ["llama3.2:3b", "llama3.2:1b", "qwen2.5:7b", "mistral:7b", "gemma2:9b"],
  openai: ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1", "gpt-4o"],
  gemini: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
};

const PROVIDER_LABELS: Record<ModelProvider, string> = {
  ollama: "Ollama (Local)",
  openai: "OpenAI",
  gemini: "Gemini",
};

function normalizeProvider(provider: string): ModelProvider {
  if (provider === "openai" || provider === "gemini" || provider === "ollama") {
    return provider;
  }
  return "ollama";
}

function maskApiKey(value?: string | null): string | null {
  if (!value || value.trim().length === 0) {
    return null;
  }
  const trimmed = value.trim();
  if (trimmed.length <= 8) {
    return "********";
  }
  return `${trimmed.slice(0, 4)}...${trimmed.slice(-4)}`;
}

function getModelForProvider(settings: GlobalSettings, provider: ModelProvider): string {
  if (provider === "openai") return settings.openAIModelName;
  if (provider === "gemini") return settings.geminiModelName;
  return settings.ollamaModelName;
}

function setModelForProvider(settings: GlobalSettings, provider: ModelProvider, model: string): GlobalSettings {
  if (provider === "openai") return { ...settings, openAIModelName: model };
  if (provider === "gemini") return { ...settings, geminiModelName: model };
  return { ...settings, ollamaModelName: model };
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<"global" | "prompts">("global");
  
  const [settings, setSettings] = useState<GlobalSettings | null>(null);
  const [prompts, setPrompts] = useState<SystemPrompt[]>([]);
  
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [savingPromptId, setSavingPromptId] = useState<string | null>(null);
  const [deletingPromptId, setDeletingPromptId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  
  const [editingPromptId, setEditingPromptId] = useState<string | null>(null);
  const [editPromptText, setEditPromptText] = useState<string>("");
  
  const [isCreatingPrompt, setIsCreatingPrompt] = useState(false);
  const [newPromptData, setNewPromptData] = useState({ key: '', description: '', promptText: '' });

  useEffect(() => {
    readSettings().then(setSettings).catch(console.error);
    refreshPrompts();
  }, []);

  const refreshPrompts = () => {
    readPrompts().then(setPrompts).catch(console.error);
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;
    setIsSavingSettings(true);
    setMessage(null);
    try {
      const updated = await saveSettings(settings);
      setSettings(updated);
      setMessage("Settings saved successfully.");
    } catch (err) {
      setMessage("Failed to save settings.");
    } finally {
      setIsSavingSettings(false);
    }
  };

  const handleSavePrompt = async (promptId: string) => {
    setSavingPromptId(promptId);
    setMessage(null);
    try {
      await savePrompt(promptId, editPromptText);
      setMessage("Prompt saved successfully.");
      setEditingPromptId(null);
      refreshPrompts();
    } catch (err) {
      setMessage("Failed to save prompt.");
    } finally {
      setSavingPromptId(null);
    }
  };
  
  const handleDeletePrompt = async (promptId: string) => {
    if (!confirm("Are you sure you want to delete this prompt?")) return;
    setDeletingPromptId(promptId);
    setMessage(null);
    try {
      await deletePrompt(promptId);
      setMessage("Prompt deleted successfully.");
      refreshPrompts();
    } catch (err) {
      setMessage("Failed to delete prompt.");
    } finally {
      setDeletingPromptId(null);
    }
  };

  const handleCreatePrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingSettings(true);
    setMessage(null);
    try {
      await createPrompt(newPromptData);
      setMessage("Prompt created successfully.");
      setIsCreatingPrompt(false);
      setNewPromptData({ key: '', description: '', promptText: '' });
      refreshPrompts();
    } catch (err) {
      setMessage("Failed to create prompt.");
    } finally {
      setIsSavingSettings(false);
    }
  };

  const activeProvider = settings ? normalizeProvider(settings.activeModelProvider) : "ollama";

  const modelCatalog = useMemo(() => {
    const raw = settings?.modelCatalog ?? {};
    return {
      ollama: raw.ollama && raw.ollama.length > 0 ? raw.ollama : PROVIDER_MODEL_FALLBACKS.ollama,
      openai: raw.openai && raw.openai.length > 0 ? raw.openai : PROVIDER_MODEL_FALLBACKS.openai,
      gemini: raw.gemini && raw.gemini.length > 0 ? raw.gemini : PROVIDER_MODEL_FALLBACKS.gemini,
    };
  }, [settings]);

  const activeModelOptions = modelCatalog[activeProvider];
  const activeModelValue = settings ? getModelForProvider(settings, activeProvider) : "";
  const selectedActiveModel = activeModelOptions.includes(activeModelValue) ? activeModelValue : activeModelOptions[0];

  const openAIKeyConfigured = settings ? (settings.hasOpenAIApiKey ?? Boolean(settings.openAIApiKey?.trim())) : false;
  const geminiKeyConfigured = settings ? (settings.hasGeminiApiKey ?? Boolean(settings.geminiApiKey?.trim())) : false;

  const activeApiKeyConfigured =
    activeProvider === "openai" ? openAIKeyConfigured :
    activeProvider === "gemini" ? geminiKeyConfigured :
    true;
  const activeApiKeyMasked =
    activeProvider === "openai" ? maskApiKey(settings?.openAIApiKey) :
    activeProvider === "gemini" ? maskApiKey(settings?.geminiApiKey) :
    null;

  return (
    <AppShell
      current="/settings"
      eyebrow="Settings & Prompts"
      title="Global Configuration"
      summary="Manage your API keys, model preferences, and the system prompts used by automations."
    >
      {message && <p className="jobs-live__meta" style={{ marginBottom: "1rem" }}>{message}</p>}
      
      <div style={{ display: "flex", gap: "1rem", borderBottom: "1px solid var(--line)", paddingBottom: "0.5rem", marginBottom: "2rem" }}>
        <button type="button" className={`shell__nav-link ${activeTab === 'global' ? 'shell__nav-link--active' : ''}`} onClick={() => setActiveTab('global')}>
          Global Configuration
        </button>
        <button type="button" className={`shell__nav-link ${activeTab === 'prompts' ? 'shell__nav-link--active' : ''}`} onClick={() => setActiveTab('prompts')}>
          System Prompts
        </button>
      </div>
      
      {activeTab === 'global' && (
        <div className="panel jobs-controls">
          <div className="panel__header">
            <h3>Global Settings</h3>
            <span>API keys and Model Preferences</span>
          </div>
          {settings ? (
            <form onSubmit={handleSaveSettings} className="jobs-controls__fields" style={{ padding: "0 1.5rem 1.5rem" }}>
              <label className="jobs-controls__field">
                <span>Active Model Provider</span>
                <select
                  value={activeProvider}
                  onChange={(e) => {
                    const nextProvider = normalizeProvider(e.target.value);
                    const nextOptions = modelCatalog[nextProvider];
                    const currentValue = getModelForProvider(settings, nextProvider);
                    const nextValue = nextOptions.includes(currentValue) ? currentValue : nextOptions[0];

                    const nextSettings = setModelForProvider(
                      { ...settings, activeModelProvider: nextProvider },
                      nextProvider,
                      nextValue,
                    );
                    setSettings(nextSettings);
                  }}
                  style={{ width: "100%", padding: "8px", background: "var(--color-surface)", color: "var(--color-text)", border: "1px solid var(--color-border)", borderRadius: "6px" }}
                >
                  {(Object.keys(PROVIDER_LABELS) as ModelProvider[]).map((provider) => (
                    <option key={provider} value={provider}>
                      {PROVIDER_LABELS[provider]}
                    </option>
                  ))}
                </select>
              </label>

              <label className="jobs-controls__field">
                <span>{PROVIDER_LABELS[activeProvider]} Model Picker</span>
                <select
                  value={selectedActiveModel}
                  onChange={(e) => setSettings(setModelForProvider(settings, activeProvider, e.target.value))}
                  style={{ width: "100%", padding: "8px", background: "var(--color-surface)", color: "var(--color-text)", border: "1px solid var(--color-border)", borderRadius: "6px" }}
                >
                  {activeModelOptions.map((modelName) => (
                    <option key={modelName} value={modelName}>
                      {modelName}
                    </option>
                  ))}
                </select>
                <small className="shell__note">Only valid models for {PROVIDER_LABELS[activeProvider]} are shown.</small>
              </label>

              <div className="jobs-controls__field" style={{ background: "var(--surface-1)", border: "1px solid var(--line)", borderRadius: "10px", padding: "0.9rem" }}>
                <span style={{ display: "block", marginBottom: "0.3rem", fontWeight: 600 }}>API Key In Global Settings</span>
                {activeProvider === "ollama" ? (
                  <p className="shell__note" style={{ margin: 0 }}>No API key required for local Ollama.</p>
                ) : (
                  <p className="shell__note" style={{ margin: 0 }}>
                    {activeApiKeyConfigured ? `Configured (${activeApiKeyMasked ?? "masked"})` : "Not configured yet"}
                  </p>
                )}
              </div>

              {activeProvider === "openai" && (
                <label className="jobs-controls__field">
                  <span>OpenAI API Key</span>
                  <input
                    type="password"
                    value={settings.openAIApiKey || ""}
                    onChange={(e) => setSettings({ ...settings, openAIApiKey: e.target.value })}
                    placeholder="sk-..."
                  />
                </label>
              )}

              {activeProvider === "gemini" && (
                <label className="jobs-controls__field">
                  <span>Gemini API Key</span>
                  <input
                    type="password"
                    value={settings.geminiApiKey || ""}
                    onChange={(e) => setSettings({ ...settings, geminiApiKey: e.target.value })}
                    placeholder="AIza..."
                  />
                </label>
              )}

              <div className="jobs-controls__field">
                <span>Provider Key Status</span>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.6rem" }}>
                  <div style={{ border: "1px solid var(--line)", borderRadius: "8px", padding: "0.65rem" }}>
                    <strong>OpenAI</strong>
                    <p className="shell__note" style={{ margin: "0.35rem 0 0" }}>
                      {openAIKeyConfigured ? `Configured (${maskApiKey(settings.openAIApiKey) ?? "masked"})` : "Not configured"}
                    </p>
                  </div>
                  <div style={{ border: "1px solid var(--line)", borderRadius: "8px", padding: "0.65rem" }}>
                    <strong>Gemini</strong>
                    <p className="shell__note" style={{ margin: "0.35rem 0 0" }}>
                      {geminiKeyConfigured ? `Configured (${maskApiKey(settings.geminiApiKey) ?? "masked"})` : "Not configured"}
                    </p>
                  </div>
                </div>
              </div>

              <div className="jobs-controls__actions" style={{ marginTop: "1rem", borderTop: "none", padding: "0" }}>
                <button type="submit" className="shell__nav-link" disabled={isSavingSettings}>
                  {isSavingSettings ? "Saving..." : "Save Settings"}
                </button>
              </div>
            </form>
          ) : (
            <p className="empty-state">Loading settings...</p>
          )}
        </div>
      )}

      {activeTab === 'prompts' && (
        <div className="panel jobs-live">
          <div className="panel__header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h3>System Prompts</h3>
              <span>Edit the prompts used by the workers</span>
            </div>
            <button className="shell__nav-link" onClick={() => setIsCreatingPrompt(!isCreatingPrompt)}>
              {isCreatingPrompt ? "Cancel" : "Add Prompt"}
            </button>
          </div>
          
          <div className="table-scroll" style={{ padding: "0 1.5rem 1.5rem" }}>
            {isCreatingPrompt && (
              <form onSubmit={handleCreatePrompt} style={{ marginBottom: "2rem", padding: "1rem", border: "1px solid var(--line)", borderRadius: "6px" }}>
                 <h4 style={{ marginBottom: "1rem" }}>Create New Prompt</h4>
                 <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                   <input required placeholder="Prompt Key (e.g. email_generation)" value={newPromptData.key} onChange={e => setNewPromptData({...newPromptData, key: e.target.value})} style={{ padding: "8px", background: "var(--color-surface)", color: "var(--color-text)", border: "1px solid var(--color-border)", borderRadius: "6px" }} />
                   <input required placeholder="Brief Description" value={newPromptData.description} onChange={e => setNewPromptData({...newPromptData, description: e.target.value})} style={{ padding: "8px", background: "var(--color-surface)", color: "var(--color-text)", border: "1px solid var(--color-border)", borderRadius: "6px" }} />
                   <textarea rows={4} required placeholder="You are a helpful assistant..." value={newPromptData.promptText} onChange={e => setNewPromptData({...newPromptData, promptText: e.target.value})} style={{ padding: "12px", background: "var(--color-surface)", color: "var(--color-text)", border: "1px solid var(--color-border)", borderRadius: "6px", fontFamily: "monospace" }} />
                   <button type="submit" className="shell__nav-link" disabled={isSavingSettings} style={{ alignSelf: "flex-start" }}>
                     {isSavingSettings ? "Creating..." : "Save New Prompt"}
                   </button>
                 </div>
              </form>
            )}

            {prompts.length === 0 ? (
              <p className="empty-state">Loading prompts...</p>
            ) : (
              <table className="data-table jobs-table">
                <thead>
                  <tr>
                    <th>Key</th>
                    <th>Description</th>
                    <th>Last Updated</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {prompts.map(prompt => (
                    <tr key={prompt.id} className="jobs-table__row">
                      <td style={{ verticalAlign: "top" }}>
                         <strong>{prompt.key}</strong>
                      </td>
                      <td style={{ verticalAlign: "top", width: "50%" }}>
                        {editingPromptId === prompt.id ? (
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                            <textarea 
                              value={editPromptText}
                              rows={8}
                              style={{ width: "100%", padding: "12px", background: "var(--color-surface)", color: "var(--color-text)", border: "1px solid var(--color-border)", borderRadius: "6px", fontFamily: "monospace", fontSize: "14px", resize: "vertical" }}
                              onChange={(e) => setEditPromptText(e.target.value)}
                            />
                            <div style={{ display: "flex", gap: "0.5rem" }}>
                              <button className="shell__nav-link" onClick={() => handleSavePrompt(prompt.id)} disabled={savingPromptId === prompt.id}>
                                {savingPromptId === prompt.id ? "Saving..." : "Keep Edit"}
                              </button>
                              <button className="shell__nav-link" onClick={() => setEditingPromptId(null)}>Cancel</button>
                            </div>
                          </div>
                        ) : (
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                            <p className="shell__note" style={{ margin: 0 }}>{prompt.description}</p>
                            <pre style={{ margin: 0, whiteSpace: "pre-wrap", background: "rgba(0,0,0,0.1)", padding: "0.5rem", borderRadius: "4px", fontSize: "0.85rem" }}>
                              {prompt.promptText.length > 150 ? prompt.promptText.substring(0, 150) + "..." : prompt.promptText}
                            </pre>
                          </div>
                        )}
                      </td>
                      <td style={{ verticalAlign: "top" }}>{new Date(prompt.updatedAt).toLocaleDateString()}</td>
                      <td style={{ verticalAlign: "top" }}>
                        <div style={{ display: "flex", gap: "0.5rem" }}>
                          <button className="shell__nav-link" onClick={() => { setEditingPromptId(prompt.id); setEditPromptText(prompt.promptText); }}>Edit</button>
                          <button className="shell__nav-link" style={{ color: "var(--color-failed)" }} onClick={() => handleDeletePrompt(prompt.id)} disabled={deletingPromptId === prompt.id}>
                            {deletingPromptId === prompt.id ? "..." : "Delete"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </AppShell>
  );
}
