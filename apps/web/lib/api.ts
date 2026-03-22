export type KpiCard = {
  label: string;
  value: number | string;
  hint: string;
};

export type OverviewResponse = {
  generatedAt: string;
  kpis: KpiCard[];
  recentJobs: Array<{
    id: string;
    type: string;
    status: string;
    provider: string;
    createdAt: string;
    completedAt?: string | null;
  }>;
  activeAccounts: Array<{
    id: string;
    provider: string;
    nickname: string;
    lastActiveAt?: string | null;
    lastFailureAt?: string | null;
    lastError?: string | null;
  }>;
};

export type JobItem = {
  id: string;
  type: string;
  status: string;
  provider: string;
  accountId?: string | null;
  productId?: string | null;
  model?: string | null;
  createdAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
  errorMessage?: string | null;
};

export type JobEventItem = {
  id: number;
  level: string;
  step: string;
  message: string;
  createdAt: string;
};

export type JobDetailsItem = JobItem & {
  payloadJson?: string | null;
  resultJson?: string | null;
  events: JobEventItem[];
};

export type QueueJobRequest = {
  type: string;
  provider?: string | null;
  accountId?: string | null;
  productId?: string | null;
  model?: string | null;
  parameters?: Record<string, string | null>;
};

export type AccountItem = {
  id: string;
  provider: string;
  nickname: string;
  topic?: string | null;
  niche?: string | null;
  language?: string | null;
  lastActiveAt?: string | null;
  lastFailureAt?: string | null;
  lastError?: string | null;
  assetCount: number;
};

export type ContentItem = {
  id: string;
  kind: string;
  provider: string;
  accountId: string;
  title: string;
  description?: string | null;
  url?: string | null;
  localPath?: string | null;
  views?: number | null;
  clicks?: number | null;
  revenue?: number | null;
  cost?: number | null;
  publishedAt: string;
};

export type AffiliateOverview = {
  products: Array<{
    id: string;
    affiliateLink: string;
    accountId?: string | null;
    accountNickname?: string | null;
    name?: string | null;
    createdAt: string;
  }>;
  revenue: Array<{
    productId: string;
    revenue: number;
    clicks: number;
    conversions: number;
  }>;
};

export type ProfitResponse = {
  revenue: Array<{
    id: string;
    source: string;
    productId?: string | null;
    amount: number;
    currency: string;
    clicks?: number | null;
    conversions?: number | null;
    notes?: string | null;
    occurredAt: string;
  }>;
  cost: Array<{
    id: string;
    jobId?: string | null;
    category: string;
    amount: number;
    currency: string;
    notes?: string | null;
    occurredAt: string;
  }>;
  totals: {
    revenue: number;
    cost: number;
    profit: number;
  };
};

export type OutreachLeadItem = {
  id: string;
  title: string;
  category: string;
  address: string;
  website?: string | null;
  phone?: string | null;
  plusCode?: string | null;
  reviewCount?: string | null;
  reviewRating?: string | null;
  email?: string | null;
  status: "ready" | "website_only" | "missing_contact";
};

export type OutreachLeadsResponse = {
  generatedAt: string;
  sourcePath: string;
  leadCount: number;
  readyCount: number;
  websiteOnlyCount: number;
  missingContactCount: number;
  rows: OutreachLeadItem[];
};

const API_BASE_URL = process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:5050";

async function readJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      cache: "no-store",
      next: { revalidate: 0 },
    });

    if (!response.ok) {
      throw new Error(`Failed to load ${path}: ${response.status}`);
    }

    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export async function readOverview(): Promise<OverviewResponse> {
  return readJson("/api/overview", {
    generatedAt: new Date().toISOString(),
    kpis: [],
    recentJobs: [],
    activeAccounts: [],
  });
}

export async function readJobs(): Promise<JobItem[]> {
  return readJson<JobItem[]>("/api/jobs", []);
}

