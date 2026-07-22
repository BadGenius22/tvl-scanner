"""Tests for the RemoteOK source."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from job_scanner.sources.remoteok import fetch_remoteok

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://remoteok.com/api"


@pytest.fixture
def remoteok_payload() -> list[Any]:
    return json.loads((FIXTURES / "remoteok.json").read_text())


async def test_legal_notice_head_is_skipped(
    httpx_mock: HTTPXMock, remoteok_payload: list[Any]
) -> None:
    httpx_mock.add_response(url=URL, json=remoteok_payload)

    jobs = await fetch_remoteok()

    assert len(jobs) == 2  # 3 elements, head is the legal notice
    assert all(j.job_id.startswith("remoteok:") for j in jobs)


async def test_salary_fields_and_zero_gating(
    httpx_mock: HTTPXMock, remoteok_payload: list[Any]
) -> None:
    httpx_mock.add_response(url=URL, json=remoteok_payload)

    jobs = await fetch_remoteok()

    auditor = next(j for j in jobs if j.job_id == "remoteok:555001")
    assert (auditor.salary_min_usd, auditor.salary_max_usd) == (90_000, 140_000)
    assert auditor.posted_at is not None and auditor.posted_at.isoformat() == "2026-07-21"
    assert auditor.remote is True

    backend = next(j for j in jobs if j.job_id == "remoteok:555002")
    # salary 0 is junk, not "zero pay"
    assert backend.salary_min_usd is None and backend.salary_max_usd is None
    assert backend.best_salary_usd is None


async def test_user_agent_header_sent(
    httpx_mock: HTTPXMock, remoteok_payload: list[Any]
) -> None:
    """RemoteOK rejects UA-less requests — the fetch must always send one."""
    httpx_mock.add_response(url=URL, json=remoteok_payload)

    await fetch_remoteok()

    request = httpx_mock.get_requests()[0]
    assert request.headers.get("User-Agent", "").startswith("job-scanner/")
