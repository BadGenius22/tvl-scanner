"""Arbeitnow job board — https://www.arbeitnow.com/api/job-board-api

Public, keyless. Europe-leaning catalogue with an explicit `remote` boolean
and unix `created_at`. Single page is plenty — deeper pages are stale.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

import httpx

from job_scanner.config import settings
from job_scanner.http import HttpError, get_json
from job_scanner.models import JobPosting, JobSource
from job_scanner.text import clip, strip_html

log = logging.getLogger(__name__)


async def fetch_arbeitnow(*, client: httpx.AsyncClient | None = None) -> list[JobPosting]:
    s = settings()
    try:
        payload = await get_json(s.ARBEITNOW_URL, client=client)
    except HttpError as exc:
        log.warning("arbeitnow: fetch failed: %s", exc)
        return []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []

    out: list[JobPosting] = []
    for raw in data:
        job = _parse_job(raw)
        if job is not None:
            out.append(job)
    log.info("arbeitnow: %d job(s)", len(out))
    return out


def _parse_job(raw: Any) -> JobPosting | None:
    if not isinstance(raw, dict):
        return None
    slug = raw.get("slug")
    title = raw.get("title")
    url = raw.get("url")
    if not (isinstance(slug, str) and isinstance(title, str) and isinstance(url, str)):
        return None

    job_types = raw.get("job_types")
    employment = (
        str(job_types[0]) if isinstance(job_types, list) and job_types else None
    )

    return JobPosting(
        job_id=f"arbeitnow:{slug}",
        source=JobSource.ARBEITNOW,
        title=title.strip(),
        company=str(raw.get("company_name") or "unknown").strip(),
        url=url,
        location=str(raw.get("location") or ""),
        remote=bool(raw["remote"]) if isinstance(raw.get("remote"), bool) else None,
        tags=[str(t).lower() for t in raw.get("tags") or [] if isinstance(t, (str, int))],
        description=clip(strip_html(raw.get("description"))),
        posted_at=_parse_unix(raw.get("created_at")),
        employment_type=employment,
    )


def _parse_unix(value: Any) -> date | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=UTC).date()
    except (OverflowError, OSError, ValueError):
        return None
