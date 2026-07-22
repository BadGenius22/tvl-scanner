"""Greenhouse job boards — per-company watchlist source.

https://boards-api.greenhouse.io/v1/boards/<board>/jobs?content=true
Public, keyless. The profile's `company_boards.greenhouse` lists board tokens
(the slug in boards.greenhouse.io/<token>), so dream-company openings are
pulled from the horse's mouth instead of waiting on aggregator coverage.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import httpx

from job_scanner.config import settings
from job_scanner.http import HttpError, get_json
from job_scanner.models import JobPosting, JobSource
from job_scanner.text import clip, strip_html

log = logging.getLogger(__name__)


async def fetch_greenhouse_board(
    board: str, *, client: httpx.AsyncClient | None = None
) -> list[JobPosting]:
    s = settings()
    try:
        payload = await get_json(
            f"{s.GREENHOUSE_BASE}/{board}/jobs",
            params={"content": "true"},
            client=client,
        )
    except HttpError as exc:
        log.warning("greenhouse: board %r failed: %s", board, exc)
        return []
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        return []

    out: list[JobPosting] = []
    for raw in jobs:
        job = _parse_job(raw, board)
        if job is not None:
            out.append(job)
    log.info("greenhouse: %s → %d job(s)", board, len(out))
    return out


def _parse_job(raw: Any, board: str) -> JobPosting | None:
    if not isinstance(raw, dict):
        return None
    native_id = raw.get("id")
    title = raw.get("title")
    url = raw.get("absolute_url")
    if not (native_id and isinstance(title, str) and isinstance(url, str)):
        return None

    location_field = raw.get("location")
    location = (
        str(location_field.get("name") or "") if isinstance(location_field, dict) else ""
    )
    # Greenhouse `content` is HTML-escaped HTML; strip_html unescapes then strips.
    description = clip(strip_html(raw.get("content")))

    return JobPosting(
        job_id=f"greenhouse:{board}:{native_id}",
        source=JobSource.GREENHOUSE,
        title=title.strip(),
        company=board.replace("-", " ").title(),
        url=url,
        location=location,
        remote="remote" in location.lower() or None,
        description=description,
        posted_at=_parse_date(raw.get("updated_at")),
    )


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None
