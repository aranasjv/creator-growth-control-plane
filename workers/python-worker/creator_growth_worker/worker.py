from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import traceback
from typing import TextIO

import redis

from .api_client import ApiClient
from .settings import load_settings

ANSI_ESCAPE_PATTERN = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
MAX_EVENT_MESSAGE_LENGTH = 900
MAX_STREAMED_EVENTS = 250


def run() -> None:
    settings = load_settings()
    api = ApiClient(settings.api_base_url)
    queue = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    print(f"[worker] Listening on {settings.queue_name} via {settings.redis_url}")
    print(f"[worker] Repository root: {settings.repo_root}")

    while True:
        item = queue.blpop(settings.queue_name, timeout=settings.poll_timeout_seconds)
        if item is None:
            continue

        _, raw_payload = item
        job = json.loads(raw_payload)
        job_id = str(job["jobId"])

        try:
            api.post_status(job_id, "running")
            api.post_event(job_id, "info", "starting", f"Starting {job['type']} for provider {job.get('provider', 'unknown')}.")
            api.post_event(job_id, "info", "launch", f"Launching legacy runner for job type {job['type']}.")
            result = _run_legacy_job(job, settings.repo_root, api, job_id)
            api.post_event(job_id, "info", "sync", "Syncing legacy cache into the orchestrator read model.")
            api.sync_legacy()
            api.post_status(job_id, "succeeded", result_json=json.dumps(result))
        except Exception as exc:  # pragma: no cover - integration path
            trace = traceback.format_exc(limit=4)
            try:
                api.post_event(job_id, "error", "failed", str(exc))
                api.post_status(job_id, "failed", error_message=f"{exc}\n{trace}")
            except Exception:
                print(f"[worker] Failed to report error for job {job_id}:\n{trace}")


def _run_legacy_job(job: dict, repo_root: os.PathLike[str] | str, api: ApiClient, job_id: str) -> dict:
    parameters = job.get("parameters") or {}
    command = [
        sys.executable,
        str(os.path.join(repo_root, "src", "worker_task.py")),
        "--job-type",
        str(job["type"]),
    ]

    if job.get("accountId"):
        command.extend(["--account-id", str(job["accountId"])])
    if job.get("productId"):
        command.extend(["--product-id", str(job["productId"])])
    if job.get("model"):
        command.extend(["--model", str(job["model"])])

    env = os.environ.copy()
    env["CGCP_JOB_PARAMETERS"] = json.dumps(parameters)

    process = subprocess.Popen(
        command,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )

    stream_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    sent_events = 0
    stream_notice_sent = False
    last_sent_message = ""

    threads = [
        threading.Thread(
            target=_stream_pipe_lines,
            args=(process.stdout, "stdout", stream_queue),
            daemon=True,
        ),
        threading.Thread(
            target=_stream_pipe_lines,
            args=(process.stderr, "stderr", stream_queue),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()

    closed_streams = 0
    while closed_streams < 2:
        stream_name, payload = stream_queue.get()
        if payload is None:
            closed_streams += 1
            continue

        normalized = _normalize_output_line(payload)
        if not normalized:
            continue

        if stream_name == "stdout":
            stdout_lines.append(normalized)
        else:
            stderr_lines.append(normalized)

        if _looks_like_result_json(normalized):
            continue

        if sent_events >= MAX_STREAMED_EVENTS:
            if not stream_notice_sent:
                _post_event_safe(
                    api,
                    job_id,
                    "warning",
                    "stream_limit",
                    f"Live output truncated after {MAX_STREAMED_EVENTS} messages to keep the dashboard responsive.",
                )
                stream_notice_sent = True
            continue

        level, step, message = _classify_runtime_line(stream_name, normalized)
        if not message or message == last_sent_message:
            continue

        _post_event_safe(api, job_id, level, step, message)
        last_sent_message = message
        sent_events += 1

    for thread in threads:
        thread.join(timeout=2)

    return_code = process.wait()
    stdout = "\n".join(stdout_lines).strip()
    stderr = "\n".join(stderr_lines).strip()

    if return_code != 0:
        raise RuntimeError(stderr or stdout or f"Legacy task exited with code {return_code}")

    if not stdout:
        return {"summary": "Legacy task completed.", "metrics": {}}

    for line in reversed(stdout_lines):
        if not _looks_like_result_json(line):
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    last_line = stdout_lines[-1]
    return {"summary": last_line, "metrics": {}, "stdout": stdout}


def _stream_pipe_lines(
    pipe: TextIO | None,
    stream_name: str,
    out_queue: queue.Queue[tuple[str, str | None]],
) -> None:
    if pipe is None:
        out_queue.put((stream_name, None))
        return

    try:
        for line in iter(pipe.readline, ""):
            out_queue.put((stream_name, line))
    finally:
        try:
            pipe.close()
        except Exception:
            pass
        out_queue.put((stream_name, None))


def _normalize_output_line(line: str) -> str:
    stripped = ANSI_ESCAPE_PATTERN.sub("", line).replace("\r", "").strip()
    return stripped


def _looks_like_result_json(line: str) -> bool:
    text = line.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return False

    try:
        parsed = json.loads(text)
        return isinstance(parsed, dict)
    except json.JSONDecodeError:
        return False


def _classify_runtime_line(stream_name: str, line: str) -> tuple[str, str, str]:
    level = "info"
    step = "progress"
    message = line

    if message.startswith("[ok]"):
        step = "milestone"
        message = message[4:].strip()
    elif message.startswith("[i]"):
        step = "progress"
        message = message[3:].strip()
    elif message.startswith("[!]"):
        level = "warning"
        step = "warning"
        message = message[3:].strip()
    elif message.startswith("[x]"):
        level = "error"
        step = "error"
        message = message[3:].strip()

    lowered = message.lower()
    if "scraping niche" in lowered:
        step = "scrape_niche"
    elif "running scraper" in lowered:
        step = "scraper"
    elif "email preview for" in lowered:
        step = "email_preview"
    elif "dry run" in lowered:
        step = "email_dry_run" if "email" in lowered else "dry_run"
    elif "sending email" in lowered:
        step = "send_email"
    elif "sent email" in lowered:
        step = "email_sent"
    elif "email delivery failed for" in lowered:
        level = "error"
        step = "email_failed"
    elif "no email provided for" in lowered:
        level = "warning"
        step = "email_skipped_no_email"
    elif "no website for" in lowered:
        level = "warning"
        step = "email_skipped_no_website"
    elif "website " in lowered and "skipping" in lowered:
        level = "warning"
        step = "email_skipped_website"
    elif "reached live send cap" in lowered:
        level = "warning"
        step = "email_cap_reached"
    elif "scraped" in lowered and "items" in lowered:
        step = "scrape_result"
    elif "timed out" in lowered:
        level = "warning"
        step = "timeout"

    if stream_name == "stderr" and level == "info":
        level = "error"
        step = "stderr"

    if len(message) > MAX_EVENT_MESSAGE_LENGTH:
        message = f"{message[:MAX_EVENT_MESSAGE_LENGTH]}..."

    return level, step, message


def _post_event_safe(api: ApiClient, job_id: str, level: str, step: str, message: str) -> None:
    try:
        api.post_event(job_id, level, step, message)
    except Exception:
        pass

