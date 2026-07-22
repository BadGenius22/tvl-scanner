"""Tests for the company-watchlist sources (Greenhouse + Lever)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from job_scanner.sources.greenhouse import fetch_greenhouse_board
from job_scanner.sources.lever import fetch_lever_company

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def greenhouse_payload() -> dict[str, Any]:
    return json.loads((FIXTURES / "greenhouse_board.json").read_text())


@pytest.fixture
def lever_payload() -> list[Any]:
    return json.loads((FIXTURES / "lever_postings.json").read_text())


async def test_greenhouse_parses_board(
    httpx_mock: HTTPXMock, greenhouse_payload: dict[str, Any]
) -> None:
    httpx_mock.add_response(
        url="https://boards-api.greenhouse.io/v1/boards/chainguard/jobs?content=true",
        json=greenhouse_payload,
    )

    jobs = await fetch_greenhouse_board("chainguard")

    assert len(jobs) == 2
    staff = next(j for j in jobs if j.job_id == "greenhouse:chainguard:7001")
    assert staff.company == "Chainguard"
    assert staff.remote is True  # "Remote - Worldwide" location
    # content is HTML-escaped HTML: entities unescaped, tags stripped
    assert "Lead audits of smart contracts" in staff.description
    assert "&lt;" not in staff.description and "<p>" not in staff.description
    assert staff.posted_at is not None and staff.posted_at.isoformat() == "2026-07-18"

    recruiter = next(j for j in jobs if j.job_id == "greenhouse:chainguard:7002")
    assert recruiter.remote is None  # onsite location → source doesn't say remote
    assert recruiter.location == "New York, NY"


async def test_lever_parses_postings(
    httpx_mock: HTTPXMock, lever_payload: list[Any]
) -> None:
    httpx_mock.add_response(
        url="https://api.lever.co/v0/postings/vaultco?mode=json",
        json=lever_payload,
    )

    jobs = await fetch_lever_company("vaultco")

    assert len(jobs) == 2
    eng = next(j for j in jobs if j.job_id == "lever:vaultco:a1b2c3d4")
    assert eng.company == "Vaultco"
    assert eng.remote is True  # workplaceType: remote
    assert (eng.salary_min_usd, eng.salary_max_usd) == (130_000, 180_000)
    assert eng.employment_type == "Full-time"
    # createdAt ms → date (2026-07-19 UTC)
    assert eng.posted_at is not None and eng.posted_at.isoformat() == "2026-07-19"

    cm = next(j for j in jobs if j.job_id == "lever:vaultco:e5f6a7b8")
    assert cm.remote is None  # onsite workplaceType, non-remote location
    assert cm.best_salary_usd is None


async def test_board_failure_returns_empty(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://boards-api.greenhouse.io/v1/boards/ghosted/jobs?content=true",
        status_code=404,
    )
    assert await fetch_greenhouse_board("ghosted") == []