export async function queueJob(request: QueueJobRequest): Promise<{ jobId: string; status: string }> {
  const response = await fetch(`${API_BASE_URL}/api/jobs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Could not queue job: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as { jobId: string; status: string };
}

export async function cancelJob(jobId: string): Promise<{ jobId: string; status: string }> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/cancel`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`Could not cancel job ${jobId}: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as { jobId: string; status: string };
}

export async function readJobDetails(jobId: string): Promise<JobDetailsItem | null> {
  return readJson<JobDetailsItem | null>(`/api/jobs/${jobId}`, null);
}

export async function readAccounts(): Promise<AccountItem[]> {
  return readJson<AccountItem[]>("/api/accounts", []);
}

export async function readContent(): Promise<ContentItem[]> {
  return readJson<ContentItem[]>("/api/content", []);
}

export async function readAffiliateOverview(): Promise<AffiliateOverview> {
  return readJson("/api/affiliate/overview", { products: [], revenue: [] });
}

export async function readProfit(): Promise<ProfitResponse> {
  return readJson("/api/profit", {
    revenue: [],
    cost: [],
    totals: {
      revenue: 0,
      cost: 0,
      profit: 0,
    },
  });
}

export async function readOutreachLeads(): Promise<OutreachLeadsResponse> {
  return readJson("/api/outreach/leads", {
    generatedAt: new Date().toISOString(),
    sourcePath: "",
    leadCount: 0,
    readyCount: 0,
    websiteOnlyCount: 0,
    missingContactCount: 0,
    rows: [],
  });
}

export function formatDate(value?: string | null): string {
  if (!value) {
    return "Not yet";
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatMoney(value: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

export type GlobalSettings = {
  openAIApiKey?: string | null;
  geminiApiKey?: string | null;
  hasOpenAIApiKey?: boolean;
  hasGeminiApiKey?: boolean;
  activeProviderApiKeyConfigured?: boolean;
  activeProviderApiKeyMasked?: string | null;
  activeModelProvider: string;
  ollamaModelName: string;
  openAIModelName: string;
  geminiModelName: string;
  modelCatalog?: Record<string, string[]>;
};

export type SystemPrompt = {
  id: string;
  key: string;
  description: string;
  promptText: string;
  updatedAt: string;
};

export async function readSettings(): Promise<GlobalSettings> {
  return readJson<GlobalSettings>("/api/settings", {
    activeModelProvider: "ollama",
    ollamaModelName: "llama3.2:3b",
    openAIModelName: "gpt-4o-mini",
    geminiModelName: "gemini-2.5-flash",
    modelCatalog: {
      ollama: ["llama3.2:3b", "llama3.2:1b", "qwen2.5:7b", "mistral:7b", "gemma2:9b"],
      openai: ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1", "gpt-4o"],
      gemini: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
    },
  });
}

export async function saveSettings(settings: Partial<GlobalSettings>): Promise<GlobalSettings> {
  const response = await fetch(`${API_BASE_URL}/api/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!response.ok) throw new Error("Could not save settings");
  return response.json() as Promise<GlobalSettings>;
}

export async function readPrompts(): Promise<SystemPrompt[]> {
  return readJson<SystemPrompt[]>("/api/prompts", []);
}

export async function savePrompt(id: string, promptText: string): Promise<SystemPrompt> {
  const response = await fetch(`${API_BASE_URL}/api/prompts/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ promptText }),
  });
  if (!response.ok) throw new Error("Could not save prompt");
  return response.json() as Promise<SystemPrompt>;
}

export async function createPrompt(promptParams: { key: string; description: string; promptText: string }): Promise<SystemPrompt> {
  const response = await fetch(`${API_BASE_URL}/api/prompts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(promptParams),
  });
  if (!response.ok) throw new Error("Could not create prompt");
  return response.json() as Promise<SystemPrompt>;
}

export async function deletePrompt(id: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/prompts/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Could not delete prompt");
}
