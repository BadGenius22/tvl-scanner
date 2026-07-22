"""RemoteOK — https://remoteok.com/api

Public, keyless JSON array. Quirks: element [0] is a legal notice (skipped),
salary_min/salary_max are numeric but sometimes 0/junk (plausibility-gated),
and requests without a User-Agent are rejected.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import httpx

from job_scanner.config import settings
from job_scanner.http import HttpError, get_json
from job_scanner.models import JobPosting, JobSource
from job_scanner.salary import plausible_annual_usd
from job_scanner.text import clip, strip_html

log = logging.getLogger(__name__)


async def fetch_remoteok(*, client: httpx.AsyncClient | None = None) -> list[JobPosting]:
    s = settings()
    try:
        payload = await get_json(
            s.REMOTEOK_URL,
            headers={"User-Agent": s.USER_AGENT},
            client=client,
        )
    except HttpError as exc:
        log.warning("remoteok: fetch failed: %s", exc)
        return []
    if not isinstance(payload, list):
        return []

    out: list[JobPosting] = []
    for raw in payload:
        job = _parse_job(raw)
        if job is not None:
            out.append(job)
    log.info("remoteok: %d job(s)", len(out))
    return out


def _parse_job(raw: Any) -> JobPosting | None:
    if not isinstance(raw, dict):
        return None
    # The legal-notice head element has no position/id.
    native_id = raw.get("id")
    title = raw.get("position")
    if not (native_id and isinstance(title, str) and title.strip()):
        return None

    url = raw.get("url") or raw.get("apply_url")
    if not isinstance(url, str):
        return None

    salary_min = plausible_annual_usd(_num(raw.get("salary_min")))
    salary_max = plausible_annual_usd(_num(raw.get("salary_max")))
    location = str(raw.get("location") or "")

    return JobPosting(
        job_id=f"remoteok:{native_id}",
        source=JobSource.REMOTEOK,
        title=title.strip(),
        company=str(raw.get("company") or "unknown").strip(),
        url=url,
        location=location,
        remote=True,  # RemoteOK lists remote jobs only
        salary_min_usd=salary_min,
        salary_max_usd=salary_max,
        salary_raw=(
            f"${salary_min:,}–${salary_max:,}" if salary_min and salary_max else None
        ),
        tags=[str(t).lower() for t in raw.get("tags") or [] if isinstance(t, (str, int))],
        description=clip(strip_html(raw.get("description"))),
        posted_at=_parse_date(raw.get("date")),
    )


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None
