"""End-to-end orchestrator tests with the GitHub layer patched at the boundary."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from tvl_scanner.enrich.github_delta import ChangedFile, RepoComparison
from tvl_scanner.models import BountyProfile, CandidateRecord, Chain, DiscoverySource
from tvl_scanner.recon.orchestrator import run_recon
from tvl_scanner.recon.shortlist import ShortlistSelection
from tvl_scanner.recon.sources import RepoSnapshot


def _candidate(
    name: str = "alpha",
    *,
    github: str | None = "https://github.com/org/alpha",
    bounty: str = "immunefi",
    latest_audit: date | None = date(2026, 5, 1),
) -> CandidateRecord:
    profile = None
    if latest_audit is not None:
        profile = BountyProfile(latest_audit_at=latest_audit)
    return CandidateRecord(
        chain=Chain.ARBITRUM,
        address=f"0x{name}",
        tvl_usd=8_000_000.0,
        tvl_resolved=True,
        first_seen=date(2026, 1, 1),
        source=DiscoverySource.IMMUNEFI_CATALOG,
        target_name=name,
        display_name=name.title(),
        protocol_type="Lending on arbitrum",
        languages=[],
        github_repo=github,
        audit_density_score=1,
        under_audited=True,
        priority_score=7.5,
        tvl_score=8.0,
        freshness_score=6.0,
        audit_gap_score=8.0,
        activity_score=5.0,
        edge_match_score=5.0,
        bounty_score=10.0,
        priority_formula="bounty",
        why_interesting="test",
        scan_date=date(2026, 8, 24),
        age_days=120,
        bounty_program=bounty,
        bounty_url="https://immunefi.com/bug-bounty/alpha",
        bounty_max_payout_usd=250_000,
        bounty_profile=profile,
    )


def _comparison() -> RepoComparison:
    return RepoComparison(
        base="sha_audit",
        head="head123",
        total_commits=12,
        files=[
            ChangedFile(
                filename="src/WithdrawVault.sol",
                status="modified",
                additions=120,
                deletions=10,
                code_additions=100,
                code_deletions=8,
            ),
            ChangedFile(filename="README.md", status="modified", additions=5),
        ],
    )


def _snapshot() -> RepoSnapshot:
    src = (
        "contract WithdrawVault {\n"
        "  function pull() external onlyOwner {}\n"
        "  uint256 p = feed.latestRoundData;\n"
        "}\n"
    )
    return RepoSnapshot(
        owner="org",
        repo="alpha",
        ref="head123",
        paths=["src/WithdrawVault.sol", "test/WithdrawVault.t.sol", "foundry.toml"],
        sizes={"src/WithdrawVault.sol": len(src), "test/WithdrawVault.t.sol": 10,
               "foundry.toml": 5},
        contents={"src/WithdrawVault.sol": src},
    )


def _selection(cands: list[CandidateRecord]) -> ShortlistSelection:
    from tvl_scanner.enrich.immunefi_filter import FilterFunnel

    return ShortlistSelection(
        candidates=cands,
        funnel=FilterFunnel(
            fetched=len(cands), subject="shortlist candidates", origin="from tests"
        ),
        notes=[],
        source_of={c.target_name.lower(): "immunefi" for c in cands},
    )


def _patches(**kw: Any) -> dict[str, Any]:
    return {
        "fetch_delta": AsyncMock(return_value=("main", "head123", _comparison())),
        "get_commit_before": AsyncMock(return_value="sha_audit"),
        "fetch_snapshot": AsyncMock(return_value=_snapshot()),
        "load_watchlist": lambda: [],
        "_github_headers": lambda: {},
        **kw,
    }


async def test_run_recon_happy_path(tmp_path: Path) -> None:
    cand = _candidate()
    p = _patches()
    with (
        patch("tvl_scanner.recon.orchestrator.fetch_delta", p["fetch_delta"]),
        patch("tvl_scanner.recon.orchestrator.get_commit_before", p["get_commit_before"]),
        patch("tvl_scanner.recon.orchestrator.fetch_snapshot", p["fetch_snapshot"]),
        patch("tvl_scanner.recon.orchestrator.load_watchlist", p["load_watchlist"]),
        patch("tvl_scanner.recon.orchestrator._github_headers", p["_github_headers"]),
    ):
        summary = await run_recon(
            selection=_selection([cand]),
            scan_date=date(2026, 8, 24),
            reports_dir=tmp_path / "reports",
            state_path=tmp_path / "state.json",
            cache_dir=str(tmp_path / "cache"),
        )

    assert summary.name == "2026-08-24-recon.md"
    assert summary.is_file()
    record = tmp_path / "reports" / "2026-08-24-recon" / "candidates" / "01-alpha.md"
    body = record.read_text()

    # baseline came from the audit date lookup (not the 90d window fallback)
    p["get_commit_before"].assert_awaited_once()
    args = p["get_commit_before"].call_args.args
    assert args[0] == "org" and args[1] == "alpha"
    assert args[2] == "2026-05-01T23:59:59Z"

    # frontmatter carries the additive recon keys + identity keys
    assert body.startswith("---\n")
    assert "attack_surface_score:" in body
    assert "recon_signals:" in body
    assert "payout_path: bounty" in body
    assert "baseline_source: audit_date" in body
    assert "fund_path_files_changed: 1" in body

    # bounty-backed → vault trigger phrase in the next-step block
    assert "new audit on alpha at" in body
    assert "delta_watch_targets.yaml" not in body

    # state pinned the observed HEAD
    import json

    state = json.loads((tmp_path / "state.json").read_text())
    assert state["alpha"]["last_checked_commit"] == "head123"

    # snapshot signals flowed through: 1 production source (test file excluded),
    # privileged + oracle markers counted
    assert "**Privileged markers**: 1" in body
    assert summary.read_text().count("|") > 10  # summary table rendered


async def test_run_recon_first_run_is_delta_neutral(tmp_path: Path) -> None:
    cand = _candidate(latest_audit=None)
    p = _patches(
        get_commit_before=AsyncMock(return_value=None),
        fetch_delta=AsyncMock(return_value=("main", "head123", None)),
    )
    with (
        patch("tvl_scanner.recon.orchestrator.fetch_delta", p["fetch_delta"]),
        patch("tvl_scanner.recon.orchestrator.get_commit_before", p["get_commit_before"]),
        patch("tvl_scanner.recon.orchestrator.fetch_snapshot", p["fetch_snapshot"]),
        patch("tvl_scanner.recon.orchestrator.load_watchlist", p["load_watchlist"]),
        patch("tvl_scanner.recon.orchestrator._github_headers", p["_github_headers"]),
    ):
        await run_recon(
            selection=_selection([cand]),
            scan_date=date(2026, 8, 24),
            reports_dir=tmp_path / "reports",
            state_path=tmp_path / "state.json",
            cache_dir=str(tmp_path / "cache"),
        )
    record = tmp_path / "reports" / "2026-08-24-recon" / "candidates" / "01-alpha.md"
    body = record.read_text()
    assert "baseline_source: first_run" in body
    assert "fund_delta: 5.0" in body  # unknown ≠ zero


async def test_no_repo_candidate_dropped_with_reason(tmp_path: Path) -> None:
    cand = _candidate(name="ghost", github=None)
    p = _patches()
    with (
        patch("tvl_scanner.recon.orchestrator.fetch_delta", p["fetch_delta"]),
        patch("tvl_scanner.recon.orchestrator.get_commit_before", p["get_commit_before"]),
        patch("tvl_scanner.recon.orchestrator.fetch_snapshot", p["fetch_snapshot"]),
        patch("tvl_scanner.recon.orchestrator.load_watchlist", p["load_watchlist"]),
        patch("tvl_scanner.recon.orchestrator._github_headers", p["_github_headers"]),
    ):
        await run_recon(
            selection=_selection([cand]),
            scan_date=date(2026, 8, 24),
            reports_dir=tmp_path / "reports",
            state_path=tmp_path / "state.json",
            cache_dir=str(tmp_path / "cache"),
        )
    summary = (tmp_path / "reports" / "2026-08-24-recon.md").read_text()
    assert "no github repo resolved" in summary
    cands_dir = tmp_path / "reports" / "2026-08-24-recon" / "candidates"
    assert not any(cands_dir.glob("*.md"))


async def test_no_bounty_candidate_gets_watchlist_entry(tmp_path: Path) -> None:
    cand = _candidate(name="prebounty", bounty="none", latest_audit=None)
    p = _patches()
    with (
        patch("tvl_scanner.recon.orchestrator.fetch_delta", p["fetch_delta"]),
        patch("tvl_scanner.recon.orchestrator.get_commit_before", p["get_commit_before"]),
        patch("tvl_scanner.recon.orchestrator.fetch_snapshot", p["fetch_snapshot"]),
        patch("tvl_scanner.recon.orchestrator.load_watchlist", p["load_watchlist"]),
        patch("tvl_scanner.recon.orchestrator._github_headers", p["_github_headers"]),
    ):
        await run_recon(
            selection=_selection([cand]),
            scan_date=date(2026, 8, 24),
            reports_dir=tmp_path / "reports",
            state_path=tmp_path / "state.json",
            cache_dir=str(tmp_path / "cache"),
        )
    record = tmp_path / "reports" / "2026-08-24-recon" / "candidates" / "01-prebounty.md"
    body = record.read_text()
    assert "payout_path: none" in body
    assert "delta_watch_targets.yaml" in body
    assert "- slug: prebounty" in body
    assert "new audit on" not in body


async def test_snapshot_failure_degrades_but_keeps_delta(tmp_path: Path) -> None:
    cand = _candidate()
    p = _patches(fetch_snapshot=AsyncMock(return_value=None))
    with (
        patch("tvl_scanner.recon.orchestrator.fetch_delta", p["fetch_delta"]),
        patch("tvl_scanner.recon.orchestrator.get_commit_before", p["get_commit_before"]),
        patch("tvl_scanner.recon.orchestrator.fetch_snapshot", p["fetch_snapshot"]),
        patch("tvl_scanner.recon.orchestrator.load_watchlist", p["load_watchlist"]),
        patch("tvl_scanner.recon.orchestrator._github_headers", p["_github_headers"]),
    ):
        await run_recon(
            selection=_selection([cand]),
            scan_date=date(2026, 8, 24),
            reports_dir=tmp_path / "reports",
            state_path=tmp_path / "state.json",
            cache_dir=str(tmp_path / "cache"),
        )
    record = tmp_path / "reports" / "2026-08-24-recon" / "candidates" / "01-alpha.md"
    body = record.read_text()
    assert "No repo snapshot" in body
    # delta subscore still real (not neutral) — comparison was valid
    assert "fund_path_files_changed: 1" in body
    summary = (tmp_path / "reports" / "2026-08-24-recon.md").read_text()
    assert "snapshot unavailable" in summary
