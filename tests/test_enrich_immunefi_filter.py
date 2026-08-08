"""Tests for ProgramFilter and the drop-reason funnel."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from tvl_scanner.enrich import immunefi_filter as f
from tvl_scanner.enrich.immunefi_filter import FilterFunnel, ProgramFilter
from tvl_scanner.models import (
    BountyProfile,
    Chain,
    DiscoverySource,
    EnrichedCandidate,
    Language,
)

SCAN = date(2026, 8, 8)


def _cand(
    *,
    profile: BountyProfile | None = None,
    target_name: str = "acme",
    display_name: str = "Acme Protocol",
    defillama_slug: str | None = None,
    languages: list[Language] | None = None,
    tvl_usd: float = 5_000_000,
    tvl_resolved: bool = True,
    **profile_fields: Any,
) -> EnrichedCandidate:
    if profile is None:
        profile = BountyProfile(**profile_fields)
    return EnrichedCandidate(
        chain=Chain.ETHEREUM,
        address="0x" + "ab" * 20,
        tvl_usd=tvl_usd,
        tvl_resolved=tvl_resolved,
        first_seen=date(2026, 2, 8),
        source=DiscoverySource.IMMUNEFI_CATALOG,
        target_name=target_name,
        display_name=display_name,
        defillama_slug=defillama_slug,
        protocol_type="Lending on ethereum",
        languages=languages or [Language.SOLIDITY],
        bounty_program="immunefi",
        bounty_profile=profile,
    )


def _reject(candidate: EnrichedCandidate, **filter_fields: Any) -> str | None:
    return ProgramFilter(**filter_fields).reject_reason(candidate, scan_date=SCAN)


# --- Availability ----------------------------------------------------------


def test_closed_programs_are_dropped_by_default() -> None:
    """59 of 247 live catalogue entries are ended competitions — unsubmittable."""
    closed = _cand(program_ends_at=date(2024, 8, 21), is_time_boxed=True)
    assert _reject(closed) == f.REASON_CLOSED
    assert _reject(closed, include_closed=True) is None


def test_a_program_ending_today_is_still_open() -> None:
    assert _reject(_cand(program_ends_at=SCAN, is_time_boxed=True)) is None


def test_open_ended_programs_are_never_closed() -> None:
    assert _reject(_cand()) is None


def test_closed_is_reported_before_other_failures() -> None:
    """An unsubmittable program fails every other test vacuously."""
    closed_and_poor = _cand(program_ends_at=date(2024, 1, 1), max_bounty_usd=100)
    assert _reject(closed_and_poor, min_max_bounty_usd=1_000_000) == f.REASON_CLOSED


def test_invite_only_filter_is_opt_in() -> None:
    iop = _cand(invite_only=True)
    assert _reject(iop) is None
    assert _reject(iop, exclude_invite_only=True) == f.REASON_INVITE_ONLY


# --- Exclusion list --------------------------------------------------------


@pytest.mark.parametrize("token", ["acme", "ACME", "Acme Protocol", "acme-protocol", "acme-dl"])
def test_exclusion_matches_any_name_the_program_is_known_by(token: str) -> None:
    """A user types back whatever the report showed them — all of it should work."""
    candidate = _cand(defillama_slug="acme-dl")
    assert _reject(candidate, exclude_slugs={token}) == f.REASON_EXCLUDED_SLUG


def test_exclusion_does_not_match_an_unrelated_slug() -> None:
    assert _reject(_cand(), exclude_slugs={"other"}) is None


# --- Economics -------------------------------------------------------------


def test_min_bounty_separates_below_floor_from_unpublished() -> None:
    """The funnel must distinguish 'failed your bar' from 'could not be checked'."""
    assert _reject(_cand(max_bounty_usd=10_000), min_max_bounty_usd=100_000) == f.REASON_BOUNTY_LOW
    assert _reject(_cand(), min_max_bounty_usd=100_000) == f.REASON_BOUNTY_UNKNOWN
    assert _reject(_cand(max_bounty_usd=250_000), min_max_bounty_usd=100_000) is None


def test_critical_floor_filter_falls_back_to_the_lowest_published_floor() -> None:
    assert _reject(_cand(critical_min_usd=50_000), min_critical_floor_usd=25_000) is None
    assert (
        _reject(_cand(critical_min_usd=5_000), min_critical_floor_usd=25_000)
        == f.REASON_FLOOR_LOW
    )
    # No critical tier, but a floor exists elsewhere in the reward table.
    assert _reject(_cand(min_bounty_usd=30_000), min_critical_floor_usd=25_000) is None
    assert _reject(_cand(), min_critical_floor_usd=25_000) == f.REASON_FLOOR_UNKNOWN


def test_tvl_and_ratio_filters_run_only_after_tvl_resolution() -> None:
    """They live in a separate method because the on-chain fallback runs late."""
    poor = _cand(max_bounty_usd=50_000, max_payout_vs_tvl_pct=0.0025)
    filters = ProgramFilter(min_tvl_usd=1_000_000, min_payout_ratio_pct=1.0)
    # Not evaluated by the pre-network pass at all.
    assert filters.reject_reason(poor, scan_date=SCAN) is None
    assert filters.tvl_reject_reason(poor) == f.REASON_RATIO_LOW


def test_min_tvl_distinguishes_low_from_unresolved() -> None:
    low = ProgramFilter(min_tvl_usd=10_000_000)
    assert low.tvl_reject_reason(_cand(tvl_usd=1_000_000)) == f.REASON_TVL_LOW
    assert (
        low.tvl_reject_reason(_cand(tvl_usd=0.0, tvl_resolved=False)) == f.REASON_TVL_UNKNOWN
    )
    assert low.tvl_reject_reason(_cand(tvl_usd=50_000_000)) is None


def test_payout_ratio_unknown_is_its_own_reason() -> None:
    filters = ProgramFilter(min_payout_ratio_pct=1.0)
    assert filters.tvl_reject_reason(_cand()) == f.REASON_RATIO_UNKNOWN
    assert filters.tvl_reject_reason(_cand(max_payout_vs_tvl_pct=5.0)) is None


# --- Program health --------------------------------------------------------


def test_updated_within_drops_dormant_programs() -> None:
    assert _reject(_cand(days_since_program_update=700), updated_within_days=180) == (
        f.REASON_UPDATED_STALE
    )
    assert _reject(_cand(days_since_program_update=30), updated_within_days=180) is None
    assert _reject(_cand(), updated_within_days=180) == f.REASON_UPDATED_UNKNOWN


def test_max_program_age_keeps_only_young_programs() -> None:
    assert _reject(_cand(program_age_days=2000), max_program_age_days=365) == f.REASON_AGE_OLD
    assert _reject(_cand(program_age_days=30), max_program_age_days=365) is None
    assert _reject(_cand(), max_program_age_days=365) == f.REASON_AGE_UNKNOWN


def test_max_known_issues_drops_minefields() -> None:
    assert _reject(_cand(known_issue_count=37), max_known_issues=3) == f.REASON_KNOWN_ISSUES
    assert _reject(_cand(known_issue_count=2), max_known_issues=3) is None
    # Zero is the common case and must never be treated as unknown.
    assert _reject(_cand(), max_known_issues=0) is None


# --- Audit staleness -------------------------------------------------------


def test_audit_older_than_keeps_never_audited_programs() -> None:
    """Never audited is the limiting case of stale coverage, not an exception."""
    assert _reject(_cand(), audit_older_than_days=540) is None
    assert _reject(_cand(days_since_latest_audit=900), audit_older_than_days=540) is None
    assert (
        _reject(_cand(days_since_latest_audit=60), audit_older_than_days=540)
        == f.REASON_AUDIT_RECENT
    )


def test_under_audited_only_is_evaluated_against_stage_3() -> None:
    filters = ProgramFilter(under_audited_only=True)
    assert filters.audit_reject_reason(under_audited=True) is None
    assert filters.audit_reject_reason(under_audited=False) == f.REASON_NOT_UNDER_AUDITED
    assert ProgramFilter().audit_reject_reason(under_audited=False) is None


# --- Scope -----------------------------------------------------------------


def test_scope_bounds_are_inclusive() -> None:
    assert _reject(_cand(smart_contract_assets=355), max_scope_contracts=50) == (
        f.REASON_SCOPE_LARGE
    )
    assert _reject(_cand(smart_contract_assets=50), max_scope_contracts=50) is None
    assert _reject(_cand(smart_contract_assets=1), min_scope_contracts=3) == f.REASON_SCOPE_SMALL
    assert _reject(_cand(smart_contract_assets=3), min_scope_contracts=3) is None


def test_fresh_scope_requires_a_recent_addition() -> None:
    assert _reject(_cand(days_since_newest_asset=20), fresh_scope_days=90) is None
    assert _reject(_cand(days_since_newest_asset=400), fresh_scope_days=90) == (
        f.REASON_SCOPE_STALE
    )
    assert _reject(_cand(), fresh_scope_days=90) == f.REASON_SCOPE_STALE_UNKNOWN


# --- Edge, competition, payout quality -------------------------------------


def test_language_filter_keeps_any_overlap() -> None:
    rust = _cand(languages=[Language.RUST])
    assert _reject(rust, languages={Language.RUST}) is None
    assert _reject(rust, languages={Language.SOLIDITY}) == f.REASON_LANGUAGE
    assert _reject(rust, languages={Language.SOLIDITY, Language.RUST}) is None


def test_kyc_filter_is_three_valued() -> None:
    kyc = _cand(kyc_required=True)
    no_kyc = _cand(kyc_required=False)
    assert _reject(kyc) is None and _reject(no_kyc) is None  # None = both
    assert _reject(kyc, kyc=False) == f.REASON_KYC
    assert _reject(no_kyc, kyc=False) is None


def test_exclude_boosted_and_require_vault() -> None:
    assert _reject(_cand(is_boosted=True), exclude_boosted=True) == f.REASON_BOOSTED
    assert _reject(_cand(), exclude_boosted=True) is None
    assert _reject(_cand(), require_vault=True) == f.REASON_NO_VAULT
    assert _reject(_cand(vault_escrow=True), require_vault=True) is None


# --- Defaults and robustness -----------------------------------------------


def test_default_filter_keeps_an_ordinary_open_program() -> None:
    assert _reject(_cand(max_bounty_usd=1_000, known_issue_count=99, invite_only=True)) is None


def test_is_active_ignores_the_closed_default() -> None:
    assert ProgramFilter().is_active is False
    assert ProgramFilter(include_closed=True).is_active is False
    assert ProgramFilter(min_tvl_usd=1.0).is_active is True


def test_candidate_without_a_profile_is_kept() -> None:
    """A missing profile is a scanner gap, not a property of the program."""
    candidate = _cand()
    candidate.bounty_profile = None
    assert _reject(candidate, min_max_bounty_usd=1_000_000, max_known_issues=0) is None
    # Name-based constraints still apply — they do not need the profile.
    assert _reject(candidate, exclude_slugs={"acme"}) == f.REASON_EXCLUDED_SLUG


# --- Funnel ----------------------------------------------------------------


def test_funnel_counts_and_arithmetic() -> None:
    funnel = FilterFunnel(fetched=100)
    for _ in range(30):
        funnel.drop(f.REASON_CLOSED)
    for _ in range(5):
        funnel.drop(f.REASON_BOUNTY_LOW)
    assert funnel.total_dropped == 35
    assert funnel.kept == 65


def test_funnel_rows_use_the_canonical_order_not_insertion_order() -> None:
    """Stable ordering lets two scans be diffed."""
    funnel = FilterFunnel(fetched=10)
    funnel.drop(f.REASON_BOUNTY_LOW)
    funnel.drop(f.REASON_CLOSED)
    funnel.drop(f.REASON_NO_CHAIN)
    assert [r for r, _ in funnel.rows()] == [
        f.REASON_NO_CHAIN,
        f.REASON_CLOSED,
        f.REASON_BOUNTY_LOW,
    ]


def test_funnel_omits_reasons_that_never_fired() -> None:
    funnel = FilterFunnel(fetched=5)
    funnel.drop(f.REASON_CLOSED)
    assert funnel.rows() == [(f.REASON_CLOSED, 1)]


def test_funnel_reports_an_unregistered_reason() -> None:
    """A future filter must not silently vanish from the accounting."""
    funnel = FilterFunnel(fetched=5)
    funnel.drop("--some-new-flag: nope")
    assert ("--some-new-flag: nope", 1) in funnel.rows()


def test_funnel_render_shows_the_arithmetic() -> None:
    funnel = FilterFunnel(fetched=247)
    for _ in range(86):
        funnel.drop(f.REASON_NO_CHAIN)
    for _ in range(59):
        funnel.drop(f.REASON_CLOSED)
    text = funnel.render()
    assert "247  programs fetched" in text
    assert "-86  " + f.REASON_NO_CHAIN in text
    assert "-59  " + f.REASON_CLOSED in text
    assert "102  candidates kept" in text


def test_funnel_markdown_is_report_ready() -> None:
    funnel = FilterFunnel(fetched=247)
    for _ in range(59):
        funnel.drop(f.REASON_CLOSED)
    md = funnel.render_markdown()
    assert md.startswith("**Filter funnel** — 247 programs fetched:")
    assert f"−59 {f.REASON_CLOSED}" in md
    assert "**188 candidates kept**" in md


def test_funnel_markdown_says_so_when_nothing_was_filtered() -> None:
    assert "no filter removed anything" in FilterFunnel(fetched=12).render_markdown()
