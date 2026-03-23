"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { JobDetailsItem, JobEventItem, JobItem } from "@/lib/api";
import { cancelJob, formatDate, queueJob, type QueueJobRequest } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:5050";
const EMAIL_PATTERN = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i;
const EMAIL_PREVIEW_PATTERN = /Email preview for\s+(.+?)\s+\|\s+Subject:\s*(.*?)\s+\|\s+Body:\s*(.*)$/i;
const NO_EMAIL_PATTERN = /No email provided for\s+(.+?)\.\s+Skipping/i;
const NO_WEBSITE_PATTERN = /No website for\s+(.+?)\.\s+Skipping/i;

const STEP_PROGRESS_WEIGHTS: Record<string, number> = {
  queued: 5,
  starting: 12,
  launch: 18,
  scraper: 35,
  scrape_niche: 50,
  scrape_result: 68,
  dry_run: 72,
  email_dry_run: 76,
  email_preview: 78,
  send_email: 84,
  email_sent: 90,
  email_failed: 88,
  email_skipped_no_email: 74,
  email_skipped_no_website: 70,
  email_skipped_website: 70,
  email_cap_reached: 86,
  milestone: 75,
  sync: 95,
  warning: 70,
  timeout: 72,
};

type JobsLiveMonitorProps = {
  initialJobs: JobItem[];
};

type JobsStreamSnapshot = {
  timestamp?: string;
  jobs?: JobItem[];
  selectedJob?: JobDetailsItem | null;
};

type OutreachEmailAttempt = {
  companyName?: string;
  website?: string;
  recipient?: string;
  status?: string;
  subject?: string;
  bodyPreview?: string;
  error?: string;
};

type OutreachOutput = {
  dryRun?: boolean;
  leadsScraped?: number;
  emailsPrepared?: number;
  emailsSent?: number;
  emailsFailed?: number;
  emailsSkippedNoEmail?: number;
  emailsSkippedInvalidWebsite?: number;
  emailSendCap?: number;
  emailSendCapReached?: boolean;
  emailAttempts?: OutreachEmailAttempt[];
};

type ParsedJobResult = {
  summary?: string;
  metrics?: Record<string, number | string | null | undefined>;
  output?: {
    outreach?: OutreachOutput | null;
  } | null;
};

type InspectorDialogState = {
  title: string;
  subtitle: string;
  fields: Array<{ label: string; value: string }>;
  body: string;
};

type DeliveryStatus = "sent" | "partial" | "not_sent" | "dry_run" | "no_attempt";

