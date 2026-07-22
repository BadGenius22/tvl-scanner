"""Tests for the Remotive source."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from job_scanner.models import JobSource
from job_scanner.profile import Profile
from job_scanner.sources.remotive import fetch_remotive

FIXTURES = Path(__file__).parent / "fixtures"
REMOTIVE_URL = re.compile(r"https://remotive\.com/api/remote-jobs\?.*")


@pytest.fixture
def remotive_payload() -> dict[str, Any]:
    return json.loads((FIXTURES / "remotive_jobs.json").read_text())


async def test_fetch_parses_fields(
    httpx_mock: HTTPXMock, remotive_payload: dict[str, Any]
) -> None:
    httpx_mock.add_response(url=REMOTIVE_URL, json=remotive_payload)
    profile = Profile(role_keywords=["security researcher"])

    jobs = await fetch_remotive(profile)

    assert len(jobs) == 3
    first = next(j for j in jobs if j.job_id == "remotive:1001")
    assert first.source == JobSource.REMOTIVE
    assert first.title == "Senior Security Researcher (Smart Contracts)"
    assert first.company == "ChainGuard Labs"
    assert first.remote is True
    assert first.location == "Worldwide"
    # salary text parsed to an annualized range
    assert (first.salary_min_usd, first.salary_max_usd) == (120_000, 150_000)
    assert first.salary_raw == "$120,000 - $150,000"
    # HTML stripped, entities collapsed
    assert "<p>" not in first.description
    assert "Audit smart contracts" in first.description
    assert first.tags == ["solidity", "defi", "audit"]
    assert first.posted_at is not None and first.posted_at.isoformat() == "2026-07-20"
    assert first.employment_type == "full_time"


async def test_unparseable_optional_fields_degrade(
    httpx_mock: HTTPXMock, remotive_payload: dict[str, Any]
) -> None:
    httpx_mock.add_response(url=REMOTIVE_URL, json=remotive_payload)
    profile = Profile(role_keywords=["rust"])

    jobs = await fetch_remotive(profile)

    rust = next(j for j in jobs if j.job_id == "remotive:1003")
    assert rust.salary_min_usd is None  # salary was null
    assert rust.posted_at is None  # "not-a-date"
    assert rust.description == ""  # null description


async def test_dedupe_across_queries(
    httpx_mock: HTTPXMock, remotive_payload: dict[str, Any]
) -> None:
    """Two role keywords → two searches; overlapping job ids collapse."""
    httpx_mock.add_response(url=REMOTIVE_URL, json=remotive_payload)
    httpx_mock.add_response(url=REMOTIVE_URL, json=remotive_payload)
    profile = Profile(role_keywords=["security researcher", "rust engineer"])

    jobs = await fetch_remotive(profile)

    assert len(jobs) == 3  # not 6
    assert len({j.job_id for j in jobs}) == 3


async def test_failed_query_skips_not_aborts(
    httpx_mock: HTTPXMock, remotive_payload: dict[str, Any]
) -> None:
    """One failing search must not lose the other queries' results."""
    httpx_mock.add_response(url=REMOTIVE_URL, status_code=404)
    httpx_mock.add_response(url=REMOTIVE_URL, json=remotive_payload)
    profile = Profile(role_keywords=["security researcher", "rust engineer"])

    jobs = await fetch_remotive(profile)

    assert len(jobs) == 3
