from __future__ import annotations

import requests


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def post_event(self, job_id: str, level: str, step: str, message: str) -> None:
        self._session.post(
            f"{self._base_url}/api/internal/jobs/{job_id}/events",
            json={"level": level, "step": step, "message": message},
            timeout=15,
        ).raise_for_status()

    def post_status(self, job_id: str, status: str, error_message: str | None = None, result_json: str | None = None) -> None:
        self._session.post(
            f"{self._base_url}/api/internal/jobs/{job_id}/status",
            json={"status": status, "errorMessage": error_message, "resultJson": result_json},
            timeout=15,
        ).raise_for_status()

    def sync_legacy(self) -> None:
        self._session.post(f"{self._base_url}/api/internal/legacy/sync", timeout=30).raise_for_status()
