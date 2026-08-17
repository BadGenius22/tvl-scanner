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
    EXCLUSION_TEXT_CHARS,
    RATIO_MIN_TVL_USD,
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


def test_body_minimum_overrides_fixed_headline_when_a_percentage_is_set() -> None:
    """Synthetix: structured row is fixed $100k + 10%; body says minimum $10k.

    Scoring the $100k headline as the Critical *floor* inflated criterion 2.
    The percentage makes the headline the cap; the body is the floor.
    """
    p = build_profile(
        _program(
            rewards=[
                {
                    "severity": "critical",
                    "assetType": "smart_contract",
                    "rewardModel": "fixed",
                    "fixedReward": 100_000,
                    "maxReward": 100_000,
                    "rewardCalculationPercentage": 10,
                }
            ],
            rewardsBody=(
                "For critical Smart Contract bugs, the reward amount is __10%__ "
                "of the funds directly affected up to a maximum of __USD $100,000__. "
                "However, a minimum reward of __USD $10,000__ is to be rewarded."
            ),
        ),
        scan_date=SCAN,
    )
    assert p.critical_min_usd == 10_000
    assert p.critical_max_usd == 100_000
    assert p.payout_basis.startswith("10% of funds at risk")
    assert "minimum $10,000" in p.payout_basis


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

    # Dust / wrong-row TVL is resolved but unusable as a ratio denominator.
    # TruYields ($7) must not produce a 400,000% "pays of funds at risk" score.
    attach_payout_ratio(p, 7.0, True)
    assert p.max_payout_vs_tvl_pct is None
    attach_payout_ratio(p, RATIO_MIN_TVL_USD - 1, True)
    assert p.max_payout_vs_tvl_pct is None
    attach_payout_ratio(p, RATIO_MIN_TVL_USD, True)
    assert p.max_payout_vs_tvl_pct == 2500.0  # $250k / $10k


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


def test_category_label_auditor_is_a_placeholder_not_an_audit() -> None:
    """"All Audits" + a link to the project's own security page is a pointer.

    Twyne's entire audit list was one such row, dated to the launch date, which
    made `days_since_latest_audit` equal `program_age_days` exactly. Criterion 7
    carries the heaviest weight in the formula and was reading that number.
    """
    p = build_profile(
        _program(
            audits=[
                {
                    "auditor": "All Audits",
                    "date": _ts("2026-03-17"),
                    "url": "https://acme.gitbook.io/resources/security",
                }
            ]
        ),
        scan_date=SCAN,
    )
    assert p.audit_count == 1
    assert p.verified_audit_count == 0
    assert p.latest_audit_at is None
    assert p.days_since_latest_audit is None
    assert p.auditors == []
    assert p.audit_records[0].is_placeholder is True
    assert "category label" in (p.audit_records[0].placeholder_reason or "")


def test_audit_dated_to_the_launch_date_is_a_placeholder() -> None:
    """A real firm name does not rescue a row dated the day the bounty listed."""
    p = build_profile(
        _program(audits=[{"auditor": "Zenith", "date": _ts("2026-05-10")}]),  # == launchDate
        scan_date=SCAN,
    )
    assert p.verified_audit_count == 0
    assert p.latest_audit_at is None
    assert "launch date" in (p.audit_records[0].placeholder_reason or "")


def test_real_audits_survive_alongside_placeholders() -> None:
    p = build_profile(
        _program(
            audits=[
                {"auditor": "All Audits", "date": _ts("2026-05-10")},
                {"auditor": "Zenith", "date": _ts("2026-03-17")},
            ]
        ),
        scan_date=SCAN,
    )
    assert (p.audit_count, p.verified_audit_count) == (2, 1)
    assert p.latest_audit_at == date(2026, 3, 17)
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


