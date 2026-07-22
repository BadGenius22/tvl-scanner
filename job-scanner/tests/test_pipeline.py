"""End-to-end pipeline tests: mocked sources → report + state on disk."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pytest_httpx import HTTPXMock

from job_scanner.pipeline import run_job_scan
from job_scanner.profile import Profile

FIXTURES = Path(__file__).parent / "fixtures"
SCAN_DATE = date(2026, 7, 22)

PROFILE = Profile(
    name="e2e",
    role_keywords=["smart contract", "security engineer"],
    core_skills=["solidity", "rust", "audit", "defi", "security", "evm"],
    bonus_skills=["foundry", "fuzzing"],
    seniority_levels=["senior", "staff", "lead"],
    exclude_keywords=["intern"],
    remote_only=True,
    location_keywords=["remote", "worldwide", "asia", "singapore"],
    min_salary_usd=60_000,
    target_salary_usd=150_000,
    benefits_keywords=["equity", "unlimited pto"],
    max_age_days=45,
)


def _mock_sources(httpx_mock: HTTPXMock) -> None:
    """One response per aggregator request (Remotive fans out per role keyword)."""
    remotive = json.loads((FIXTURES / "remotive_jobs.json").read_text())
    httpx_mock.add_response(
        url=re.compile(r"https://remotive\.com/api/remote-jobs\?.*"), json=remotive
    )
    httpx_mock.add_response(
        url=re.compile(r"https://remotive\.com/api/remote-jobs\?.*"), json=remotive
    )
    httpx_mock.add_response(
        url="https://remoteok.com/api",
        json=json.loads((FIXTURES / "remoteok.json").read_text()),
    )
    httpx_mock.add_response(
        url="https://www.arbeitnow.com/api/job-board-api",
        json=json.loads((FIXTURES / "arbeitnow.json").read_text()),
    )


async def test_full_scan_writes_report_and_state(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    _mock_sources(httpx_mock)
    reports = tmp_path / "reports"
    state_path = tmp_path / "state.json"

    summary = await run_job_scan(
        profile=PROFILE,
        scan_date=SCAN_DATE,
        reports_dir=reports,
        state_path=state_path,
    )

    text = summary.read_text()
    assert summary.name == "2026-07-22-job-scan.md"
    # The three suitable roles, ranked; the weak ones cut by the cutoff.
    assert "Senior Security Researcher (Smart Contracts)" in text
    assert "Smart Contract Auditor" in text
    assert "Blockchain Security Engineer" in text
    assert "Growth Marketer" not in text
    # Dealbreaker drops are reported, never silent.
    assert "onsite-only outside preferred locations: 1" in text
    # Marketer + two one-skill matches fail the relevance gate, visibly.
    assert "weak profile match: 3" in text
    # Everything is new on a first run.
    assert "**3** new since the last scan" in text

    # Per-role records exist, with liftable YAML frontmatter.
    roles_dir = reports / "2026-07-22-job-scan" / "roles"
    records = sorted(roles_dir.glob("*.md"))
    assert len(records) == 3
    top = records[0].read_text()
    frontmatter = yaml.safe_load(top.split("---")[1])
    assert frontmatter["suitability_score"] > 8
    assert frontmatter["company"] == "ChainGuard Labs"
    assert frontmatter["is_new"] is True
    assert set(frontmatter["scores"]) == {
        "skill_match", "compensation", "location", "seniority", "benefits", "freshness",
    }

    # State recorded every reported job.
    state: dict[str, Any] = json.loads(state_path.read_text())
    assert len(state) == 3
    assert all(v == "2026-07-22" for v in state.values())


async def test_second_scan_flags_nothing_new(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    reports = tmp_path / "reports"
    state_path = tmp_path / "state.json"

    _mock_sources(httpx_mock)
    await run_job_scan(
        profile=PROFILE, scan_date=SCAN_DATE, reports_dir=reports, state_path=state_path
    )

    _mock_sources(httpx_mock)
    summary = await run_job_scan(
        profile=PROFILE, scan_date=SCAN_DATE, reports_dir=reports, state_path=state_path
    )

    assert "**0** new since the last scan" in summary.read_text()


async def test_new_only_reports_only_unseen(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    reports = tmp_path / "reports"
    state_path = tmp_path / "state.json"

    _mock_sources(httpx_mock)
    await run_job_scan(
        profile=PROFILE, scan_date=SCAN_DATE, reports_dir=reports, state_path=state_path
    )

    _mock_sources(httpx_mock)
    summary = await run_job_scan(
        profile=PROFILE,
        scan_date=SCAN_DATE,
        reports_dir=reports,
        state_path=state_path,
        new_only=True,
    )

    text = summary.read_text()
    assert "Smart Contract Auditor" not in text  # seen on the first run
    roles_dir = reports / "2026-07-22-job-scan" / "roles"
    assert list(roles_dir.glob("*.md")) == []
