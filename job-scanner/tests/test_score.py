"""Tests for the suitability scoring formula + dealbreakers."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from job_scanner.models import JobPosting, JobSource
from job_scanner.profile import Profile
from job_scanner.score import (
    compensation_score,
    dealbreaker,
    location_score,
    rank_all,
    rank_job,
    seniority_score,
    skill_match_score,
)

SCAN_DATE = date(2026, 7, 22)

PROFILE = Profile(
    name="test",
    role_keywords=["security researcher", "smart contract"],
    core_skills=["solidity", "rust", "audit", "defi"],
    bonus_skills=["foundry", "fuzzing"],
    seniority_levels=["senior", "lead"],
    exclude_keywords=["intern"],
    remote_only=True,
    location_keywords=["remote", "worldwide", "asia", "singapore"],
    min_salary_usd=60_000,
    target_salary_usd=150_000,
    benefits_keywords=["equity", "unlimited pto"],
    max_age_days=45,
)


def make_job(**overrides: object) -> JobPosting:
    base: dict[str, object] = {
        "job_id": "test:1",
        "source": JobSource.REMOTIVE,
        "title": "Software Engineer",
        "company": "Acme",
        "url": "https://example.com/job",
    }
    base.update(overrides)
    return JobPosting.model_validate(base)


# ---------------------------------------------------------------------------
# Sub-scores
# ---------------------------------------------------------------------------


def test_skill_match_title_role_hit_dominates() -> None:
    job = make_job(title="Security Researcher", description="")
    score, role_hits, _ = skill_match_score(job, PROFILE)
    assert role_hits == ["security researcher"]
    assert score >= 5.0


def test_skill_match_caps_at_8_without_role_hit() -> None:
    """Skill soup in a wrong-role posting can't beat an actual role match."""
    job = make_job(
        title="Growth Lead",
        description="solidity rust audit defi foundry fuzzing everywhere",
    )
    score, role_hits, matched = skill_match_score(job, PROFILE)
    assert role_hits == []
    assert score <= 8.0
    assert "solidity" in matched


def test_skill_match_is_word_boundary_aware() -> None:
    """'rust' must not hit 'trust' — the live-run bug that ranked a marketing
    role #1 on a phantom skill match."""
    job = make_job(
        title="Head of Marketing",
        description="a role built on trust and strong industry relationships",
    )
    score, _role_hits, matched = skill_match_score(job, PROFILE)
    assert matched == []
    assert score == 0.0


def test_plural_titles_still_match_role_keywords() -> None:
    job = make_job(title="Senior Security Researcher (Smart Contracts)")
    _, role_hits, _ = skill_match_score(job, PROFILE)
    assert "smart contract" in role_hits


def test_compensation_anchors() -> None:
    assert compensation_score(make_job(), PROFILE) == 5.0  # unstated → neutral
    assert compensation_score(make_job(salary_max_usd=60_000), PROFILE) == 3.0
    assert compensation_score(make_job(salary_max_usd=105_000), PROFILE) == pytest.approx(6.5)
    assert compensation_score(make_job(salary_max_usd=150_000), PROFILE) == 10.0
    assert compensation_score(make_job(salary_max_usd=999_000), PROFILE) == 10.0
    assert compensation_score(make_job(salary_max_usd=30_000), PROFILE) == pytest.approx(1.5)


def test_location_remote_worldwide_is_perfect() -> None:
    job = make_job(remote=True, location="Worldwide")
    assert location_score(job, PROFILE) == 10.0


def test_location_geo_fenced_remote_is_a_long_shot() -> None:
    """'Remote (US only)' is not remote for an APAC profile — the generic
    'remote' keyword must not lift the fence."""
    job = make_job(remote=True, location="Remote (US only)")
    assert location_score(job, PROFILE) == 3.0


def test_location_fence_in_profile_region_is_fine() -> None:
    job = make_job(remote=True, location="Remote — Asia")
    assert location_score(job, PROFILE) == 10.0


def test_location_onsite_in_preferred_place() -> None:
    job = make_job(remote=False, location="Singapore")
    assert location_score(job, PROFILE) == 7.0


