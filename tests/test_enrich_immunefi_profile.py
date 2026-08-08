"""Tests for the Immunefi bounty-program profile extractor.

Fixtures mirror the shape of the live `bounties.json` catalogue (247 programs
as of 2026-08), including the awkward cases that motivated each guard: reward
rows with no severity, future-dated audits, testnet-only assets and programs
that omit whole sections.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tvl_scanner.enrich.immunefi_profile import (
    attach_payout_ratio,
    build_profile,
)

SCAN = date(2026, 8, 8)


def _ts(iso_date: str) -> str:
    """Immunefi publishes ISO-8601 with a Z suffix."""
    return f"{iso_date}T12:00:00.000Z"


def _program(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "slug": "acme",
        "project": "Acme",
        "kyc": False,
        "maxBounty": 250_000,
        "launchDate": _ts("2026-05-10"),  # 90 days before SCAN
        "updatedDate": _ts("2026-08-01"),  # 7 days before SCAN
        "rewards": [
            {
                "severity": "critical",
                "assetType": "smart_contract",
                "rewardModel": "range",
                "minReward": 50_000,
                "maxReward": 250_000,
                "rewardCalculationPercentage": 10,
                "pocRequired": True,
            },
            {
                "severity": "high",
                "assetType": "smart_contract",
                "rewardModel": "range",
                "minReward": 10_000,
                "maxReward": 50_000,
            },
        ],
        "tenPercentEconomicRule": True,
        "assets": [
            {
                "type": "smart_contract",
                "url": "https://etherscan.io/address/0x" + "ab" * 20,
                "addedAt": _ts("2026-07-20"),
                "revision": 0,
            }
        ],
        "audits": [{"auditor": "Zenith", "date": _ts("2026-03-17"), "url": "https://x/y"}],
        "knownIssues": [],
        "ecosystem": ["ETH"],
        "programType": ["Smart Contract"],
        "projectType": ["Defi"],
        "impacts": [
            {
                "type": "smart_contract",
                "severity": "critical",
                "title": "Direct theft of any user funds",
            },
            {"type": "smart_contract", "severity": "high", "title": "Griefing"},
        ],
        "features": [],
        "immunefiStandard": True,
    }
    base.update(overrides)
    return base


# --- 2. Maximum + minimum bounty ------------------------------------------


def test_reward_band_and_floors_extracted() -> None:
    p = build_profile(_program(), scan_date=SCAN)
    assert p.max_bounty_usd == 250_000
    assert p.critical_min_usd == 50_000
    assert p.critical_max_usd == 250_000
    # Lowest floor across every smart-contract tier, not just critical.
    assert p.min_bounty_usd == 10_000
    assert [t.severity for t in p.reward_tiers] == ["critical", "high"]


def test_fixed_reward_supersedes_the_range() -> None:
    """A `fixedReward` row pays flat regardless of the min/max columns."""
    p = build_profile(
        _program(
            rewards=[
                {
                    "severity": "critical",
                    "assetType": "smart_contract",
                    "rewardModel": "fixed",
                    "minReward": 1_000,
                    "maxReward": 5_000,
                    "fixedReward": 5_000,
                }
            ]
        ),
        scan_date=SCAN,
    )
    assert p.critical_min_usd == 5_000
    assert p.critical_max_usd == 5_000


def test_reward_row_without_severity_is_dropped() -> None:
    """Competition payout-pool rows carry no severity and are not a tier."""
    p = build_profile(
        _program(rewards=[{"payout": 50_000, "level": 1}, *_program()["rewards"]]),
        scan_date=SCAN,
    )
    assert len(p.reward_tiers) == 2
    assert all(t.severity for t in p.reward_tiers)


def test_smart_contract_tiers_sort_ahead_of_web_tiers() -> None:
    p = build_profile(
        _program(
            rewards=[
                {"severity": "critical", "assetType": "websites_and_applications", "maxReward": 10},
                {"severity": "low", "assetType": "smart_contract", "maxReward": 20},
            ]
        ),
        scan_date=SCAN,
    )
    assert [t.asset_type for t in p.reward_tiers] == [
        "smart_contract",
        "websites_and_applications",
    ]


# --- 3. Bounty calculation -------------------------------------------------


def test_payout_basis_reads_as_prose() -> None:
    p = build_profile(_program(), scan_date=SCAN)
    assert p.reward_model == "range"
    assert p.reward_calculation_percentage == 10
    assert p.ten_percent_economic_rule is True
    assert p.poc_required_for_critical is True
    assert "10% of funds at risk" in p.payout_basis
    assert "$250,000" in p.payout_basis
    assert "10% economic rule" in p.payout_basis


def test_fixed_payout_basis_flags_that_it_does_not_scale() -> None:
    p = build_profile(
        _program(
            tenPercentEconomicRule=False,
            rewards=[
                {
                    "severity": "critical",
                    "assetType": "smart_contract",
                    "rewardModel": "fixed",
                    "fixedReward": 5_000,
                }
            ],
        ),
        scan_date=SCAN,
    )
    assert "does NOT scale" in p.payout_basis


def test_payout_ratio_needs_resolved_tvl() -> None:
    p = build_profile(_program(), scan_date=SCAN)
    assert p.max_payout_vs_tvl_pct is None

    attach_payout_ratio(p, 25_000_000.0, True)
    assert p.max_payout_vs_tvl_pct == 1.0  # $250K of $25M

    # An unresolved TVL is a 0.0 placeholder meaning UNKNOWN — it must not
    # produce a division or a confident zero.
    attach_payout_ratio(p, 0.0, False)
    assert p.max_payout_vs_tvl_pct is None


# --- 4-5. Last update / program age ---------------------------------------


def test_program_age_and_update_recency() -> None:
    p = build_profile(_program(), scan_date=SCAN)
    assert p.program_age_days == 90
    assert p.days_since_program_update == 7
    assert p.is_time_boxed is False


def test_end_date_marks_a_time_boxed_competition() -> None:
    p = build_profile(_program(endDate=_ts("2026-09-01")), scan_date=SCAN)
    assert p.is_time_boxed is True
    assert p.program_ends_at == date(2026, 9, 1)


def test_future_launch_date_clamps_to_zero_rather_than_negative() -> None:
    p = build_profile(_program(launchDate=_ts("2026-12-01")), scan_date=SCAN)
    assert p.program_age_days == 0


def test_malformed_dates_degrade_to_none() -> None:
    p = build_profile(_program(launchDate="soon", updatedDate=None), scan_date=SCAN)
    assert p.program_launched_at is None
    assert p.program_age_days is None
    assert p.days_since_program_update is None


# --- 6. Known issues -------------------------------------------------------


def test_known_issues_parsed_with_latest_update() -> None:
    p = build_profile(
        _program(
            knownIssues=[
                {
                    "description": "Governor quorum can be met with abstain votes.",
                    "link": "https://github.com/x/y/issues/1",
                    "lastUpdatedAt": _ts("2025-08-25"),
                    "relatedImpactInScope": "smart_contract",
                },
                {"description": "Reserve cap drift.", "lastUpdatedAt": _ts("2026-01-05")},
                {"description": "   "},  # blank — dropped
            ]
        ),
        scan_date=SCAN,
    )
    assert p.known_issue_count == 2
    assert p.known_issues_last_updated == date(2026, 1, 5)
    assert p.known_issues[0].link == "https://github.com/x/y/issues/1"


def test_no_known_issues_is_zero_not_unknown() -> None:
    p = build_profile(_program(), scan_date=SCAN)
    assert p.known_issue_count == 0
    assert p.known_issues == []


# --- 7. Audit history ------------------------------------------------------


def test_audit_recency_and_auditors() -> None:
    p = build_profile(_program(), scan_date=SCAN)
    assert p.audit_count == 1
    assert p.latest_audit_at == date(2026, 3, 17)
    assert p.days_since_latest_audit == 144
    assert p.auditors == ["Zenith"]


def test_future_dated_audit_is_ignored_for_recency() -> None:
    """A date ahead of the scan is a data error, not a fresh review."""
    p = build_profile(
        _program(
            audits=[
                {"auditor": "Zenith", "date": _ts("2026-03-17")},
                {"auditor": "Ghost", "date": _ts("2027-01-01")},
            ]
        ),
        scan_date=SCAN,
    )
    assert p.audit_count == 2
    assert p.latest_audit_at == date(2026, 3, 17)


# --- 8. Architecture -------------------------------------------------------


def test_asset_types_counted_separately() -> None:
    p = build_profile(
        _program(
            assets=[
                {"type": "smart_contract", "url": "https://etherscan.io/address/0x1"},
                {"type": "smart_contract", "url": "https://arbiscan.io/address/0x2"},
                {"type": "websites_and_applications", "url": "https://acme.xyz"},
                {"type": "blockchain_dlt", "url": "https://acme.xyz/node"},
            ]
        ),
        scan_date=SCAN,
    )
    assert (p.smart_contract_assets, p.web_app_assets, p.blockchain_dlt_assets) == (2, 1, 1)


def test_only_critical_smart_contract_impacts_are_kept() -> None:
    p = build_profile(_program(), scan_date=SCAN)
    assert p.critical_impacts == ["Direct theft of any user funds"]


def test_primacy_of_impact_flag() -> None:
    p = build_profile(
        _program(
            assets=[
                {
                    "type": "smart_contract",
                    "url": "https://immunefi.com/",
                    "isPrimacyOfImpact": True,
                }
            ]
        ),
        scan_date=SCAN,
    )
    assert p.primacy_of_impact is True


# --- 9. Recent upgrades / scope churn --------------------------------------


def test_scope_churn_counts_only_recent_smart_contract_additions() -> None:
    p = build_profile(
        _program(
            assets=[
                {"type": "smart_contract", "url": "u1", "addedAt": _ts("2026-07-20")},  # 19d
                {"type": "smart_contract", "url": "u2", "addedAt": _ts("2026-06-01")},  # 68d
                {"type": "smart_contract", "url": "u3", "addedAt": _ts("2025-01-01")},  # old
                # A web asset added yesterday is not fresh on-chain surface.
                {"type": "websites_and_applications", "url": "u4", "addedAt": _ts("2026-08-07")},
            ]
        ),
        scan_date=SCAN,
    )
    assert p.assets_added_90d == 2
    assert p.newest_asset_added_at == date(2026, 7, 20)
    assert p.days_since_newest_asset == 19


def test_revision_counter_tracked() -> None:
    p = build_profile(
        _program(
            assets=[
                {"type": "smart_contract", "url": "u1", "revision": 2},
                {"type": "smart_contract", "url": "u2", "revision": 0},
            ]
        ),
        scan_date=SCAN,
    )
    assert p.assets_revised == 1


# --- 11-12. Competition and resolution quality -----------------------------


def test_feature_flags_are_substring_matched() -> None:
    p = build_profile(
        _program(
            kyc=True,
            features=[
                "Pay to Mediate - No Free Mediations",
                "Managed Triage: Signal Booster",
                "Vault",
                "Arbitration",
                "Safe Harbor Documents Signed",
                "Attackathon",
            ],
        ),
        scan_date=SCAN,
    )
    assert p.kyc_required is True
    assert p.pay_to_mediate is True
    assert p.no_free_mediation is True
    assert p.managed_triage is True
    assert p.vault_escrow is True
    assert p.arbitration_available is True
    assert p.safe_harbor is True
    assert p.is_boosted is True


def test_invite_only_from_either_flag_or_feature() -> None:
    assert build_profile(_program(inviteOnly=True), scan_date=SCAN).invite_only is True
    assert (
        build_profile(
            _program(features=["IOP (Invite Only Program)"]), scan_date=SCAN
        ).invite_only
        is True
    )
    assert build_profile(_program(), scan_date=SCAN).invite_only is False


def test_leaderboard_totals_only_count_paid_researchers() -> None:
    p = build_profile(
        _program(
            boostedLeaderboard=[
                {"name": "a", "totalEarnings": 45_845},
                {"name": "b", "totalEarnings": 23_295},
                {"name": "c", "totalEarnings": 0},  # placed but unpaid
            ]
        ),
        scan_date=SCAN,
    )
    assert p.boosted_researcher_count == 2
    assert p.boosted_total_paid_usd == 69_140


def test_rewards_pool_alone_marks_a_competition() -> None:
    p = build_profile(_program(rewardsPool=250_000), scan_date=SCAN)
    assert p.is_boosted is True


# --- Robustness ------------------------------------------------------------


def test_empty_program_produces_neutral_profile_without_raising() -> None:
    """One malformed program must never abort a 247-program scan."""
    p = build_profile({}, scan_date=SCAN)
    assert p.max_bounty_usd is None
    assert p.known_issue_count == 0
    assert p.smart_contract_assets == 0
    assert p.program_age_days is None
    assert p.payout_basis == "no critical smart-contract tier published"


def test_wrong_typed_sections_are_skipped_not_fatal() -> None:
    p = build_profile(
        _program(
            rewards="nonsense",
            knownIssues=[None, 42],
            assets=[None, "x"],
            audits=["bad"],
            features="Vault",
            ecosystem=None,
        ),
        scan_date=SCAN,
    )
    assert p.reward_tiers == []
    assert p.known_issue_count == 0
    assert p.smart_contract_assets == 0
    assert p.audit_count == 0
    assert p.ecosystems == []
    # A bare string `features` is still usable — normalized to a one-item list.
    assert p.vault_escrow is True


# --- Pay to Submit / subscription tier -------------------------------------


def test_pay_to_submit_detected() -> None:
    assert build_profile(_program(features=["Pay to Submit"]), scan_date=SCAN).pay_to_submit
    assert not build_profile(_program(), scan_date=SCAN).pay_to_submit
    # Must not be confused with the (much more common) mediation fee.
    assert not build_profile(
        _program(features=["Pay to Mediate"]), scan_date=SCAN
    ).pay_to_submit


def test_subscription_tier_is_parsed_from_the_label() -> None:
    for label, tier in (
        ("Subscription Plan: Elite", "Elite"),
        ("Subscription Plan: Pro", "Pro"),
        ("Subscription Plan: Essential", "Essential"),
    ):
        assert build_profile(_program(features=[label]), scan_date=SCAN).subscription_plan == tier


def test_subscription_label_without_a_tier_is_kept_whole() -> None:
    """An unrecognised future shape must surface, not silently vanish."""
    p = build_profile(_program(features=["Subscription Plan"]), scan_date=SCAN)
    assert p.subscription_plan == "Subscription Plan"


def test_no_subscription_plan_is_none() -> None:
    assert build_profile(_program(features=["Vault"]), scan_date=SCAN).subscription_plan is None
