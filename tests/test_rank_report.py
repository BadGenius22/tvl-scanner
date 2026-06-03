"""Tests for the Stage 4 report writer (summary + per-candidate YAML records)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml

from tvl_scanner.models import (
    AuditSource,
    AuditSourceKind,
    CandidateRecord,
    Chain,
    DiscoverySource,
    Language,
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
