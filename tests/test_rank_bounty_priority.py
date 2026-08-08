"""Tests for the 12-criteria bounty target-selection formula."""

from __future__ import annotations

from datetime import date

import pytest

from tvl_scanner.models import (
    AuditedCandidate,
    BountyProfile,
    Chain,
    DiscoverySource,
    Language,
    RewardTier,
)
from tvl_scanner.rank.bounty_priority import (
    _WEIGHTS,
    NEUTRAL,
    architecture_score,
    audit_history_score,
    bounty_calc_score,
    bounty_size_score,
    competition_score,
    known_issues_score,
    program_age_score,
    program_update_score,
    rank_all_bounty,
    rank_candidate_bounty,
    resolution_quality_score,
    upgrade_activity_score,
)

SCAN = date(2026, 8, 8)


def _profile(**overrides: object) -> BountyProfile:
    return BountyProfile(**overrides)  # type: ignore[arg-type]


def _candidate(
    *,
    profile: BountyProfile | None = None,
    tvl_usd: float = 5_000_000,
    tvl_resolved: bool = True,
    audit_density: int = 0,
    audit_resolved: bool = True,
    display_name: str = "Acme Protocol",
    protocol_type: str = "Lending on ethereum",
) -> AuditedCandidate:
    return AuditedCandidate(
        chain=Chain.ETHEREUM,
        address="0x" + "ab" * 20,
        tvl_usd=tvl_usd,
        tvl_resolved=tvl_resolved,
        first_seen=date(2026, 2, 8),
        source=DiscoverySource.IMMUNEFI_CATALOG,
        target_name="acme",
        display_name=display_name,
        protocol_type=protocol_type,
        languages=[Language.SOLIDITY],
        bounty_program="immunefi",
        bounty_url="https://immunefi.com/bug-bounty/acme",
        bounty_max_payout_usd=250_000,
        bounty_profile=profile,
        audit_density_score=audit_density,
        under_audited=audit_density <= 2,
        audit_record_resolved=audit_resolved,
    )


def test_weights_sum_to_one() -> None:
    assert sum(_WEIGHTS) == pytest.approx(1.0)


# --- Every sub-score is neutral when the profile is missing ---------------


@pytest.mark.parametrize(
    "fn",
    [
        bounty_size_score,
        bounty_calc_score,
        program_update_score,
        program_age_score,
        known_issues_score,
        architecture_score,
        upgrade_activity_score,
        competition_score,
        resolution_quality_score,
    ],
)
def test_missing_profile_scores_neutral(fn: object) -> None:
    """A candidate with no program record is neither rewarded nor punished."""
    assert fn(None) == NEUTRAL  # type: ignore[operator]


# --- 2. Maximum + minimum bounty ------------------------------------------


def test_bounty_size_is_log_scaled_on_the_ceiling() -> None:
    assert bounty_size_score(_profile(max_bounty_usd=10_000)) == pytest.approx(0.0)
    assert bounty_size_score(_profile(max_bounty_usd=100_000)) == pytest.approx(5.0)
    assert bounty_size_score(_profile(max_bounty_usd=1_000_000)) == pytest.approx(10.0)
    # Above $1M the ceiling term saturates rather than running away.
    assert bounty_size_score(_profile(max_bounty_usd=10_000_000)) == pytest.approx(10.0)


def test_critical_floor_pulls_the_score_toward_realistic_value() -> None:
    """Two programs with the same headline separate on what a critical floors at."""
    generous = bounty_size_score(
        _profile(max_bounty_usd=1_000_000, critical_min_usd=100_000)
    )
    stingy = bounty_size_score(_profile(max_bounty_usd=1_000_000, critical_min_usd=1_000))
    assert generous > stingy
    # Ceiling alone would score both a flat 10.
    assert stingy < 10.0
    assert bounty_size_score(_profile(max_bounty_usd=1_000_000)) == pytest.approx(10.0)


def test_zero_max_bounty_scores_zero_but_missing_scores_neutral() -> None:
    assert bounty_size_score(_profile(max_bounty_usd=0)) == 0.0
    assert bounty_size_score(_profile(max_bounty_usd=None)) == NEUTRAL


# --- 3. Bounty calculation -------------------------------------------------


def test_percentage_of_funds_at_risk_beats_a_flat_payout() -> None:
    scaling = bounty_calc_score(
        _profile(reward_model="range", reward_calculation_percentage=10)
    )
    flat = bounty_calc_score(_profile(reward_model="fixed"))
    discretionary = bounty_calc_score(_profile(reward_model="up_to"))
    assert scaling > flat > discretionary


