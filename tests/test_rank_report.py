"""Tests for the Stage 4 report writer (summary + per-candidate YAML records)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from tvl_scanner.models import (
    AuditRecord,
    AuditSource,
    AuditSourceKind,
    BountyProfile,
    CandidateRecord,
    Chain,
    DiscoverySource,
    KnownIssue,
    Language,
    ProgramExclusions,
    ProgramImpact,
    ProgramResource,
    RewardTier,
    ScopeAsset,
)
from tvl_scanner.rank.report import (
    _fmt_age,
    _fmt_loc,
    _fmt_tvl,
    _frontmatter_dict,
    write_candidate_file,
    write_report,
)


def _record(
    *,
    target_name: str = "leverage-vault",
    display_name: str = "Leverage Vault",
    tvl_usd: float = 5_000_000,
    priority: float = 8.2,
    audit_density: int = 0,
    under_audited: bool = True,
    edge_keywords: list[str] | None = None,
    onchain_address: str | None = None,
) -> CandidateRecord:
    return CandidateRecord(
        chain=Chain.ARBITRUM,
        address="0xABCdef1234567890abcdef1234567890abcdef12",
        onchain_address=onchain_address,
        tvl_usd=tvl_usd,
        first_seen=date(2026, 3, 15),
        unique_users_30d=1200,
        source=DiscoverySource.GECKOTERMINAL,
        target_name=target_name,
        display_name=display_name,
        protocol_type="Yield on arbitrum",
        languages=[Language.SOLIDITY],
        github_repo="https://github.com/foo/bar",  # type: ignore[arg-type]
        loc_estimate=3500,
        audit_density_score=audit_density,
        audit_sources_found=[
            AuditSource(
                source=AuditSourceKind.CODE4RENA,
                url="https://github.com/code-423n4/2024-01-foo",  # type: ignore[arg-type]
                title="code-423n4/2024-01-foo",
                weight=3,
            )
        ] if audit_density > 0 else [],
        under_audited=under_audited,
        priority_score=priority,
        tvl_score=7.0,
        freshness_score=9.2,
        audit_gap_score=10.0 if audit_density == 0 else 4.0,
        activity_score=7.8,
        edge_match_score=10.0 if edge_keywords else 0.0,
        bounty_score=0.0,
        edge_match_keywords=edge_keywords or [],
        focus_areas_suggested=["prioritize leverage-loop entry points", "check aave integration seams"],
        inferred_platform="private",
        inferred_mode="private",
        why_interesting=f"Yield on arbitrum • {int(tvl_usd):,} TVL • 29d old • ~3500 LOC • no prior audits found",
        scan_date=date(2026, 4, 13),
        age_days=29,
    )


# ---- Formatter tests ----


def test_fmt_tvl_scales() -> None:
    assert _fmt_tvl(500) == "$500"
    assert _fmt_tvl(50_000) == "$50K"
    assert _fmt_tvl(5_000_000) == "$5.0M"
    assert _fmt_tvl(1_500_000) == "$1.5M"


def test_fmt_age_units() -> None:
    assert _fmt_age(10) == "10d"
    assert _fmt_age(45) == "1mo"
    assert _fmt_age(365) == "1y0mo"
    assert _fmt_age(500) == "1y4mo"


def test_fmt_loc_units() -> None:
    assert _fmt_loc(None) == "?"
    assert _fmt_loc(500) == "500"
    assert _fmt_loc(3500) == "3k"


# ---- Frontmatter schema tests (the vault handoff contract) ----


def test_frontmatter_has_all_phase2a_sections() -> None:
    record = _record()
    fm = _frontmatter_dict(record)

    # Section 1: Target Identification
    assert "target_name" in fm
    assert "display_name" in fm
    assert "protocol_type" in fm
    assert "languages" in fm
    assert "chains" in fm
    assert "inferred_platform" in fm
    assert "inferred_mode" in fm

    # Section 2: Prior Audits
    assert "audit_density_score" in fm
    assert "audit_sources_found" in fm
    assert "under_audited" in fm

    # Section 6: Suggested Focus Areas
    assert "edge_match_keywords" in fm
    assert "focus_areas_suggested" in fm

    # Section 7: Submission Platform Context
    assert "bounty_program" in fm
    assert "bounty_url" in fm
    assert "bounty_max_payout_usd" in fm


def test_frontmatter_primary_contract_prefers_onchain_address() -> None:
    """Catalog candidates carry a synthetic `address`; the resolved on-chain
    contract must win for primary_contract and be surfaced in the frontmatter,
    so the vault handoff gets the real address."""
    real = "ethereum:0xe76c6c83af64e4c60245d8c7de953df673a7a33d"
    record = _record(onchain_address=real)
    assert record.primary_contract == real
    fm = _frontmatter_dict(record)
    assert fm["onchain_address"] == real
    assert fm["primary_contract"] == real


def test_frontmatter_primary_contract_falls_back_without_onchain() -> None:
    """With no resolved on-chain address, primary_contract uses chain:address."""
    record = _record()  # onchain_address defaults to None
    assert record.primary_contract == "arbitrum:0xABCdef1234567890abcdef1234567890abcdef12"
    assert _frontmatter_dict(record)["onchain_address"] is None


def test_frontmatter_languages_serialized_as_strings() -> None:
    """Stage A needs to parse this as YAML — enum values must be primitive strings."""
    record = _record()
    fm = _frontmatter_dict(record)
    assert fm["languages"] == ["solidity"]
    assert all(isinstance(v, str) for v in fm["languages"])


def test_frontmatter_yaml_round_trip() -> None:
    """The frontmatter dict must serialize to valid YAML and re-parse cleanly."""
    record = _record()
    fm = _frontmatter_dict(record)
    yaml_str = yaml.safe_dump(fm, sort_keys=False)
    parsed = yaml.safe_load(yaml_str)
    assert parsed["target_name"] == "leverage-vault"
    assert parsed["tvl_usd"] == 5_000_000
    assert parsed["under_audited"] is True


def test_write_candidate_file_creates_frontmatter_and_body(tmp_path: Path) -> None:
    record = _record(edge_keywords=["leverage", "vault"])
    path = write_candidate_file(record, rank=3, out_dir=tmp_path)
    content = path.read_text()

    assert path.name == "03-leverage-vault.md"
    assert content.startswith("---\n")
    assert "\n---\n" in content  # closing frontmatter delimiter
    assert "target_name: leverage-vault" in content
    assert "# Leverage Vault" in content  # body heading
    assert "## Summary" in content
    assert "## Audit history" in content
    assert "## Priority breakdown" in content
    assert "## Suggested focus areas" in content
    assert "## Vault handoff (Phase 2a)" in content


def test_write_report_produces_summary_and_candidates(tmp_path: Path) -> None:
    r1 = _record(target_name="leverage-vault", display_name="Leverage Vault", priority=8.5)
    r2 = _record(target_name="yield-opt", display_name="Yield Optimizer", priority=6.1)

    summary, candidate_paths = write_report(
        [r1, r2], scan_date=date(2026, 4, 13), reports_dir=tmp_path
    )

    assert summary.exists()
    assert summary.name == "2026-04-13-scan.md"
    summary_text = summary.read_text()
    assert "# TVL Scanner Report" in summary_text
    assert "Leverage Vault" in summary_text
    assert "Yield Optimizer" in summary_text
    assert "2026-04-13-scan" in summary_text  # link substitution worked

    assert len(candidate_paths) == 2
    assert candidate_paths[0].name == "01-leverage-vault.md"
    assert candidate_paths[1].name == "02-yield-opt.md"
    assert (tmp_path / "2026-04-13-scan" / "candidates").is_dir()


# ---- immunefi-scan layout (12-criteria bounty records) ----


def _bounty_record(
    *,
    target_name: str = "acme",
    display_name: str = "Acme Protocol",
    priority: float = 7.4,
    invite_only: bool = False,
    known_issue_count: int = 0,
    tvl_resolved: bool = True,
) -> CandidateRecord:
    """A record as produced by `rank/bounty_priority.rank_candidate_bounty`."""
    profile = BountyProfile(
        max_bounty_usd=250_000,
        min_bounty_usd=2_000,
        critical_min_usd=50_000,
        critical_max_usd=250_000,
        reward_tiers=[
            RewardTier(
                severity="critical",
                asset_type="smart_contract",
                reward_model="range",
                min_usd=50_000,
                max_usd=250_000,
                calculation_percentage=10,
            )
        ],
        reward_model="range",
        reward_calculation_percentage=10,
        ten_percent_economic_rule=True,
        poc_required_for_critical=True,
        payout_basis="10% of funds at risk, capped at $250,000; Immunefi 10% economic rule applies",
        max_payout_vs_tvl_pct=5.0 if tvl_resolved else None,
        program_updated_at=date(2026, 4, 1),
        days_since_program_update=12,
        program_launched_at=date(2025, 10, 13),
        program_age_days=182,
        known_issue_count=known_issue_count,
        known_issues=[
            KnownIssue(description="Governor quorum drift.", link="https://example.test/1")
        ]
        * known_issue_count,
        audit_count=1,
        latest_audit_at=date(2024, 1, 1),
        days_since_latest_audit=833,
        auditors=["Zenith"],
        smart_contract_assets=8,
        web_app_assets=1,
        ecosystems=["ETH"],
        project_types=["Defi"],
        critical_impacts=["Direct theft of any user funds"],
        newest_asset_added_at=date(2026, 3, 20),
        days_since_newest_asset=24,
        assets_added_90d=3,
        assets_revised=2,
        kyc_required=True,
        invite_only=invite_only,
        immunefi_standard=True,
        vault_escrow=True,
        responsible_publication_category="category_2",
    )
    base = _record(target_name=target_name, display_name=display_name, priority=priority)
    return base.model_copy(
        update={
            "bounty_program": "immunefi",
            "bounty_url": "https://immunefi.com/bug-bounty/acme",
            "bounty_max_payout_usd": 250_000,
            "bounty_profile": profile,
            "tvl_resolved": tvl_resolved,
            "priority_formula": "bounty",
            "bounty_size_score": 8.4,
            "bounty_calc_score": 9.1,
            "program_update_score": 10.0,
            "program_age_score": 8.7,
            "known_issues_score": 10.0 - 1.5 * known_issue_count,
            "architecture_score": 9.5,
            "upgrade_activity_score": 9.0,
            "competition_score": 6.0,
            "resolution_quality_score": 7.5,
        }
    )


def test_bounty_summary_uses_the_target_selection_columns(tmp_path: Path) -> None:
    summary, _ = write_report(
        [_bounty_record()], scan_date=date(2026, 4, 13), reports_dir=tmp_path, label="immunefi-scan"
    )
    text = summary.read_text()

    assert summary.name == "2026-04-13-immunefi-scan.md"
    assert "# Immunefi Bounty Scan" in text
    # Columns the discovery table has no place for.
    for header in ("Crit floor", "%TVL", "Prog age", "New 90d", "Known", "Comp"):
        assert header in text
    assert "$250K" in text  # max payout
    assert "$50K" in text  # critical floor
    assert "5%" in text  # payout vs funds at risk
    # The 12-criteria legend replaces the 6-factor one.
    assert "Recent upgrades / features" in text
    assert "not comparable" in text


def test_bounty_summary_flags_invite_only_programs(tmp_path: Path) -> None:
    summary, _ = write_report(
        [_bounty_record(invite_only=True)],
        scan_date=date(2026, 4, 13),
        reports_dir=tmp_path,
        label="immunefi-scan",
    )
    text = summary.read_text()
    assert "⚠IOP" in text
    assert "Invite-only (cannot submit without an invitation)**: 1" in text


def test_tvl_records_keep_the_discovery_layout(tmp_path: Path) -> None:
    """A `run` report must not gain bounty columns just because the code exists."""
    summary, _ = write_report([_record()], scan_date=date(2026, 4, 13), reports_dir=tmp_path)
    text = summary.read_text()
    assert "# TVL Scanner Report" in text
    assert "Crit floor" not in text
    assert "Under-audited |" in text  # the discovery table's own column


def test_bounty_candidate_record_covers_all_twelve_criteria(tmp_path: Path) -> None:
    path = write_candidate_file(_bounty_record(known_issue_count=2), 1, tmp_path)
    content = path.read_text()

    assert "## Bounty program profile (12-criteria rubric)" in content
    for heading in (
        "### 1. Funds at risk",
        "### 2. Maximum + minimum bounty",
        "### 3. Bounty calculation",
        "### 4-5. Program update & age",
        "### 6. Known issues",
        "### 7. Audit history (per Immunefi)",
        "### 8. Protocol architecture",
        "### 9. Recent upgrades / scope changes",
        "### 11. Likely researcher competition",
        "### 12. Payout & resolution quality",
    ):
        assert heading in content, heading

    # The 12-term breakdown replaces the 6-factor one.
    assert "## Priority breakdown (12-criteria bounty formula)" in content
    assert "9. recent upgrades / scope churn: 9.0 × 0.10" in content
    assert "7. audit history (gap + staleness)" in content

    # Decision-critical prose, not just numbers.
    assert "10% of funds at risk" in content
    assert "entered scope in the last 90 days" in content
    assert "published known issue(s)" in content
    assert "Over 18 months old" in content  # stale-audit warning
    assert "PoC is REQUIRED" in content or "PoC required for critical" in content


def test_bounty_record_warns_when_the_cap_binds(tmp_path: Path) -> None:
    record = _bounty_record()
    assert record.bounty_profile is not None
    record.bounty_profile.max_payout_vs_tvl_pct = 0.0025
    content = write_candidate_file(record, 1, tmp_path).read_text()
    assert "The cap binds hard" in content


def test_bounty_frontmatter_extends_without_breaking_the_vault_contract() -> None:
    fm = _frontmatter_dict(_bounty_record())

    # Stage 3.5 fields the vault template reads are untouched.
    for key in ("target_name", "bounty_program", "bounty_url", "bounty_max_payout_usd"):
        assert key in fm

    # Additive bounty keys.
    assert fm["bounty_critical_min_usd"] == 50_000
    assert fm["bounty_payout_basis"].startswith("10% of funds at risk")
    assert fm["bounty_assets_added_90d"] == 3
    assert fm["priority_formula"] == "bounty"
    assert fm["priority_subscores"]["upgrade_activity"] == 9.0
    assert fm["bounty_program_profile"]["smart_contract_assets"] == 8

    # Serializable as YAML (dates rendered as strings by model_dump(mode="json")).
    assert yaml.safe_load(yaml.safe_dump(fm))["bounty_invite_only"] is False


def test_run_records_carry_no_bounty_frontmatter_keys() -> None:
    fm = _frontmatter_dict(_record())
    assert "bounty_program_profile" not in fm
    assert "priority_subscores" not in fm


def test_filter_funnel_lands_in_the_bounty_summary_header(tmp_path: Path) -> None:
    """A short candidate list must be attributable to the filters that made it."""
    summary, _ = write_report(
        [_bounty_record()],
        scan_date=date(2026, 4, 13),
        reports_dir=tmp_path,
        label="immunefi-scan",
        filter_summary="**Filter funnel** — 247 programs fetched:\n\n- −59 program closed",
    )
    text = summary.read_text()
    assert "**Filter funnel** — 247 programs fetched" in text
    assert "−59 program closed" in text
    # Placed above the table, so it is read before the shortlist is believed.
    assert text.index("Filter funnel") < text.index("| Rank |")


def test_empty_bounty_scan_still_shows_its_funnel(tmp_path: Path) -> None:
    """Filtering everything out must not silently fall back to the discovery layout."""
    summary, paths = write_report(
        [],
        scan_date=date(2026, 4, 13),
        reports_dir=tmp_path,
        label="immunefi-scan",
        filter_summary="**Filter funnel** — 247 programs fetched:\n\n- −247 everything",
    )
    text = summary.read_text()
    assert paths == []
    assert "# Immunefi Bounty Scan" in text
    assert "−247 everything" in text


def test_run_reports_never_carry_a_funnel(tmp_path: Path) -> None:
    summary, _ = write_report([_record()], scan_date=date(2026, 4, 13), reports_dir=tmp_path)
    assert "Filter funnel" not in summary.read_text()


# ---- Scope, exclusions and resources ----


def _documented_record() -> CandidateRecord:
    """A bounty record carrying the program-document fields, as a live scan does."""
    record = _bounty_record()
    assert record.bounty_profile is not None
    p = record.bounty_profile
    p.scope_assets = [
        ScopeAsset(
            asset_type="smart_contract",
            url="https://arbiscan.io/address/0x" + "ab" * 20,
            description="Vault Manager",
            address="0x" + "ab" * 20,
            explorer="arbiscan.io",
            added_at=date(2026, 3, 20),
        ),
        ScopeAsset(
            asset_type="smart_contract",
            url="https://github.com/acme/core/tree/main/src",
            description="Core contracts",
            repo="acme/core/tree/main/src",
        ),
        ScopeAsset(
            asset_type="smart_contract",
            url="https://immunefi.com/",
            description="Primacy of Impact",
            primacy_of_impact=True,
            is_placeholder=True,
        ),
    ]
    p.repo_scoped_assets = 1
    p.primacy_of_impact = True
    p.impacts = [
        ProgramImpact(severity="critical", asset_type="smart_contract", title="Direct theft of any user funds"),
        ProgramImpact(severity="high", asset_type="smart_contract", title="Temporary freezing of funds"),
        ProgramImpact(severity="medium", asset_type="smart_contract", title="Block stuffing"),
    ]
    p.poc_required_tiers = ["smart_contract - critical"]
    p.exclusions = ProgramExclusions(
        feasibility_limitations="Attacks requiring a compromised private key are out of scope.",
        custom_out_of_scope="The legacy v1 vaults are excluded.",
        prioritized_vulnerabilities="Accounting drift in the credit vaults.",
    )
    p.resources = [
        ProgramResource(kind="website", url="https://acme.xyz"),
        ProgramResource(kind="audit", url="https://acme.xyz/audit.pdf", label="Zenith"),
    ]
    return record


def test_scope_table_lists_every_asset_and_hides_the_placeholder(tmp_path: Path) -> None:
    content = write_candidate_file(_documented_record(), 1, tmp_path).read_text()

    assert "## Assets in scope" in content
    assert "2 listed asset(s)" in content
    assert "0x" + "ab" * 20 in content
    assert "acme/core/tree/main/src" in content
    # The sentinel row is disclosed as excluded rather than silently dropped.
    assert "Primacy-of-Impact placeholder row(s) are excluded" in content
    assert "point at a repo or a path inside one" in content


def test_impact_table_renders_every_severity(tmp_path: Path) -> None:
    content = write_candidate_file(_documented_record(), 1, tmp_path).read_text()
    assert "Pays for these impacts" in content
    for tier in ("**critical**", "**high**", "**medium**"):
        assert tier in content
    assert "Temporary freezing of funds" in content
    assert "Block stuffing" in content


def test_scope_limits_section_quotes_the_exclusions(tmp_path: Path) -> None:
    content = write_candidate_file(_documented_record(), 1, tmp_path).read_text()
    assert "## Scope limits and exclusions" in content
    assert "compromised private key" in content
    assert "legacy v1 vaults" in content
    assert "Prioritized vulnerabilities" in content


def test_program_resources_are_listed(tmp_path: Path) -> None:
    content = write_candidate_file(_documented_record(), 1, tmp_path).read_text()
    assert "## Program resources" in content
    assert "https://acme.xyz/audit.pdf" in content


def test_placeholder_audit_row_is_called_out(tmp_path: Path) -> None:
    record = _bounty_record()
    assert record.bounty_profile is not None
    record.bounty_profile.audit_count = 1
    record.bounty_profile.verified_audit_count = 0
    record.bounty_profile.latest_audit_at = None
    record.bounty_profile.days_since_latest_audit = None
    record.bounty_profile.auditors = []
    record.bounty_profile.audit_records = [
        AuditRecord(
            auditor="All Audits",
            url="https://acme.xyz/security",
            performed_at=date(2025, 10, 13),
            is_placeholder=True,
            placeholder_reason="auditor is 'All Audits', a category label rather than a firm",
        )
    ]
    content = write_candidate_file(record, 1, tmp_path).read_text()
    assert "row is a placeholder, not an audit" in content
    assert "**Most recent audit**: UNDATED" in content
    # The stale-audit warning must NOT fire off a date the program never gave.
    assert "Over 18 months old" not in content


def test_scope_assets_lift_into_the_frontmatter_without_the_prose(tmp_path: Path) -> None:
    fm = _frontmatter_dict(_documented_record())

    # The full in-scope list travels with the record, so Phase 2a does not have
    # to re-derive it from the program page by hand.
    assert [a["address"] for a in fm["bounty_scope_assets"]] == ["0x" + "ab" * 20, None]
    assert fm["bounty_repo_scoped_assets"] == 1
    assert fm["bounty_primacy_of_impact"] is True
    assert set(fm["bounty_exclusion_sections"]) == {
        "custom_out_of_scope",
        "feasibility_limitations",
        "prioritized_vulnerabilities",
    }
    # Exclusion prose is thousands of characters and belongs in the body.
    assert "exclusions" not in fm["bounty_program_profile"]
    assert "scope_assets" not in fm["bounty_program_profile"]
    assert yaml.safe_load(yaml.safe_dump(fm))["bounty_scope_assets"][0]["explorer"] == "arbiscan.io"
