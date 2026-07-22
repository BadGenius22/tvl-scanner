"""Remotive — remote-jobs API with server-side search.

https://remotive.com/api/remote-jobs?search=<query>&limit=<n>
Public, keyless. One request per profile role_keyword so the search space
covers every role identity, deduped by job id across queries.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import httpx

from job_scanner.config import settings
from job_scanner.http import HttpError, get_json
from job_scanner.models import JobPosting, JobSource
from job_scanner.profile import Profile
from job_scanner.salary import parse_salary_text
from job_scanner.text import clip, strip_html

log = logging.getLogger(__name__)

_PER_QUERY_LIMIT = 100


async def fetch_remotive(
    profile: Profile, *, client: httpx.AsyncClient | None = None
) -> list[JobPosting]:
    """One search per role keyword, deduped by native job id."""
    s = settings()
    seen: set[str] = set()
    out: list[JobPosting] = []
    queries = profile.role_keywords or ["engineer"]

    for query in queries:
        try:
            payload = await get_json(
                s.REMOTIVE_BASE,
                params={"search": query, "limit": _PER_QUERY_LIMIT},
                client=client,
            )
        except HttpError as exc:
            log.warning("remotive: query %r failed: %s", query, exc)
            continue
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            continue
        for raw in jobs:
            job = _parse_job(raw)
            if job is None or job.job_id in seen:
                continue
            seen.add(job.job_id)
            out.append(job)

    log.info("remotive: %d job(s) across %d quer(ies)", len(out), len(queries))
    return out


def _parse_job(raw: Any) -> JobPosting | None:
    if not isinstance(raw, dict):
        return None
    native_id = raw.get("id")
    title = raw.get("title")
    url = raw.get("url")
    if not (native_id and isinstance(title, str) and isinstance(url, str)):
        return None

    salary_raw = raw.get("salary") if isinstance(raw.get("salary"), str) else None
    parsed = parse_salary_text(salary_raw)
    location = str(raw.get("candidate_required_location") or "")

    return JobPosting(
        job_id=f"remotive:{native_id}",
        source=JobSource.REMOTIVE,
        title=title.strip(),
        company=str(raw.get("company_name") or "unknown").strip(),
        url=url,
        location=location,
        remote=True,  # Remotive lists remote jobs only
        salary_min_usd=parsed[0] if parsed else None,
        salary_max_usd=parsed[1] if parsed else None,
        salary_raw=salary_raw or None,
        tags=[str(t).lower() for t in raw.get("tags") or [] if isinstance(t, (str, int))],
        description=clip(strip_html(raw.get("description"))),
        posted_at=_parse_date(raw.get("publication_date")),
        employment_type=str(raw.get("job_type")) if raw.get("job_type") else None,
    )


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None
