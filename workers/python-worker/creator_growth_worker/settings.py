from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    api_base_url: str
    redis_url: str
    queue_name: str
    poll_timeout_seconds: int


def load_settings() -> Settings:
    repo_root = Path(__file__).resolve().parents[3]
    return Settings(
        repo_root=repo_root,
        api_base_url=os.environ.get("CGCP_API_BASE_URL", "http://localhost:5050"),
        redis_url=os.environ.get("CGCP_REDIS_URL", "redis://localhost:6379/0"),
        queue_name=os.environ.get("CGCP_QUEUE_NAME", "cgcp:jobs"),
        poll_timeout_seconds=int(os.environ.get("CGCP_POLL_TIMEOUT", "5")),
    )