def test_location_onsite_elsewhere_with_remote_only_profile() -> None:
    job = make_job(remote=False, location="Munich")
    assert location_score(job, PROFILE) == 0.0


def test_seniority_levels() -> None:
    assert seniority_score(make_job(title="Senior Auditor"), PROFILE) == 10.0
    assert seniority_score(make_job(title="Junior Auditor"), PROFILE) == 0.0
    assert seniority_score(make_job(title="Protocol Auditor"), PROFILE) == 6.0


# ---------------------------------------------------------------------------
# Dealbreakers
# ---------------------------------------------------------------------------


def test_dealbreaker_excluded_keyword() -> None:
    assert dealbreaker(make_job(title="Security Intern"), PROFILE) == "excluded keyword: intern"


def test_dealbreaker_below_seniority_floor() -> None:
    assert dealbreaker(make_job(title="Junior Security Engineer"), PROFILE) == (
        "below seniority floor"
    )


def test_excluded_intern_does_not_hit_international() -> None:
    assert dealbreaker(make_job(title="International Support Lead"), PROFILE) is None


def test_dealbreaker_onsite_outside_locations() -> None:
    job = make_job(remote=False, location="Munich")
    assert dealbreaker(job, PROFILE) == "onsite-only outside preferred locations"
    # ...but onsite in a preferred place is kept
    assert dealbreaker(make_job(remote=False, location="Singapore"), PROFILE) is None


# ---------------------------------------------------------------------------
# Weighted formula
# ---------------------------------------------------------------------------


def test_rank_job_weighted_sum_hand_computed() -> None:
    job = make_job(
        title="Senior Security Researcher",
        tags=["solidity"],
        description="audit defi protocols. equity.",
        salary_max_usd=150_000,
        remote=True,
        location="Worldwide",
        posted_at=SCAN_DATE - timedelta(days=9),
    )
    scored = rank_job(job, PROFILE, scan_date=SCAN_DATE)
    # skill: 5 (role) + 4.5 (3 core hits × 1.5) = 9.5; comp 10; loc 10;
    # seniority 10; benefits 2.5 (equity); freshness 10·(1−9/45) = 8.0
    assert scored.skill_match_score == 9.5
    assert scored.compensation_score == 10.0
    assert scored.benefits_score == 2.5
    assert scored.freshness_score == 8.0
    # 9.5·.30 + 10·.20 + 10·.15 + 10·.15 + 2.5·.10 + 8·.10 = 8.9
    assert scored.suitability_score == pytest.approx(8.9)
    assert "equity" in scored.matched_benefits
    assert "role match: security researcher" in scored.why_suitable


def test_rank_all_filters_sorts_caps_and_counts_drops() -> None:
    strong = make_job(
        job_id="test:strong",
        title="Senior Smart Contract Auditor",
        description="solidity audit defi equity",
        salary_max_usd=160_000,
        remote=True,
        location="Worldwide",
    )
    weak = make_job(job_id="test:weak", title="Office Manager", remote=True, location="Worldwide")
    dropped_job = make_job(job_id="test:intern", title="Solidity Intern")

    ranked, dropped = rank_all(
        [weak, strong, dropped_job], PROFILE, scan_date=SCAN_DATE, cutoff=5.0, cap=10
    )

    assert [j.job_id for j in ranked] == ["test:strong"]
    # weak has zero profile overlap → relevance gate, not a silent cutoff cut
    assert dropped == {"excluded keyword": 1, "weak profile match": 1}


def test_rank_all_cap_applies_after_sort() -> None:
    jobs = [
        make_job(
            job_id=f"test:{i}",
            title="Senior Smart Contract Auditor",
            description="solidity audit defi",
            salary_max_usd=100_000 + i * 10_000,
            remote=True,
            location="Worldwide",
        )
        for i in range(5)
    ]
    ranked, _ = rank_all(jobs, PROFILE, scan_date=SCAN_DATE, cutoff=0.0, cap=2)
    assert len(ranked) == 2
    # highest salary (highest comp score) first
    assert ranked[0].salary_max_usd == 140_000
