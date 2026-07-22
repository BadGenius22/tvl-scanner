"""Non-secret configuration for the job scanner.

Loaded from `.env` / process environment with the `JOB_SCANNER_` prefix so the
tvl_scanner settings (same `.env`, unprefixed) never collide. No secrets are
needed: every source used here is a public, keyless JSON API.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class JobScannerSettings(BaseSettings):
    """Env-tunable knobs. Field FOO reads env var JOB_SCANNER_FOO."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="JOB_SCANNER_",
        case_sensitive=True,
        extra="ignore",
    )

    # Paths (shared layout with tvl_scanner: reports/ + artifacts/ at repo root)
    REPORTS_DIR: str = "reports"
    ARTIFACTS_DIR: str = "artifacts"
    STATE_FILE: str = "job_scan_state.json"
    # Optional path to a profile.yaml overriding the packaged default.
    PROFILE_PATH: str = ""

    # API endpoints — all public, no API key required.
    REMOTIVE_BASE: str = "https://remotive.com/api/remote-jobs"
    REMOTEOK_URL: str = "https://remoteok.com/api"
    ARBEITNOW_URL: str = "https://www.arbeitnow.com/api/job-board-api"
    GREENHOUSE_BASE: str = "https://boards-api.greenhouse.io/v1/boards"
    LEVER_BASE: str = "https://api.lever.co/v0/postings"

    # HTTP behavior (see http.py — tests set BACKOFF to 0 for instant retries)
    HTTP_TIMEOUT_SECONDS: int = 30
    HTTP_MAX_RETRIES: int = 3
    HTTP_BACKOFF_SECONDS: float = 2.0

    # Seen-state entries older than this are pruned so the state file stays
    # bounded; a posting re-appearing after this window counts as new again.
    STATE_RETENTION_DAYS: int = 120

    # Some boards (RemoteOK) reject requests without a browser-ish UA.
    USER_AGENT: str = "job-scanner/0.1 (+https://github.com/BadGenius22/tvl-scanner)"

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def reports_path(self) -> Path:
        return self.repo_root / self.REPORTS_DIR

    @property
    def artifacts_path(self) -> Path:
        return self.repo_root / self.ARTIFACTS_DIR


@lru_cache(maxsize=1)
def settings() -> JobScannerSettings:
    """Singleton accessor. Cache is cleared in tests to re-read env."""
    return JobScannerSettings()
