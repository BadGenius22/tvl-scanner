"""Tests for the ranking/priority scoring module."""

from __future__ import annotations

from datetime import date

import pytest

from tvl_scanner.models import (
    AuditedCandidate,
    Chain,
    DiscoverySource,
    Language,
)
from tvl_scanner.rank.priority import (
    PRIORITY_CUTOFF,
    activity_score,
    audit_gap_score,
    bounty_score,
    edge_match_score,
    freshness_score,
    rank_all,
    rank_candidate,
    tvl_score,
)


def _audited(
    *,
    tvl_usd: float = 200000,
    days_old: int = 30,
    users: int | None = 500,
    audit_density: int = 0,
    display_name: str = "Test Protocol",
    bounty: str = "none",
) -> AuditedCandidate:
    return AuditedCandidate(
        chain=Chain.ARBITRUM,
        address="0xABC",
        tvl_usd=tvl_usd,
        first_seen=date(2026, 4, 13) - __import__("datetime").timedelta(days=days_old),
        unique_users_30d=users,
        source=DiscoverySource.GECKOTERMINAL,
        target_name="test-protocol",
        display_name=display_name,
        protocol_type="unknown protocol on arbitrum",
        languages=[Language.SOLIDITY],
        bounty_program=bounty,  # type: ignore[arg-type]
        audit_density_score=audit_density,
        audit_sources_found=[],
        under_audited=audit_density <= 2,
    )


# ---- Sub-score tests ----


def test_tvl_score_clamps_at_extremes() -> None:
    assert tvl_score(0) == 0.0
    assert tvl_score(100_000) == 0.0  # log10(100k) - 5 = 0
    assert tvl_score(1_000_000) == 5.0  # log10(1M) - 5 = 1, × 5 = 5
    assert tvl_score(10_000_000) == 10.0  # log10(10M) - 5 = 2, × 5 = 10
    assert tvl_score(1_000_000_000) == 10.0  # clamped


def test_freshness_score_decay() -> None:
    assert freshness_score(0, 365) == 10.0
    assert freshness_score(365, 365) == 0.0
    assert freshness_score(182, 365) == pytest.approx(5.01, abs=0.1)
    assert freshness_score(400, 365) == 0.0


def test_audit_gap_score_inverse() -> None:
    assert audit_gap_score(0) == 10.0
    assert audit_gap_score(1) == 8.0
    assert audit_gap_score(5) == 0.0
    assert audit_gap_score(100) == 0.0


def test_activity_score_log_scaled() -> None:
    assert activity_score(None) == 5.0  # neutral for unknown
    assert activity_score(0) == 0.0
    assert activity_score(9) == pytest.approx(2.5, abs=0.1)  # log10(10)*2.5 = 2.5
    assert activity_score(99) == pytest.approx(5.0, abs=0.1)
    assert activity_score(10_000_000) == 10.0  # clamped


def test_edge_match_score_no_match() -> None:
    c = _audited(display_name="Some Random Protocol")
    score, hits = edge_match_score(c)
    assert score == 0.0
    assert hits == []


def test_edge_match_score_single_match() -> None:
    c = _audited(display_name="Acme Leverage Protocol")
    score, hits = edge_match_score(c)
    assert score == 5.0
    assert "leverage" in hits


def test_edge_match_score_multiple_matches_caps_at_10() -> None:
    c = _audited(display_name="Leverage Vault on Aave")
    score, hits = edge_match_score(c)
    assert score == 10.0
    assert len(hits) >= 2


def test_bounty_score_binary() -> None:
    assert bounty_score(_audited(bounty="none")) == 0.0
    assert bounty_score(_audited(bounty="immunefi")) == 10.0
    assert bounty_score(_audited(bounty="hackerone")) == 10.0


# ---- Composite rank tests ----


def test_rank_candidate_produces_full_record() -> None:
    c = _audited(
        tvl_usd=5_000_000,
        days_old=30,
        users=1000,
        audit_density=0,
        display_name="Leverage Vault on Silo",
    )
    result = rank_candidate(c, scan_date=date(2026, 4, 13))
    assert result.priority_score > 7.0  # strong candidate
    assert result.edge_match_score == 10.0  # "leverage" + "vault" + "silo"
    assert result.tvl_score > 5.0
    assert result.audit_gap_score == 10.0
    assert result.inferred_platform == "private"
    assert result.inferred_mode == "private"
    assert result.age_days == 30
    assert len(result.focus_areas_suggested) > 0
    assert result.why_interesting  # non-empty


def test_rank_candidate_heavily_audited_scores_low() -> None:
    c = _audited(
        tvl_usd=200_000,
        days_old=200,
        users=100,
        audit_density=10,
        display_name="Boring DEX",
    )
    result = rank_candidate(c, scan_date=date(2026, 4, 13))
    assert result.priority_score < 5.0  # should be filtered out
    assert result.audit_gap_score == 0.0
    assert result.edge_match_score == 0.0


def test_rank_all_filters_and_sorts() -> None:
    high = _audited(tvl_usd=5_000_000, days_old=10, audit_density=0,
                    display_name="Leverage Vault")
    mid = _audited(tvl_usd=300_000, days_old=100, audit_density=1,
                   display_name="Medium Protocol")
    low = _audited(tvl_usd=150_000, days_old=300, audit_density=10,
                   display_name="Ancient DEX")

    ranked = rank_all([low, high, mid], scan_date=date(2026, 4, 13))

    # Low-priority "Ancient DEX" should be filtered out by cutoff
    slugs = [r.target_name for r in ranked]
    assert "test-protocol" in slugs  # both high and mid share target_name from fixture
    # High should rank first
    assert ranked[0].display_name == "Leverage Vault"
    assert ranked[0].priority_score > ranked[-1].priority_score


def test_rank_all_respects_cap() -> None:
    """50+ candidates should be capped at `cap`."""
    many = [
        _audited(tvl_usd=5_000_000, days_old=10, audit_density=0)
        for _ in range(60)
    ]
    ranked = rank_all(many, scan_date=date(2026, 4, 13), cap=20)
    assert len(ranked) == 20


def test_priority_cutoff_constant() -> None:
    assert PRIORITY_CUTOFF == 5.0