def test_primacy_placeholder_is_not_counted_as_a_contract() -> None:
    """The sentinel row is not an asset — 61 of 247 live programs publish one.

    Twyne is the worked case: 16 assets, 15 real addresses plus this row. Both
    counts appeared in the same record, and the inflated one fed criterion 8.
    """
    p = build_profile(
        _program(
            assets=[
                {"type": "smart_contract", "url": "https://etherscan.io/address/0x1"},
                {"type": "smart_contract", "url": "https://etherscan.io/address/0x2"},
                {
                    "type": "smart_contract",
                    "url": "https://immunefi.com/",
                    "description": "Primacy of Impact",
                    "isPrimacyOfImpact": True,
                },
            ]
        ),
        scan_date=SCAN,
    )
    assert p.smart_contract_assets == 2
    assert p.primacy_of_impact is True
    # Kept in the table so the record and the program page agree line for line.
    assert len(p.scope_assets) == 3
    assert [a.is_placeholder for a in p.scope_assets] == [False, False, True]


def test_scope_assets_carry_address_repo_and_flags() -> None:
    p = build_profile(
        _program(
            assets=[
                {
                    "type": "smart_contract",
                    "url": "https://arbiscan.io/address/0x" + "ab" * 20 + "#code",
                    "description": "Vault Manager",
                    "addedAt": _ts("2026-07-20"),
                    "revision": 2,
                    "isSafeHarbor": True,
                },
                {
                    "type": "smart_contract",
                    "url": "https://github.com/acme/core/tree/main/src/vault",
                },
                {"type": "smart_contract", "url": "https://sepolia.etherscan.io/address/0x9"},
            ]
        ),
        scan_date=SCAN,
    )
    onchain, repo, testnet = p.scope_assets
    assert onchain.address == "0x" + "ab" * 20
    assert onchain.explorer == "arbiscan.io"
    assert onchain.description == "Vault Manager"
    assert onchain.revision == 2
    assert onchain.safe_harbor is True
    assert repo.repo == "acme/core/tree/main/src/vault"
    assert repo.address is None
    assert p.repo_scoped_assets == 1
    assert testnet.is_testnet is True


def test_impact_table_is_carried_at_every_severity() -> None:
    """Only the critical tier used to survive; the reachable tier decides the hunt."""
    p = build_profile(
        _program(
            impacts=[
                {"type": "smart_contract", "severity": "critical", "title": "Direct theft"},
                {"type": "smart_contract", "severity": "high", "title": "Temporary freezing"},
                {"type": "smart_contract", "severity": "medium", "title": "Griefing"},
                {"type": "websites_and_applications", "severity": "critical", "title": "XSS"},
            ]
        ),
        scan_date=SCAN,
    )
    assert [(i.severity, i.title) for i in p.impacts] == [
        ("critical", "Direct theft"),
        ("high", "Temporary freezing"),
        ("medium", "Griefing"),
        ("critical", "XSS"),
    ]
    # critical_impacts stays the smart-contract critical subset it always was.
    assert p.critical_impacts == ["Direct theft"]


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


# --- Researcher-level submission gate (prose-detected) ---------------------


def test_level_gate_detected_in_program_prose() -> None:
    """Verbatim from Alchemix, the only program stating it in the 2026-08 snapshot."""
    p = build_profile(
        _program(
            programOverview=(
                "Due to the high complexity of our architecture, we are currently focusing "
                "our review bandwidth on reports from researchers at the **Intermediate** "
                "level or higher. If you are at a **Novice** or **Junior** level, level up first."
            )
        ),
        scan_date=SCAN,
    )
    assert p.researcher_level_gate is not None
    assert "Intermediate level or higher" in p.researcher_level_gate
    # Markdown emphasis stripped so the quote reads cleanly in a report.
    assert "**" not in p.researcher_level_gate


