"""Seen-jobs state so daily runs can flag what's NEW.

`artifacts/job_scan_state.json` maps job_id → first-seen ISO date. A job absent
from the state is new this scan; entries older than STATE_RETENTION_DAYS are
pruned so the file stays bounded (a listing re-appearing after that window
counts as new again, which is the desired behavior for re-opened roles).
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from job_scanner.config import settings
from job_scanner.models import ScoredJob

log = logging.getLogger(__name__)


def _state_path() -> Path:
    s = settings()
    return s.artifacts_path / s.STATE_FILE


def load_state(path: Path | None = None) -> dict[str, str]:
    p = path or _state_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("state: could not read %s: %s — treating all jobs as new", p, exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def save_state(state: dict[str, str], path: Path | None = None) -> None:
    p = path or _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, sort_keys=True))


def flag_and_record(
    jobs: list[ScoredJob], state: dict[str, str], *, scan_date: date
) -> None:
    """Set `is_new` on each job from the state, then record this sighting.

    Mutates both the jobs and the state; call `save_state` after.
    """
    for job in jobs:
        job.is_new = job.job_id not in state
        state.setdefault(job.job_id, scan_date.isoformat())
    prune(state, scan_date=scan_date)


def prune(state: dict[str, str], *, scan_date: date) -> None:
    """Drop entries first seen more than STATE_RETENTION_DAYS ago."""
    horizon = scan_date - timedelta(days=settings().STATE_RETENTION_DAYS)
    stale = [k for k, v in state.items() if _older_than(v, horizon)]
    for k in stale:
        del state[k]
    if stale:
        log.info("state: pruned %d stale entr(ies)", len(stale))


def _older_than(iso_date: str, horizon: date) -> bool:
    try:
        return date.fromisoformat(iso_date) < horizon
    except ValueError:
        return True  # unparseable entries are garbage — prune them