def test_ten_percent_rule_lifts_the_model_score() -> None:
    without = bounty_calc_score(_profile(reward_model="range"))
    with_rule = bounty_calc_score(
        _profile(reward_model="range", ten_percent_economic_rule=True)
    )
    assert with_rule > without


def test_payout_ratio_dominates_a_cap_that_binds() -> None:
    """A $50K cap over $2B is 0.0025% — no reward model rescues that."""
    good_ratio = bounty_calc_score(
        _profile(
            reward_model="range",
            reward_calculation_percentage=10,
            max_payout_vs_tvl_pct=10.0,
        )
    )
    bad_ratio = bounty_calc_score(
        _profile(
            reward_model="range",
            reward_calculation_percentage=10,
            max_payout_vs_tvl_pct=0.0025,
        )
    )
    assert good_ratio == pytest.approx(10.0)
    assert bad_ratio < 6.0


def test_unresolved_tvl_leaves_the_model_score_standing_alone() -> None:
    profile = _profile(reward_model="fixed")
    assert bounty_calc_score(profile) == pytest.approx(4.0)


# --- 4-5. Update recency and program age ----------------------------------


def test_program_update_decays_with_staleness() -> None:
    assert program_update_score(_profile(days_since_program_update=7)) == 10.0
    assert program_update_score(_profile(days_since_program_update=730)) == 0.0
    mid = program_update_score(_profile(days_since_program_update=380))
    assert 0.0 < mid < 10.0
    # Unknown must not read as maximally stale.
    assert program_update_score(_profile()) == NEUTRAL


def test_young_programs_score_above_picked_over_ones() -> None:
    assert program_age_score(_profile(program_age_days=30)) == 10.0
    assert program_age_score(_profile(program_age_days=90)) == 10.0
    assert program_age_score(_profile(program_age_days=1095)) == 0.0
    assert program_age_score(_profile(program_age_days=2000)) == 0.0
    assert program_age_score(_profile(program_age_days=600)) > program_age_score(
        _profile(program_age_days=900)
    )


# --- 6. Known issues -------------------------------------------------------


def test_known_issues_penalty_is_gentle_then_floors() -> None:
    assert known_issues_score(_profile(known_issue_count=0)) == 10.0
    assert known_issues_score(_profile(known_issue_count=1)) == pytest.approx(8.5)
    assert known_issues_score(_profile(known_issue_count=37)) == 0.0


# --- 7. Audit history ------------------------------------------------------


def test_stale_audit_reopens_the_audit_gap() -> None:
    """An 18-month-old report no longer describes actively developed code."""
    fresh = audit_history_score(
        _candidate(audit_density=3, profile=_profile(days_since_latest_audit=60))
    )
    stale = audit_history_score(
        _candidate(audit_density=3, profile=_profile(days_since_latest_audit=1095))
    )
    assert fresh == pytest.approx(4.0)  # 10 - 2*3, no bonus
    assert stale == pytest.approx(7.0)  # + the full 3-point staleness bonus


def test_staleness_bonus_never_applies_to_an_unresolved_record() -> None:
    """'We found no audit' plus 'it is old' is one unknown, not two."""
    score = audit_history_score(
        _candidate(
            audit_density=0,
            audit_resolved=False,
            profile=_profile(days_since_latest_audit=2000),
        )
    )
    assert score == NEUTRAL


def test_audit_gap_is_capped_at_ten() -> None:
    score = audit_history_score(
        _candidate(audit_density=0, profile=_profile(days_since_latest_audit=2000))
    )
    assert score == 10.0


# --- 8. Architecture -------------------------------------------------------


def test_scope_sweet_spot_beats_both_extremes() -> None:
    tiny = architecture_score(_profile(smart_contract_assets=1))
    sweet = architecture_score(_profile(smart_contract_assets=10))
    wide = architecture_score(_profile(smart_contract_assets=60))
    unreadable = architecture_score(_profile(smart_contract_assets=355))
    assert sweet > tiny
    assert sweet > wide > unreadable


def test_web_heavy_scope_is_discounted() -> None:
    """Web/app assets pay a different skillset than this scanner's user has."""
    contracts_only = architecture_score(_profile(smart_contract_assets=10))
    mostly_web = architecture_score(
        _profile(smart_contract_assets=10, web_app_assets=40)
    )
    assert contracts_only > mostly_web


def test_primacy_of_impact_with_no_listed_contracts_is_workable_not_zero() -> None:
    assert architecture_score(
        _profile(smart_contract_assets=0, web_app_assets=1, primacy_of_impact=True)
    ) > architecture_score(_profile(smart_contract_assets=0, web_app_assets=1))


