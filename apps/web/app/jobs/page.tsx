import { AppShell } from "@/components/app-shell";
import { JobsLiveMonitor } from "@/components/jobs-live-monitor";
import { readJobs } from "@/lib/api";

export default async function JobsPage() {
  const jobs = await readJobs();

  return (
    <AppShell
      current="/jobs"
      eyebrow="Jobs"
      title="Queue depth, failures, and output timing"
      summary="This is the operating table for every task the system tries to run. Use it to spot stuck providers, broken profiles, and weak automation paths before they burn time."
    >
      <JobsLiveMonitor initialJobs={jobs} />
    </AppShell>
  );
}