function chooseSelectedJobId(jobs: JobItem[], preferredId?: string | null, currentId?: string | null): string | null {
  if (preferredId && jobs.some((job) => job.id === preferredId)) {
    return preferredId;
  }

  if (currentId && jobs.some((job) => job.id === currentId)) {
    return currentId;
  }

  const runningJob = jobs.find((job) => job.status === "running");
  if (runningJob) {
    return runningJob.id;
  }

  return jobs[0]?.id ?? null;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

function parseJsonSafe<T>(value?: string | null): T | null {
  if (!value) {
    return null;
  }

  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}

function toNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function truncateText(value: string, maxLength = 200): string {
  const text = (value ?? "").trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength).trimEnd()}...`;
}

function getElapsedSeconds(job?: JobItem | null): number {
  if (!job?.startedAt) {
    return 0;
  }

  const startTime = new Date(job.startedAt).getTime();
  const endTime = job.completedAt ? new Date(job.completedAt).getTime() : Date.now();
  return Math.max(0, Math.floor((endTime - startTime) / 1000));
}

function getElapsedText(job?: JobItem | null): string {
  const seconds = getElapsedSeconds(job);
  if (!seconds) {
    return "Not started";
  }

  if (seconds < 60) {
    return `${seconds}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m ${remainder}s`;
}

function getProgressPercent(job?: JobDetailsItem | null): number {
  if (!job) {
    return 0;
  }

  if (job.status === "succeeded" || job.status === "failed" || job.status === "cancelled") {
    return 100;
  }

  let progress = job.status === "running" ? 12 : 5;
  for (const eventItem of job.events ?? []) {
    const weight = STEP_PROGRESS_WEIGHTS[eventItem.step] ?? STEP_PROGRESS_WEIGHTS[eventItem.level] ?? 0;
    if (weight > progress) {
      progress = weight;
    }
  }

  return Math.min(99, Math.max(0, progress));
}

function getEtaText(job: JobDetailsItem | null, progress: number): string {
  if (!job || job.status !== "running" || !job.startedAt) {
    return "No ETA needed";
  }

  if (progress < 10) {
    return "Calibrating";
  }

  const elapsedSeconds = getElapsedSeconds(job);
  if (!elapsedSeconds) {
    return "Calibrating";
  }

  const remainingSeconds = Math.round((elapsedSeconds * (100 - progress)) / progress);
  if (remainingSeconds <= 0) {
    return "Under 1 minute";
  }

  if (remainingSeconds < 60) {
    return `${remainingSeconds}s`;
  }

  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

function toStepLabel(step: string): string {
  return step
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function normalizeAttemptStatus(status?: string): string {
  return (status ?? "unknown").trim().toLowerCase();
}

function extractEmail(message: string): string {
  const match = message.match(EMAIL_PATTERN);
  return match ? match[0] : "";
}

function parsePreviewMessage(message: string): { recipient: string; subject: string; body: string } | null {
  const match = message.match(EMAIL_PREVIEW_PATTERN);
  if (!match) {
    return null;
  }

  return {
    recipient: match[1]?.trim() ?? "",
    subject: match[2]?.trim() ?? "",
    body: match[3]?.trim() ?? "",
  };
}

function buildAttemptsFromEvents(events: JobEventItem[]): OutreachEmailAttempt[] {
  const attemptsByKey = new Map<string, OutreachEmailAttempt>();
  const ordered = [...events].sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime());

  for (const eventItem of ordered) {
    const message = eventItem.message ?? "";
    const recipientFromMessage = extractEmail(message);
    const preview = parsePreviewMessage(message);

    if (preview) {
      const key = preview.recipient.toLowerCase();
      const existing = attemptsByKey.get(key) ?? {};
      attemptsByKey.set(key, {
        ...existing,
        recipient: preview.recipient,
        subject: preview.subject,
        bodyPreview: preview.body,
        status: existing.status ?? "previewed",
      });
      continue;
    }

    if (eventItem.step === "send_email" && recipientFromMessage) {
      const key = recipientFromMessage.toLowerCase();
      const existing = attemptsByKey.get(key) ?? {};
      attemptsByKey.set(key, {
        ...existing,
        recipient: recipientFromMessage,
        status: "sending",
      });
      continue;
    }

    if (eventItem.step === "email_sent" && recipientFromMessage) {
      const key = recipientFromMessage.toLowerCase();
      const existing = attemptsByKey.get(key) ?? {};
      attemptsByKey.set(key, {
        ...existing,
        recipient: recipientFromMessage,
        status: "sent",
      });
      continue;
    }

    if (eventItem.step === "email_failed" && recipientFromMessage) {
      const key = recipientFromMessage.toLowerCase();
      const existing = attemptsByKey.get(key) ?? {};
      attemptsByKey.set(key, {
        ...existing,
        recipient: recipientFromMessage,
        status: "failed",
        error: message,
      });
      continue;
    }

    const noEmailMatch = message.match(NO_EMAIL_PATTERN);
    if (eventItem.step === "email_skipped_no_email" || noEmailMatch) {
      const companyName = noEmailMatch?.[1]?.trim() ?? "";
      const key = companyName ? `company:${companyName.toLowerCase()}` : `event:${eventItem.id}`;
      const existing = attemptsByKey.get(key) ?? {};
      attemptsByKey.set(key, {
        ...existing,
        companyName,
        status: "skipped_no_email",
        error: message,
      });
      continue;
    }

    const noWebsiteMatch = message.match(NO_WEBSITE_PATTERN);
    if (eventItem.step === "email_skipped_no_website" || noWebsiteMatch) {
      const companyName = noWebsiteMatch?.[1]?.trim() ?? "";
      const key = companyName ? `company:${companyName.toLowerCase()}` : `event:${eventItem.id}`;
      const existing = attemptsByKey.get(key) ?? {};
      attemptsByKey.set(key, {
        ...existing,
        companyName,
        status: "skipped_no_website",
        error: message,
      });
      continue;
    }
  }

  return [...attemptsByKey.values()].reverse();
}

function isEmailErrorEvent(eventItem: JobEventItem): boolean {
  const lower = (eventItem.message ?? "").toLowerCase();
  if (eventItem.step === "email_failed") {
    return true;
  }
  return eventItem.level === "error" && lower.includes("email");
}

function getDeliveryStatusLabel(status: DeliveryStatus): string {
  switch (status) {
    case "sent":
      return "Sent";
    case "partial":
      return "Partially sent";
    case "not_sent":
      return "Not sent";
    case "dry_run":
      return "Dry run only";
    default:
      return "No attempts";
  }
}

export function JobsLiveMonitor({ initialJobs }: JobsLiveMonitorProps) {
  const [jobs, setJobs] = useState<JobItem[]>(initialJobs);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(chooseSelectedJobId(initialJobs));
  const [selectedJob, setSelectedJob] = useState<JobDetailsItem | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeDialog, setActiveDialog] = useState<InspectorDialogState | null>(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [activeDialogTab, setActiveDialogTab] = useState<"emails" | "timeline">("timeline");
  const [controlsBusy, setControlsBusy] = useState(false);
  const [controlsMessage, setControlsMessage] = useState<string | null>(null);
  const [outreachNiches, setOutreachNiches] = useState("pet shops");
  const [outreachMaxEmails, setOutreachMaxEmails] = useState("1");
  const [accountIdInput, setAccountIdInput] = useState("");
  const [productIdInput, setProductIdInput] = useState("");
  const [modelInput, setModelInput] = useState("");
  const [longformInput, setLongformInput] = useState("");

  const refreshState = useCallback(
    async (preferredJobId?: string | null) => {
      setIsRefreshing(true);
      setError(null);

      try {
        const nextJobs = await fetchJson<JobItem[]>("/api/jobs");
        const nextSelectedId = chooseSelectedJobId(nextJobs, preferredJobId, selectedJobId);

        setJobs(nextJobs);
        setSelectedJobId(nextSelectedId);

        if (nextSelectedId) {
          const details = await fetchJson<JobDetailsItem>(`/api/jobs/${nextSelectedId}`);
          setSelectedJob(details);
        } else {
          setSelectedJob(null);
        }

        setLastUpdatedAt(new Date().toISOString());
      } catch (refreshError) {
        const message = refreshError instanceof Error ? refreshError.message : "Unknown refresh error";
        setError(`Could not refresh live jobs view: ${message}`);
      } finally {
        setIsRefreshing(false);
      }
    },
    [selectedJobId],
  );

  useEffect(() => {
    void refreshState();
  }, [refreshState]);

  useEffect(() => {
    if (!autoRefresh) {
      return;
    }

    const query = selectedJobId ? `?jobId=${selectedJobId}` : "";
    const eventSource = new EventSource(`${API_BASE_URL}/api/jobs/stream${query}`);

    eventSource.addEventListener("jobs", (rawEvent) => {
      try {
        const event = rawEvent as MessageEvent<string>;
        const snapshot = JSON.parse(event.data) as JobsStreamSnapshot;

        if (Array.isArray(snapshot.jobs)) {
          setJobs(snapshot.jobs);
        }
        if (snapshot.selectedJob !== undefined) {
          setSelectedJob(snapshot.selectedJob ?? null);
        }

        setLastUpdatedAt(snapshot.timestamp ?? new Date().toISOString());
        setIsRefreshing(false);
        setError(null);
      } catch (streamError) {
        const message = streamError instanceof Error ? streamError.message : "Unknown stream parsing issue";
        setError(`Live stream parsing failed: ${message}`);
      }
    });

    eventSource.onerror = () => {
      setError("Live stream disconnected. Waiting for reconnect...");
    };

    return () => {
      eventSource.close();
    };
  }, [autoRefresh, selectedJobId]);

  const metrics = useMemo(() => {
    const running = jobs.filter((job) => job.status === "running").length;
    const failed = jobs.filter((job) => job.status === "failed").length;
    const succeeded = jobs.filter((job) => job.status === "succeeded").length;
    return { running, failed, succeeded };
  }, [jobs]);

  const sortedEvents = useMemo(() => {
    if (!selectedJob) {
      return [];
    }
    return [...selectedJob.events].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }, [selectedJob]);

  const parsedResult = useMemo(
    () => parseJsonSafe<ParsedJobResult>(selectedJob?.resultJson),
    [selectedJob?.resultJson],
  );

  const outreachOutput = useMemo(() => parsedResult?.output?.outreach ?? null, [parsedResult]);

  const emailAttempts = useMemo(() => {
    const fromOutput = outreachOutput?.emailAttempts ?? [];
    if (fromOutput.length > 0) {
      return fromOutput;
    }
    return buildAttemptsFromEvents(selectedJob?.events ?? []);
  }, [outreachOutput, selectedJob]);

  const progress = useMemo(() => getProgressPercent(selectedJob), [selectedJob]);
  const etaText = useMemo(() => getEtaText(selectedJob, progress), [selectedJob, progress]);

  const scrapeEvents = useMemo(
    () =>
      sortedEvents.filter((eventItem) =>
        ["scrape_niche", "scraper", "scrape_result"].includes(eventItem.step),
      ),
    [sortedEvents],
  );

  const preparedCount = useMemo(() => {
    const explicit = toNumber(outreachOutput?.emailsPrepared ?? parsedResult?.metrics?.emailsPrepared);
    if (explicit > 0) {
      return explicit;
    }
    return emailAttempts.filter((attempt) =>
      ["sent", "failed", "dry_run", "sending", "previewed"].includes(normalizeAttemptStatus(attempt.status)),
    ).length;
  }, [emailAttempts, outreachOutput, parsedResult]);

  const sentCount = useMemo(() => {
    const explicit = toNumber(outreachOutput?.emailsSent ?? parsedResult?.metrics?.emailsSent);
    if (explicit > 0) {
      return explicit;
    }
    return sortedEvents.filter((eventItem) => eventItem.step === "email_sent").length;
  }, [outreachOutput, parsedResult, sortedEvents]);

  const failedCount = useMemo(() => {
    const explicit = toNumber(outreachOutput?.emailsFailed ?? parsedResult?.metrics?.emailsFailed);
    if (explicit > 0) {
      return explicit;
    }
    return sortedEvents.filter((eventItem) => eventItem.step === "email_failed").length;
  }, [outreachOutput, parsedResult, sortedEvents]);

  const initiatedCount = useMemo(() => {
    const fromEvents = sortedEvents.filter((eventItem) => eventItem.step === "send_email").length;
    return Math.max(fromEvents, sentCount + failedCount);
  }, [failedCount, sentCount, sortedEvents]);

  const deliveryStatus = useMemo<DeliveryStatus>(() => {
    if (outreachOutput?.dryRun) {
      return "dry_run";
    }
    if (sentCount > 0 && failedCount > 0) {
      return "partial";
    }
    if (sentCount > 0 && initiatedCount > sentCount) {
      return "partial";
    }
    if (sentCount > 0) {
      return "sent";
    }
    if (initiatedCount > 0 || failedCount > 0) {
      return "not_sent";
    }
    return "no_attempt";
  }, [failedCount, initiatedCount, outreachOutput?.dryRun, sentCount]);

  const latestEmailError = useMemo(
    () => sortedEvents.find((eventItem) => isEmailErrorEvent(eventItem)),
    [sortedEvents],
  );
  const timelinePreviewEvents = useMemo(() => sortedEvents.slice(0, 30), [sortedEvents]);

  const openEventDialog = useCallback((eventItem: JobEventItem) => {
    setActiveDialog({
      title: toStepLabel(eventItem.step),
      subtitle: `${eventItem.level.toUpperCase()} | ${formatDate(eventItem.createdAt)}`,
      fields: [
        { label: "Level", value: eventItem.level },
        { label: "Step", value: eventItem.step },
        { label: "Created", value: formatDate(eventItem.createdAt) },
      ],
      body: eventItem.message,
    });
  }, []);

  const openAttemptDialog = useCallback((attempt: OutreachEmailAttempt) => {
    setActiveDialog({
      title: `Email ${toStepLabel(normalizeAttemptStatus(attempt.status))}`,
      subtitle: attempt.recipient || attempt.companyName || "Outreach email detail",
      fields: [
        { label: "Status", value: normalizeAttemptStatus(attempt.status) },
        { label: "Recipient", value: attempt.recipient || "Not resolved" },
        { label: "Company", value: attempt.companyName || "-" },
        { label: "Website", value: attempt.website || "-" },
        { label: "Subject", value: attempt.subject || "-" },
      ],
      body: attempt.bodyPreview || attempt.error || "No body preview captured for this attempt.",
    });
  }, []);

  const openInspector = useCallback(
    async (jobId: string) => {
      await refreshState(jobId);
      setIsInspectorOpen(true);
    },
    [refreshState],
  );

  const queuePresetJob = useCallback(
    async (preset: "smoke_test" | "outreach_dry" | "outreach_live" | "twitter_post" | "youtube_upload" | "youtube_upload_longform" | "afm_pitch") => {
      try {
        setControlsBusy(true);
        setControlsMessage(null);

        if ((preset === "twitter_post" || preset === "youtube_upload" || preset === "youtube_upload_longform") && !accountIdInput.trim()) {
          setControlsMessage("Account ID is required for Twitter and YouTube jobs.");
          return;
        }

        if (preset === "afm_pitch" && !productIdInput.trim()) {
          setControlsMessage("Product ID is required for Affiliate pitch jobs.");
          return;
        }

        let payload: QueueJobRequest;
        if (preset === "smoke_test") {
          payload = {
            type: "smoke_test",
            provider: "system",
            model: modelInput.trim() || null,
            parameters: {
              source: "jobs-dashboard",
            },
          };
        } else if (preset === "outreach_dry" || preset === "outreach_live") {
          payload = {
            type: "outreach_run",
            provider: "outreach",
            model: modelInput.trim() || null,
            parameters: {
              source: "jobs-dashboard",
              mode: preset === "outreach_live" ? "live" : "dry-run",
              niche: outreachNiches.trim() || "pet shops",
              niches: outreachNiches.trim() || "pet shops",
              maxEmails: outreachMaxEmails.trim() || "1",
            },
          };
        } else if (preset === "twitter_post") {
          payload = {
            type: "twitter_post",
            provider: "twitter",
            accountId: accountIdInput.trim(),
            model: modelInput.trim() || null,
            parameters: {
              source: "jobs-dashboard",
            },
          };
        } else if (preset === "youtube_upload") {
          payload = {
            type: "youtube_upload",
            provider: "youtube",
            accountId: accountIdInput.trim(),
            model: modelInput.trim() || null,
            parameters: {
              source: "jobs-dashboard",
              timeoutSeconds: "10800",
            },
          };
        } else if (preset === "youtube_upload_longform") {
          payload = {
            type: "youtube_upload",
            provider: "youtube",
            accountId: accountIdInput.trim(),
            model: modelInput.trim() || null,
            parameters: {
              source: "jobs-dashboard",
              use_longform: true,
              longform_content: longformInput.trim(),
              timeoutSeconds: "14400",
            },
          };
        } else {
          payload = {
            type: "afm_pitch",
            provider: "affiliate",
            productId: productIdInput.trim(),
            model: modelInput.trim() || null,
            parameters: {
              source: "jobs-dashboard",
            },
          };
        }

        const queued = await queueJob(payload);
        setControlsMessage(`Queued ${payload.type} as ${queued.jobId.slice(0, 8)}.`);
        await refreshState(queued.jobId);
        setIsInspectorOpen(true);
      } catch (queueError) {
        const message = queueError instanceof Error ? queueError.message : "Unknown queue error";
        setControlsMessage(`Could not queue job: ${message}`);
      } finally {
        setControlsBusy(false);
      }
    },
    [accountIdInput, modelInput, longformInput, outreachMaxEmails, outreachNiches, productIdInput, refreshState],
  );

  const stopSelectedJob = useCallback(async () => {
    if (!selectedJobId) {
      setControlsMessage("Select a job first, then press Stop selected.");
      return;
    }

    try {
      setControlsBusy(true);
      setControlsMessage(null);
      const cancelled = await cancelJob(selectedJobId);
      setControlsMessage(`Stop requested for ${cancelled.jobId.slice(0, 8)}. Status: ${cancelled.status}.`);
      await refreshState(selectedJobId);
    } catch (cancelError) {
      const message = cancelError instanceof Error ? cancelError.message : "Unknown cancel error";
      setControlsMessage(`Could not stop selected job: ${message}`);
    } finally {
      setControlsBusy(false);
    }
  }, [refreshState, selectedJobId]);

  return (
    <section className="panel jobs-live">
      <div className="panel__header">
        <h3>Live job monitor</h3>
        <span>{jobs.length} jobs tracked</span>
      </div>

      <div className="jobs-live__toolbar">
        <div className="mini-kpis">
          <div>
            <span>Running</span>
            <strong>{metrics.running}</strong>
          </div>
          <div>
            <span>Succeeded</span>
            <strong>{metrics.succeeded}</strong>
          </div>
          <div>
            <span>Failed</span>
            <strong>{metrics.failed}</strong>
          </div>
        </div>
        <div className="jobs-live__controls">
          <button className="shell__nav-link" type="button" aria-pressed={autoRefresh} onClick={() => setAutoRefresh((value) => !value)}>
            {autoRefresh ? "Live stream on" : "Live stream off"}
          </button>
          <button className="shell__nav-link" type="button" onClick={() => void refreshState(selectedJobId)}>
            Refresh now
          </button>
          <p className="jobs-live__meta">
            {isRefreshing ? "Refreshing..." : autoRefresh ? "Streaming live" : "Manual mode"} | Last update{" "}
            {lastUpdatedAt ? formatDate(lastUpdatedAt) : "pending"}
          </p>
        </div>
      </div>

      {error ? <p className="empty-state">{error}</p> : null}

      <article className="panel jobs-controls">
        <div className="panel__header">
          <h3>Backend controls</h3>
          <span>Queue and stop jobs</span>
        </div>
        <div className="jobs-controls__fields">
          <label className="jobs-controls__field">
            <span>Outreach niches</span>
            <input value={outreachNiches} onChange={(event) => setOutreachNiches(event.target.value)} placeholder="pet shops, dental clinics" />
          </label>
          <label className="jobs-controls__field">
            <span>Outreach max emails</span>
            <input value={outreachMaxEmails} onChange={(event) => setOutreachMaxEmails(event.target.value)} placeholder="1" />
          </label>
          <label className="jobs-controls__field">
            <span>Account ID (X/YouTube)</span>
            <input value={accountIdInput} onChange={(event) => setAccountIdInput(event.target.value)} placeholder="account uuid" />
          </label>
          <label className="jobs-controls__field">
            <span>Product ID (Affiliate)</span>
            <input value={productIdInput} onChange={(event) => setProductIdInput(event.target.value)} placeholder="product uuid" />
          </label>
          <label className="jobs-controls__field">
            <span>Model (optional)</span>
            <input value={modelInput} onChange={(event) => setModelInput(event.target.value)} placeholder="model name" />
          </label>
          <label className="jobs-controls__field">
            <span>Longform source (for shorts)</span>
            <textarea
              rows={3}
              value={longformInput}
              onChange={(event) => setLongformInput(event.target.value)}
              placeholder="Paste source script or article for conversion..."
            />
          </label>
        </div>
        <div className="jobs-controls__actions">
          <button className="shell__nav-link" type="button" disabled={controlsBusy} onClick={() => void queuePresetJob("smoke_test")}>
            Run smoke test
          </button>
          <button className="shell__nav-link" type="button" disabled={controlsBusy} onClick={() => void queuePresetJob("outreach_dry")}>
            Run outreach dry
          </button>
          <button className="shell__nav-link" type="button" disabled={controlsBusy} onClick={() => void queuePresetJob("outreach_live")}>
            Run outreach live
          </button>
          <button className="shell__nav-link" type="button" disabled={controlsBusy} onClick={() => void queuePresetJob("twitter_post")}>
            Run Twitter post
          </button>
          <button className="shell__nav-link" type="button" disabled={controlsBusy} onClick={() => void queuePresetJob("youtube_upload")}>
            Run YouTube upload
          </button>
          <button className="shell__nav-link" type="button" disabled={controlsBusy} onClick={() => void queuePresetJob("youtube_upload_longform")}>
            Run Longform Short
          </button>
          <button className="shell__nav-link" type="button" disabled={controlsBusy} onClick={() => void queuePresetJob("afm_pitch")}>
            Run Affiliate pitch
          </button>
          <button className="shell__nav-link" type="button" disabled={controlsBusy || !selectedJobId} onClick={() => void stopSelectedJob()}>
            Stop selected
          </button>
          <button className="shell__nav-link" type="button" disabled={controlsBusy || !selectedJobId} onClick={() => setIsInspectorOpen(true)}>
            Open inspector
          </button>
        </div>
        <p className="jobs-live__meta">
          {controlsBusy ? "Working on control action..." : controlsMessage ?? "Use the controls to trigger every backend job type or stop the selected job."}
        </p>
      </article>

      <div className="jobs-live__grid jobs-live__grid--single">
        <div className="jobs-live__left">
          <div className="table-scroll">
            <table className="data-table jobs-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Provider</th>
                  <th>Created</th>
                  <th>Elapsed</th>
                  <th>Inspect</th>
                </tr>
              </thead>
              <tbody>
                {jobs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="empty-state">
                      No jobs have been written to the orchestrator yet.
                    </td>
                  </tr>
                ) : null}
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    className={selectedJobId === job.id ? "jobs-table__row jobs-table__row--active" : "jobs-table__row"}
                    onClick={() => void openInspector(job.id)}
                  >
                    <td>{job.type}</td>
                    <td>
                      <span className={`status-pill status-pill--${job.status}`}>{job.status}</span>
                    </td>
                    <td>{job.provider}</td>
                    <td>{formatDate(job.createdAt)}</td>
                    <td>{getElapsedText(job)}</td>
                    <td>
                      <button
                        className="shell__nav-link jobs-table__inspect"
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          void openInspector(job.id);
                        }}
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <article className="panel panel--compact live-scrape">
            <div className="panel__header">
              <h3>Scrape trace</h3>
              <span>{scrapeEvents.length} events</span>
            </div>
            <div className="stack-list live-scrape__list">
              {scrapeEvents.length === 0 ? <p className="empty-state">No scrape events for this job yet.</p> : null}
              {scrapeEvents.map((eventItem) => (
                <button
                  key={eventItem.id}
                  type="button"
                  className="event-card"
                  onClick={() => openEventDialog(eventItem)}
                >
                  <div className="event-card__content">
                    <p className="stack-list__title">{toStepLabel(eventItem.step)}</p>
                    <p className="stack-list__meta">{truncateText(eventItem.message, 180)}</p>
                  </div>
                  <div className="event-card__meta">
                    <span className={`status-pill status-pill--${eventItem.level}`}>{eventItem.level}</span>
                    <span className="stack-list__meta">{formatDate(eventItem.createdAt)}</span>
                  </div>
                </button>
              ))}
            </div>
          </article>
        </div>
      </div>

      {isInspectorOpen ? (
        <div className="inspector-dialog" role="dialog" aria-modal="true">
          <article className="inspector-dialog__surface inspector-dialog__surface--wide live-feed">
            <div className="panel__header">
              <h3>Job inspector</h3>
              <button className="shell__nav-link" type="button" onClick={() => setIsInspectorOpen(false)}>
                Close
              </button>
            </div>
            <p className="stack-list__meta">
              Job {selectedJob?.id ? selectedJob.id.slice(0, 8) : "none"} | Status {selectedJob ? selectedJob.status : "unknown"} | Started{" "}
              {formatDate(selectedJob?.startedAt)} | Completed {formatDate(selectedJob?.completedAt)}
            </p>
            <p className="stack-list__meta">Provider {selectedJob?.provider ?? "-"} | Runtime {getElapsedText(selectedJob)}</p>

            <div className="job-progress">
              <div className="job-progress__header">
                <span>Progress</span>
                <strong>{progress}%</strong>
              </div>
              <div className="job-progress__track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}>
                <div className="job-progress__fill" style={{ width: `${progress}%` }} />
              </div>
              <p className="stack-list__meta">ETA {etaText}</p>
            </div>

            <div className="delivery-grid">
              <div className="delivery-card">
                <p className="kpi-card__label">Email delivery</p>
                <p className="delivery-card__value">
                  <span className={`status-pill status-pill--${deliveryStatus}`}>{getDeliveryStatusLabel(deliveryStatus)}</span>
                </p>
                <p className="stack-list__meta">Prepared {preparedCount} | Sent {sentCount} | Failed {failedCount}</p>
                <p className="stack-list__meta">Send attempts {initiatedCount}</p>
              </div>
              <div className="delivery-card">
                <p className="kpi-card__label">Scrape totals</p>
                <p className="delivery-card__value">{toNumber(outreachOutput?.leadsScraped || parsedResult?.metrics?.leadsScraped)}</p>
                <p className="stack-list__meta">
                  No email {toNumber(outreachOutput?.emailsSkippedNoEmail)} | Website issues {toNumber(outreachOutput?.emailsSkippedInvalidWebsite)}
                </p>
                <p className="stack-list__meta">
                  Send cap {toNumber(outreachOutput?.emailSendCap)} {outreachOutput?.emailSendCapReached ? "(reached)" : ""}
                </p>
              </div>
            </div>

            {latestEmailError ? (
              <p className="profile-card__error">Latest email error: {truncateText(latestEmailError.message, 220)}</p>
            ) : null}
            {selectedJob?.errorMessage ? <p className="profile-card__error">{truncateText(selectedJob.errorMessage, 260)}</p> : null}

            <div className="inspector-tabs">
              <button
                type="button"
                className={`shell__nav-link ${activeDialogTab === "timeline" ? "shell__nav-link--active" : ""}`}
                onClick={() => setActiveDialogTab("timeline")}
              >
                Timeline ({timelinePreviewEvents.length} / {sortedEvents.length})
              </button>
              <button
                type="button"
                className={`shell__nav-link ${activeDialogTab === "emails" ? "shell__nav-link--active" : ""}`}
                onClick={() => setActiveDialogTab("emails")}
              >
                Email Attempts ({emailAttempts.length})
              </button>
            </div>

            {activeDialogTab === "emails" && (
              <div className="stack-list live-feed__list">
                {emailAttempts.length === 0 ? (
                  <p className="empty-state">No email attempt details captured for this job yet.</p>
                ) : null}
                {emailAttempts.map((attempt, index) => (
                  <button
                    key={`${attempt.recipient ?? attempt.companyName ?? "attempt"}-${index}`}
                    type="button"
                    className="event-card"
                    onClick={() => openAttemptDialog(attempt)}
                  >
                    <div className="event-card__content">
                      <p className="stack-list__title">{attempt.recipient || attempt.companyName || "Unknown recipient"}</p>
                      <p className="stack-list__meta">{truncateText(attempt.subject || attempt.error || "No subject captured.", 160)}</p>
                    </div>
                    <div className="event-card__meta">
                      <span className={`status-pill status-pill--${normalizeAttemptStatus(attempt.status)}`}>
                        {normalizeAttemptStatus(attempt.status).replace(/_/g, " ")}
                      </span>
                      <span className="stack-list__meta">{attempt.website || "-"}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {activeDialogTab === "timeline" && (
              <div className="stack-list live-feed__list">
                {sortedEvents.length === 0 ? <p className="empty-state">No action events published yet.</p> : null}
                {timelinePreviewEvents.map((eventItem) => (
                  <button
                    key={eventItem.id}
                    type="button"
                    className="event-card"
                    onClick={() => openEventDialog(eventItem)}
                  >
                    <div className="event-card__content">
                      <p className="stack-list__title">{toStepLabel(eventItem.step)}</p>
                      <p className="stack-list__meta">{truncateText(eventItem.message, 180)}</p>
                    </div>
                    <div className="event-card__meta">
                      <span className={`status-pill status-pill--${eventItem.level}`}>{eventItem.level}</span>
                      <span className="stack-list__meta">{formatDate(eventItem.createdAt)}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </article>
        </div>
      ) : null}

      {activeDialog ? (
        <div className="inspector-dialog" role="dialog" aria-modal="true">
          <div className="inspector-dialog__surface">
            <div className="panel__header">
              <h3>{activeDialog.title}</h3>
              <button className="shell__nav-link" type="button" onClick={() => setActiveDialog(null)}>
                Close
              </button>
            </div>
            <p className="stack-list__meta">{activeDialog.subtitle}</p>
            <div className="dialog-meta">
              {activeDialog.fields.map((field) => (
                <div key={field.label}>
                  <span className="kpi-card__label">{field.label}</span>
                  <p>{field.value}</p>
                </div>
              ))}
            </div>
            <pre className="dialog-body">{activeDialog.body}</pre>
          </div>
        </div>
      ) : null}
    </section>
  );
}
