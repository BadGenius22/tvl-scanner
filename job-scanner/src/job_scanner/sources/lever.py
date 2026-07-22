"""Lever postings — per-company watchlist source.

https://api.lever.co/v0/postings/<company>?mode=json
Public, keyless. The profile's `company_boards.lever` lists company slugs
(the slug in jobs.lever.co/<slug>).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

import httpx

from job_scanner.config import settings
from job_scanner.http import HttpError, get_json
from job_scanner.models import JobPosting, JobSource
from job_scanner.salary import plausible_annual_usd
from job_scanner.text import clip, strip_html

log = logging.getLogger(__name__)


async def fetch_lever_company(
    company: str, *, client: httpx.AsyncClient | None = None
) -> list[JobPosting]:
    s = settings()
    try:
        payload = await get_json(
            f"{s.LEVER_BASE}/{company}",
            params={"mode": "json"},
            client=client,
        )
    except HttpError as exc:
        log.warning("lever: company %r failed: %s", company, exc)
        return []
    if not isinstance(payload, list):
        return []

    out: list[JobPosting] = []
    for raw in payload:
        job = _parse_job(raw, company)
        if job is not None:
            out.append(job)
    log.info("lever: %s → %d job(s)", company, len(out))
    return out


def _parse_job(raw: Any, company: str) -> JobPosting | None:
    if not isinstance(raw, dict):
        return None
    native_id = raw.get("id")
    title = raw.get("text")
    url = raw.get("hostedUrl")
    if not (native_id and isinstance(title, str) and isinstance(url, str)):
        return None

    categories = raw.get("categories") if isinstance(raw.get("categories"), dict) else {}
    assert isinstance(categories, dict)
    location = str(categories.get("location") or "")
    commitment = categories.get("commitment")
    workplace = str(raw.get("workplaceType") or "").lower()

    salary_min: int | None = None
    salary_max: int | None = None
    salary_range = raw.get("salaryRange")
    if isinstance(salary_range, dict):
        salary_min = plausible_annual_usd(_num(salary_range.get("min")))
        salary_max = plausible_annual_usd(_num(salary_range.get("max")))

    return JobPosting(
        job_id=f"lever:{company}:{native_id}",
        source=JobSource.LEVER,
        title=title.strip(),
        company=company.replace("-", " ").title(),
        url=url,
        location=location,
        remote=True if workplace == "remote" else ("remote" in location.lower() or None),
        salary_min_usd=salary_min,
        salary_max_usd=salary_max,
        description=clip(strip_html(str(raw.get("descriptionPlain") or ""))),
        posted_at=_parse_ms(raw.get("createdAt")),
        employment_type=str(commitment) if commitment else None,
    )


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _parse_ms(value: Any) -> date | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000.0, tz=UTC).date()
    except (OverflowError, OSError, ValueError):
        return None
