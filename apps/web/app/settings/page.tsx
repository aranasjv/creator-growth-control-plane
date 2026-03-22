"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { readSettings, saveSettings, readPrompts, savePrompt, type GlobalSettings, type SystemPrompt } from "@/lib/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState<GlobalSettings | null>(null);
  const [prompts, setPrompts] = useState<SystemPrompt[]>([]);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [savingPromptId, setSavingPromptId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    readSettings().then(setSettings).catch(console.error);
    readPrompts().then(setPrompts).catch(console.error);
  }, []);

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

  const handleSavePrompt = async (promptId: string, promptText: string) => {
    setSavingPromptId(promptId);
    setMessage(null);
    try {
      await savePrompt(promptId, promptText);
      setMessage("Prompt saved successfully.");
      const updated = await readPrompts();
      setPrompts(updated);
    } catch (err) {
      setMessage("Failed to save prompt.");
    } finally {
      setSavingPromptId(null);
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
      
      <div className="jobs-live__grid jobs-live__grid--single" style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
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

        <div className="panel jobs-live">
          <div className="panel__header">
            <h3>System Prompts</h3>
            <span>Edit the prompts used by the workers</span>
          </div>
          
          <div className="table-scroll" style={{ padding: "0 1.5rem 1.5rem" }}>
            {prompts.length === 0 ? (
              <p className="empty-state">Loading prompts...</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
                {prompts.map(prompt => (
                  <div key={prompt.id} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                      <strong style={{ fontSize: "1.1rem" }}>{prompt.key}</strong>
                      <span className="jobs-live__meta" style={{ margin: 0 }}>Last updated: {new Date(prompt.updatedAt).toLocaleDateString()}</span>
                    </div>
                    <p className="shell__note" style={{ margin: 0 }}>{prompt.description}</p>
                    <textarea 
                      value={prompt.promptText}
                      rows={5}
                      style={{ width: "100%", padding: "12px", background: "var(--color-surface)", color: "var(--color-text)", border: "1px solid var(--color-border)", borderRadius: "6px", fontFamily: "monospace", fontSize: "14px", resize: "vertical" }}
                      onChange={(e) => {
                        const newPrompts = [...prompts];
                        const index = newPrompts.findIndex(p => p.id === prompt.id);
                        if (index !== -1) {
                          newPrompts[index].promptText = e.target.value;
                          setPrompts(newPrompts);
                        }
                      }}
                    />
                    <div style={{ display: "flex", gap: "1rem" }}>
                      <button 
                        className="shell__nav-link" 
                        onClick={() => handleSavePrompt(prompt.id, prompt.promptText)}
                        disabled={savingPromptId === prompt.id}
                      >
                        {savingPromptId === prompt.id ? "Saving..." : "Save Prompt"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
