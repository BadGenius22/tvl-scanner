"""Tests for the Arbeitnow source."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from job_scanner.sources.arbeitnow import fetch_arbeitnow

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://www.arbeitnow.com/api/job-board-api"


@pytest.fixture
def arbeitnow_payload() -> dict[str, Any]:
    return json.loads((FIXTURES / "arbeitnow.json").read_text())


async def test_fetch_parses_fields(
    httpx_mock: HTTPXMock, arbeitnow_payload: dict[str, Any]
) -> None:
    httpx_mock.add_response(url=URL, json=arbeitnow_payload)

    jobs = await fetch_arbeitnow()

    assert len(jobs) == 2
    sec = next(j for j in jobs if "security" in j.title.lower())
    assert sec.job_id == "arbeitnow:blockchain-security-engineer-berlin-42"
    assert sec.company == "Krypto GmbH"
    assert sec.remote is True
    assert sec.location == "Berlin"
    assert sec.employment_type == "full-time"
    # unix created_at → date (2026-07-20 UTC)
    assert sec.posted_at is not None and sec.posted_at.isoformat() == "2026-07-20"
    assert "EVM" in sec.description and "<em>" not in sec.description

    office = next(j for j in jobs if j.job_id == "arbeitnow:office-manager-munich-7")
    assert office.remote is False
    assert office.employment_type is None  # empty job_types list