def test_defi_junior_senior_tranches_are_not_a_level_gate() -> None:
    """Royco and Strata describe junior/senior *tranches* — the trap this must not hit."""
    for prose in (
        "Its smart contracts divide yield opportunities into senior and junior tranches. "
        "The junior tranche serves as first-loss capital and receives a risk premium.",
        "Each tranche (Junior and Senior) is seeded with at least 10 assets at deployment. "
        "PoCs must initialize both tranches.",
    ):
        assert build_profile(_program(programOverview=prose), scan_date=SCAN).researcher_level_gate is None


def test_level_gate_requires_all_three_signals() -> None:
    """A level name alone, or 'level' alone, must not trip the detector."""
    for prose in (
        "Our senior engineers reviewed the code.",  # level name, no "level", no researcher
        "The contract tracks a level variable for each vault.",  # "level", no name
        "Novice traders should read the docs.",  # name, no "level", no researcher context
    ):
        assert build_profile(_program(programOverview=prose), scan_date=SCAN).researcher_level_gate is None


def test_no_level_gate_is_none() -> None:
    assert build_profile(_program(), scan_date=SCAN).researcher_level_gate is None


# --- PoC requirement, exclusions and resources -----------------------------

# The live catalogue never sets `pocRequired` on a reward row; it states the
# same fact once, program-wide, in `pocPerTypeAndSeverity`. These fixtures drop
# the per-row flag the base fixture carries so the program-list path is what is
# under test.
_REWARDS_WITHOUT_POC: list[dict[str, Any]] = [
    {"severity": "critical", "assetType": "smart_contract", "maxReward": 250_000},
    {"severity": "high", "assetType": "smart_contract", "maxReward": 50_000},
]


def test_poc_requirement_read_from_per_type_and_severity() -> None:
    """Every live program publishes this list and the scanner read none of it.

    The reward rows carry no `pocRequired` in the live catalogue, so every tier
    of every record came out null while the program plainly stated the answer.
    """
    p = build_profile(
        _program(
            rewards=_REWARDS_WITHOUT_POC,
            pocPerTypeAndSeverity=[
                "smart_contract - critical",
                "websites_and_applications - high",
            ],
        ),
        scan_date=SCAN,
    )
    assert p.poc_required_tiers == [
        "smart_contract - critical",
        "websites_and_applications - high",
    ]
    assert p.poc_required_for_critical is True
    by_severity = {t.severity: t.poc_required for t in p.reward_tiers if t.asset_type == "smart_contract"}
    assert by_severity == {"critical": True, "high": False}


def test_explicit_per_row_poc_flag_wins_over_the_program_list() -> None:
    p = build_profile(
        _program(
            rewards=[
                {
                    "severity": "critical",
                    "assetType": "smart_contract",
                    "maxReward": 100_000,
                    "pocRequired": False,
                }
            ],
            pocPerTypeAndSeverity=["smart_contract - critical"],
        ),
        scan_date=SCAN,
    )
    assert p.poc_required_for_critical is False


def test_rewards_body_poc_applies_to_smart_contracts_when_list_is_web_only() -> None:
    """Synthetix publishes pocPerTypeAndSeverity for web only, then says
    Critical and High need a PoC in rewardsBody. That is the SC answer."""
    p = build_profile(
        _program(
            rewards=_REWARDS_WITHOUT_POC,
            pocPerTypeAndSeverity=[
                "websites_and_applications - critical",
                "websites_and_applications - high",
            ],
            rewardsBody=(
                "A PoC is required for the following severity levels:\n"
                "  - Critical\n"
                "  - High\n"
            ),
        ),
        scan_date=SCAN,
    )
    assert p.poc_required_for_critical is True
    by_severity = {
        t.severity: t.poc_required
        for t in p.reward_tiers
        if t.asset_type == "smart_contract"
    }
    assert by_severity == {"critical": True, "high": True}


