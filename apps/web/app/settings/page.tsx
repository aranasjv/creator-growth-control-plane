"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { readSettings, saveSettings, readPrompts, savePrompt, createPrompt, deletePrompt, type GlobalSettings, type SystemPrompt } from "@/lib/api";

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
                  value={settings.activeModelProvider} 
                  onChange={(e) => setSettings({ ...settings, activeModelProvider: e.target.value })}
                  style={{ width: "100%", padding: "8px", background: "var(--color-surface)", color: "var(--color-text)", border: "1px solid var(--color-border)", borderRadius: "6px" }}
                >
                  <option value="ollama">Ollama (Local)</option>
                  <option value="openai">OpenAI</option>
                  <option value="gemini">Gemini</option>
                </select>
              </label>
              
              <label className="jobs-controls__field">
                <span>Ollama Model Name</span>
                <input 
                  value={settings.ollamaModelName || ""} 
                  onChange={(e) => setSettings({ ...settings, ollamaModelName: e.target.value })} 
                  placeholder="e.g. llama3" 
                />
              </label>

              <label className="jobs-controls__field">
                <span>OpenAI API Key</span>
                <input 
                  type="password"
                  value={settings.openAIApiKey || ""} 
                  onChange={(e) => setSettings({ ...settings, openAIApiKey: e.target.value })} 
                  placeholder="sk-..." 
                />
              </label>

              <label className="jobs-controls__field">
                <span>Gemini API Key</span>
                <input 
                  type="password"
                  value={settings.geminiApiKey || ""} 
                  onChange={(e) => setSettings({ ...settings, geminiApiKey: e.target.value })} 
                  placeholder="AIza..." 
                />
              </label>

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
