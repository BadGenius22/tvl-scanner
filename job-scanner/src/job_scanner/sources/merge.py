"""Discovery orchestrator: fan out to all sources, merge, dedupe.

Sources run concurrently on one shared client; a failing source logs and
contributes nothing (never aborts the scan). Cross-source duplicates (the same
role syndicated to Remotive AND RemoteOK) are collapsed by normalized
(company, title), keeping whichever record carries more information.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable

import httpx

from job_scanner.models import JobPosting
from job_scanner.profile import Profile
from job_scanner.sources.arbeitnow import fetch_arbeitnow
from job_scanner.sources.greenhouse import fetch_greenhouse_board
from job_scanner.sources.lever import fetch_lever_company
from job_scanner.sources.remoteok import fetch_remoteok
from job_scanner.sources.remotive import fetch_remotive

log = logging.getLogger(__name__)

_NORM_RE = re.compile(r"[^a-z0-9]+")


async def discover_all(
    profile: Profile, *, client: httpx.AsyncClient | None = None
) -> list[JobPosting]:
    """Fetch every source concurrently and return the deduped union."""
    tasks: list[Awaitable[list[JobPosting]]] = [
        fetch_remotive(profile, client=client),
        fetch_remoteok(client=client),
        fetch_arbeitnow(client=client),
    ]
    tasks += [fetch_greenhouse_board(b, client=client) for b in profile.greenhouse_boards]
    tasks += [fetch_lever_company(c, client=client) for c in profile.lever_companies]

    gathered = await asyncio.gather(*tasks, return_exceptions=True)
    all_jobs: list[JobPosting] = []
    for outcome in gathered:
        if isinstance(outcome, BaseException):
            log.error("discover: source failed, skipping: %s", outcome)
            continue
        all_jobs.extend(outcome)

    deduped = dedupe(all_jobs)
    log.info("discover: %d job(s) after dedupe (%d raw)", len(deduped), len(all_jobs))
    return deduped


def _norm(text: str) -> str:
    return _NORM_RE.sub(" ", text.lower()).strip()


def _richness(job: JobPosting) -> tuple[int, int]:
    """Which duplicate to keep: salary-stated wins, then longer description."""
    return (1 if job.best_salary_usd is not None else 0, len(job.description))


def dedupe(jobs: list[JobPosting]) -> list[JobPosting]:
    """Collapse duplicates by job_id, then by normalized (company, title)."""
    by_key: dict[str, JobPosting] = {}
    for job in jobs:
        key = (
            job.job_id
            if job.company.lower() in ("", "unknown")
            else f"{_norm(job.company)}::{_norm(job.title)}"
        )
        existing = by_key.get(key)
        if existing is None or _richness(job) > _richness(existing):
            by_key[key] = job
    return list(by_key.values())