def test_testnet_assets_are_kept_but_not_counted() -> None:
    p = build_profile(
        _program(
            assets=[
                {"type": "smart_contract", "url": "https://etherscan.io/address/0x1"},
                {
                    "type": "smart_contract",
                    "url": (
                        "https://explorer.solana.com/address/6EZA"
                        "?cluster=devnet"
                    ),
                },
            ]
        ),
        scan_date=SCAN,
    )
    assert p.smart_contract_assets == 1
    assert len(p.scope_assets) == 2
    assert p.scope_assets[1].is_testnet is True


def test_missing_poc_list_leaves_the_requirement_unknown() -> None:
    """Absent data stays None — the convention is unknown, never a silent False."""
    p = build_profile(
        _program(rewards=_REWARDS_WITHOUT_POC, pocPerTypeAndSeverity=[]), scan_date=SCAN
    )
    assert p.poc_required_tiers == []
    assert p.poc_required_for_critical is None


def test_exclusion_sections_are_extracted() -> None:
    p = build_profile(
        _program(
            defaultOutOfScopeGeneral="Best practice recommendations are out of scope.",
            defaultFeasibilityLimitations="Attacks requiring a compromised key are infeasible.",
            defaultProhibitedActivities="No testing on mainnet.",
            customOutOfScopeInformation="The legacy v1 vaults are excluded.",
            customProhibitedActivities=["Do not contact the team directly."],
            prioritizedVulnerabilities="Accounting drift in the credit vaults.",
        ),
        scan_date=SCAN,
    )
    e = p.exclusions
    assert "compromised key" in (e.feasibility_limitations or "")
    assert e.custom_out_of_scope == "The legacy v1 vaults are excluded."
    assert e.custom_prohibited_activities == ["Do not contact the team directly."]
    assert e.prioritized_vulnerabilities == "Accounting drift in the credit vaults."
    assert set(e.published_sections()) == {
        "out_of_scope_general",
        "feasibility_limitations",
        "prohibited_activities",
        "custom_out_of_scope",
        "custom_prohibited_activities",
        "prioritized_vulnerabilities",
    }


def test_exclusion_text_is_capped_not_dropped() -> None:
    p = build_profile(_program(defaultOutOfScopeGeneral="x" * 5_000), scan_date=SCAN)
    assert len(p.exclusions.out_of_scope_general or "") == EXCLUSION_TEXT_CHARS


def test_absent_exclusions_report_no_sections() -> None:
    assert build_profile(_program(), scan_date=SCAN).exclusions.published_sections() == []


def test_resources_collect_site_repo_and_audit_links_without_duplicates() -> None:
    p = build_profile(
        _program(
            websiteUrl="https://acme.xyz",
            githubUrl="https://github.com/acme/core",
            audits=[
                {"auditor": "Zenith", "date": _ts("2026-03-17"), "url": "https://acme.xyz/audit.pdf"},
                {"auditor": "Zenith", "date": _ts("2026-03-18"), "url": "https://acme.xyz/audit.pdf"},
            ],
        ),
        scan_date=SCAN,
    )
    assert [(r.kind, r.url) for r in p.resources] == [
        ("website", "https://acme.xyz"),
        ("repo", "https://github.com/acme/core"),
        ("audit", "https://acme.xyz/audit.pdf"),
    ]


def test_non_http_resource_links_are_skipped() -> None:
    p = build_profile(_program(websiteUrl="acme.xyz", githubUrl=None), scan_date=SCAN)
    assert [r for r in p.resources if r.kind in ("website", "repo")] == []


def test_empty_text_sentinels_are_not_treated_as_published_sections() -> None:
    """Immunefi writes `_blank_` (118×), `.` (35×) and "To be determined" (34×).

    Quoting those back would report a scope limit the program never wrote.
    """
    for sentinel in ("_blank_", ".", "To be determined.", "tbd", "  ", "N/A"):
        p = build_profile(
            _program(prioritizedVulnerabilities=sentinel, defaultOutOfScopeGeneral=sentinel),
            scan_date=SCAN,
        )
        assert p.exclusions.prioritized_vulnerabilities is None, sentinel
        assert p.exclusions.published_sections() == [], sentinel