# --- 9. Recent upgrades / scope churn -------------------------------------


def test_fresh_scope_outscores_settled_scope() -> None:
    fresh = upgrade_activity_score(
        _profile(days_since_newest_asset=10, assets_added_90d=5)
    )
    settled = upgrade_activity_score(
        _profile(days_since_newest_asset=400, assets_added_90d=0)
    )
    assert fresh == pytest.approx(10.0)
    assert settled == 0.0


def test_unknown_scope_dates_score_neutral() -> None:
    assert upgrade_activity_score(_profile()) == NEUTRAL


# --- 11. Competition -------------------------------------------------------


def test_invite_only_floors_competition_score() -> None:
    assert competition_score(_profile(invite_only=True, max_bounty_usd=50_000)) == 0.0


def test_boosts_and_headline_payouts_signal_crowding() -> None:
    quiet = competition_score(_profile(max_bounty_usd=40_000, kyc_required=True))
    crowded = competition_score(
        _profile(max_bounty_usd=5_000_000, is_boosted=True, boosted_researcher_count=30)
    )
    assert quiet > NEUTRAL
    assert crowded < NEUTRAL
    assert crowded == 0.0


def test_competition_ignores_program_age() -> None:
    """Criterion 5 already scores age — double-counting would double its weight."""
    young = competition_score(_profile(max_bounty_usd=100_000, program_age_days=10))
    old = competition_score(_profile(max_bounty_usd=100_000, program_age_days=2000))
    assert young == old


# --- 12. Resolution quality ------------------------------------------------


def test_documented_payouts_and_escrow_raise_resolution_quality() -> None:
    bare = resolution_quality_score(_profile())
    strong = resolution_quality_score(
        _profile(
            boosted_total_paid_usd=100_000,
            boosted_researcher_count=5,
            vault_escrow=True,
            safe_harbor=True,
            arbitration_available=True,
            responsible_publication_category="category_1",
        )
    )
    assert bare == NEUTRAL
    assert strong == 10.0


def test_paid_mediation_is_the_one_negative_signal() -> None:
    assert resolution_quality_score(_profile(no_free_mediation=True)) < NEUTRAL


# --- Composite -------------------------------------------------------------


def test_rank_candidate_populates_every_subscore_and_marks_the_formula() -> None:
    record = rank_candidate_bounty(
        _candidate(
            profile=_profile(
                max_bounty_usd=250_000,
                critical_min_usd=50_000,
                reward_model="range",
                reward_calculation_percentage=10,
                ten_percent_economic_rule=True,
                program_age_days=90,
                days_since_program_update=7,
                smart_contract_assets=8,
                days_since_newest_asset=20,
                assets_added_90d=3,
            )
        ),
        scan_date=SCAN,
    )
    assert record.priority_formula == "bounty"
    for field in (
        "bounty_size_score",
        "bounty_calc_score",
        "program_update_score",
        "program_age_score",
        "known_issues_score",
        "architecture_score",
        "upgrade_activity_score",
        "competition_score",
        "resolution_quality_score",
    ):
        assert getattr(record, field) is not None, field
    assert 0.0 <= record.priority_score <= 10.0
    # bounty_score is a constant across this population and carries no weight.
    assert record.bounty_score == 10.0


def test_why_interesting_leads_with_the_payout() -> None:
    record = rank_candidate_bounty(
        _candidate(
            profile=_profile(
                max_bounty_usd=250_000,
                critical_min_usd=50_000,
                max_payout_vs_tvl_pct=5.0,
                assets_added_90d=2,
                known_issue_count=1,
            )
        ),
        scan_date=SCAN,
    )
    assert record.why_interesting.startswith("$250,000 max / $50,000 critical floor")
    assert "5% of funds at risk" in record.why_interesting
    assert "2 contract(s) added to scope in 90d" in record.why_interesting
    assert "1 known issue(s)" in record.why_interesting


def test_focus_areas_lead_with_program_signals() -> None:
    record = rank_candidate_bounty(
        _candidate(
            profile=_profile(
                assets_added_90d=4,
                days_since_newest_asset=12,
                known_issue_count=2,
                days_since_latest_audit=900,
                auditors=["Zenith"],
                critical_impacts=["Direct theft of any user funds"],
            )
        ),
        scan_date=SCAN,
    )
    joined = " | ".join(record.focus_areas_suggested)
    assert "entered bounty scope in the last 90 days" in joined
    assert "900d old" in joined
    assert "published known issue" in joined
    # Code-level hints from the base formula are still appended after them.
    assert "oracle" in joined.lower()


def test_invite_only_is_flagged_loudly_in_the_record() -> None:
    record = rank_candidate_bounty(
        _candidate(profile=_profile(invite_only=True)), scan_date=SCAN
    )
    assert "INVITE-ONLY" in record.why_interesting
    assert any("Invite-only" in area for area in record.focus_areas_suggested)


def test_a_candidate_with_no_profile_still_ranks() -> None:
    """The `run` path never builds a profile; ranking must not require one."""
    record = rank_candidate_bounty(_candidate(profile=None), scan_date=SCAN)
    assert record.priority_formula == "bounty"
    assert record.bounty_size_score == NEUTRAL


# --- rank_all_bounty -------------------------------------------------------


def test_rank_all_sorts_filters_and_caps() -> None:
    strong = _candidate(
        profile=_profile(
            max_bounty_usd=1_000_000,
            critical_min_usd=100_000,
            program_age_days=30,
            days_since_program_update=5,
            smart_contract_assets=10,
            days_since_newest_asset=10,
            assets_added_90d=5,
            reward_model="range",
            reward_calculation_percentage=10,
        )
    )
    weak = _candidate(
        audit_density=6,
        profile=_profile(
            max_bounty_usd=5_000,
            program_age_days=2000,
            days_since_program_update=720,
            known_issue_count=20,
            smart_contract_assets=300,
            days_since_newest_asset=900,
            is_boosted=True,
            no_free_mediation=True,
        ),
    )
    ranked = rank_all_bounty([weak, strong], scan_date=SCAN, cutoff=0.0, cap=10)
    assert [r.priority_score for r in ranked] == sorted(
        (r.priority_score for r in ranked), reverse=True
    )
    assert ranked[0].priority_score > ranked[1].priority_score

    assert rank_all_bounty([weak, strong], scan_date=SCAN, cutoff=0.0, cap=1) == ranked[:1]
    # The weak program falls below a normal cutoff; the strong one clears it.
    kept = rank_all_bounty([weak, strong], scan_date=SCAN, cutoff=5.0, cap=10)
    assert len(kept) == 1


def test_exclude_invite_only_is_opt_in() -> None:
    iop = _candidate(profile=_profile(invite_only=True, max_bounty_usd=500_000))
    assert len(rank_all_bounty([iop], scan_date=SCAN, cutoff=0.0)) == 1
    assert (
        rank_all_bounty([iop], scan_date=SCAN, cutoff=0.0, exclude_invite_only=True) == []
    )


def test_exclude_slugs_is_case_insensitive() -> None:
    c = _candidate(profile=_profile(max_bounty_usd=500_000))
    assert rank_all_bounty([c], scan_date=SCAN, cutoff=0.0, exclude_slugs={"ACME"}) == []


def test_reward_tier_round_trips_through_model_dump() -> None:
    """The profile crosses Stage 3 as a plain dict — it must re-validate."""
    candidate = _candidate(
        profile=_profile(
            reward_tiers=[
                RewardTier(
                    severity="critical",
                    asset_type="smart_contract",
                    reward_model="range",
                    min_usd=50_000,
                    max_usd=250_000,
                )
            ]
        )
    )
    record = rank_candidate_bounty(candidate, scan_date=SCAN)
    assert record.bounty_profile is not None
    assert record.bounty_profile.reward_tiers[0].severity == "critical"


def test_pay_to_submit_scores_opposite_ways_on_11_and_12() -> None:
    """A per-report fee thins the field (good) and costs the researcher (bad).

    Netting them into one number would hide both; each is scored where it belongs.
    """
    plain = _profile(max_bounty_usd=250_000)
    fee = _profile(max_bounty_usd=250_000, pay_to_submit=True)
    assert competition_score(fee) > competition_score(plain)
    assert resolution_quality_score(fee) < resolution_quality_score(plain)


def test_subscription_tier_is_deliberately_unscored() -> None:
    """It describes what the project buys from Immunefi, not the hunt."""
    plain = _profile(max_bounty_usd=250_000)
    elite = _profile(max_bounty_usd=250_000, subscription_plan="Elite")
    assert competition_score(elite) == competition_score(plain)
    assert resolution_quality_score(elite) == resolution_quality_score(plain)


def test_researcher_level_gate_is_flagged_not_scored() -> None:
    """Whether a level gate blocks YOU depends on your level, which is unknowable here."""
    plain = _profile(max_bounty_usd=250_000)
    gated = _profile(max_bounty_usd=250_000, researcher_level_gate="Intermediate level or higher")
    assert competition_score(gated) == competition_score(plain)
    assert resolution_quality_score(gated) == resolution_quality_score(plain)
