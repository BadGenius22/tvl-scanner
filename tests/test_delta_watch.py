"""Tests for the delta-watch orchestrator."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from tvl_scanner.config import settings
from tvl_scanner.delta_watch import (
    WatchTarget,
    _fund_path_changes,
    check_target,
    classify_fund_path,
    load_state,
    load_watchlist,
    run_delta_watch,
    save_state,
    score_delta,
    write_delta_report,
)
from tvl_scanner.enrich.github_delta import ChangedFile, CommitInfo, RepoComparison
from tvl_scanner.models import Chain, DeltaWatchResult, Language

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_classify_fund_path_matches_real_delta_files() -> None:
    kw = settings().FUND_PATH_KEYWORDS
    assert classify_fund_path("src/instructions/liquidity/remove_liquidity.rs", kw) == "liquidity"
    assert classify_fund_path("src/instructions/lending/remove_collateral.rs", kw) == "collateral"
    assert classify_fund_path("src/instructions/lending/borrow.rs", kw) == "borrow"
    assert classify_fund_path("src/utils/liquidity_delta_circuit_breaker.rs", kw) == "liquidity"


def test_classify_fund_path_excludes_tests_mocks_docs() -> None:
    kw = settings().FUND_PATH_KEYWORDS
    assert classify_fund_path("tests/test_withdraw.rs", kw) is None
    assert classify_fund_path("src/mocks/withdraw_mock.rs", kw) is None
    assert classify_fund_path("src/lending/borrow_test.rs", kw) is None
    assert classify_fund_path("docs/withdraw.md", kw) is None
    assert classify_fund_path("src/lib.rs", kw) is None


def test_classify_fund_path_does_not_false_exclude_latest() -> None:
    """Regression: 'latest_' contains the substring 'test_' — must NOT be dropped."""
    kw = settings().FUND_PATH_KEYWORDS
    assert classify_fund_path("src/latest_price.rs", kw) == "price"


def test_classify_fund_path_with_extra_keywords() -> None:
    """Per-target extra keywords catch domain-named fund logic the global list misses
    (tranche/yield protocols name core files Accounting/Strategy/CDO, not withdraw/borrow)."""
    kw = settings().FUND_PATH_KEYWORDS
    # Global list misses Strata's core files (no generic fund keyword in the path)
    assert classify_fund_path("contracts/tranches/DYSAccounting.sol", kw) is None
    assert classify_fund_path("contracts/tranches/strategies/figure/FigureStrategy.sol", kw) is None
    assert classify_fund_path("contracts/tranches/StrataCDO.sol", kw) is None
    # Merged list (global + target extras) catches them
    merged = kw + ["cdo", "accounting", "strateg", "cooldown", "redemption"]
    assert classify_fund_path("contracts/tranches/DYSAccounting.sol", merged) == "accounting"
    assert classify_fund_path("contracts/tranches/strategies/figure/FigureStrategy.sol", merged) == "strateg"
    assert classify_fund_path("contracts/tranches/StrataCDO.sol", merged) == "cdo"
    # extras still respect the test/mock exclusion
    assert classify_fund_path("test/figure/MockStrategy.sol", merged) is None


def test_classify_fund_path_excludes_nonproduction_artifacts() -> None:
    """Certora specs, deploy-address JSONs, and audit PDFs match fund keywords by
    FILENAME but are not exploitable code — they must be dropped so they don't
    inflate the delta. Regression from the 2026-06-29 Veda run, where all 41
    'fund-path' files were specs/JSONs/PDFs."""
    kw = settings().FUND_PATH_KEYWORDS + ["teller", "accountant", "manager", "boring"]
    # Formal-verification specs / harnesses / confs (the `certora/` dir)
    assert classify_fund_path("certora/specs/teller_basic.spec", kw) is None
    assert classify_fund_path("certora/harness/TellerWithMultiAssetSupportHarness.sol", kw) is None
    assert classify_fund_path("certora/confs/accountantWithYieldStreaming.conf", kw) is None
    # Deployment address records (deploy dir and/or .json extension)
    assert classify_fund_path("deployments/addresses/Mainnet/Tellers.json", kw) is None
    assert classify_fund_path("WormholeBridgeWETHToMonad.json", kw) is None  # top-level .json
    # Audit reports and build config
    assert classify_fund_path("audit/certora-boring-vault-2.pdf", kw) is None
    assert classify_fund_path("foundry.toml", kw) is None
    # ...but real production source is still caught (no over-exclusion)
    assert classify_fund_path("src/base/Roles/TellerWithMultiAssetSupport.sol", kw) == "teller"
    assert classify_fund_path("src/base/Roles/AccountantWithRateProviders.sol", kw) == "accountant"


def test_fund_path_changes_drops_comment_only_files() -> None:
    """A fund-path file whose entire diff is comments (e.g. the Veda NatSpec /
    `// Last audited:` sweep) must not count — only real code changes do."""
    kw = settings().FUND_PATH_KEYWORDS
    files = [
        # real code change on a fund-path file → kept, additions = CODE lines
        ChangedFile("src/BoringVault.sol", "modified", 30, 0, code_additions=12, code_deletions=0),
        # comment-only change on a fund-path file (NatSpec/header) → dropped
        ChangedFile("src/WithdrawQueue.sol", "modified", 26, 0, code_additions=0, code_deletions=0),
        # unknown code count (patch unavailable) → kept (never drop a real change)
        ChangedFile("src/MintHelper.sol", "modified", 5, 0),
    ]
    changes = _fund_path_changes(files, kw)
    paths = {c.path for c in changes}
    assert "src/BoringVault.sol" in paths  # real code kept
    assert "src/WithdrawQueue.sol" not in paths  # comment-only dropped
    assert "src/MintHelper.sol" in paths  # unknown kept
    # reported additions are CODE lines (12), not the raw 30
    assert next(c for c in changes if c.path == "src/BoringVault.sol").additions == 12


def test_score_delta_truncated_uses_commit_signal() -> None:
    """When the file list is truncated, the commit-log signal (flagged commits +
    volume) ranks the delta — otherwise a clearly-active large delta scores ~0."""
    quiet = score_delta(0, 0, "immunefi")  # bounty bonus only
    trunc = score_delta(0, 0, "immunefi", truncated=True, notable_commits=6, total_commits=200)
    assert quiet == 2.0
    assert trunc > quiet
    # Bonus is bounded: notable capped at 5 (×2 = +10), volume capped at +5.
    assert trunc == round(2.0 + 10.0 + 5.0, 2)


@pytest.mark.asyncio
async def test_check_target_truncated_delta_flags_commit_log() -> None:
    """Truncated file list + 0 matched fund files must NOT read as a clean
    'none on fund-exit paths' — the commit-log signal keeps it a real delta."""
    comparison = RepoComparison(
        base="b",
        head="h",
        total_commits=120,
        commits=[CommitInfo(sha="c1", message="add ability to cancel a withdrawal")],
        # only artifact file matched → excluded by the sharpened classifier
        files=[ChangedFile(filename="certora/specs/teller.spec", status="added", additions=5)],
        truncated=True,
    )
    target = WatchTarget(
        slug="veda",
        display_name="Veda",
        github="https://github.com/Veda-Labs/boring-vault",
        bounty_program="immunefi",
        bounty_max_payout_usd=1_000_000,
        extra_keywords=["teller", "withdraw"],
    )
    state: dict = {}
    with patch("tvl_scanner.delta_watch.fetch_delta", return_value=("main", "h", comparison)):
        result = await check_target(target, state)
    assert result is not None
    assert result.fund_path_files_changed == 0  # certora spec excluded
    assert result.files_truncated is True
    assert result.notable_commits  # "cancel a withdrawal" flagged
    assert result.has_delta is True  # commit-log fallback, not a false negative
    assert "TRUNCATED" in result.why_interesting
    assert result.delta_score > 2.0  # truncation bonus applied


def test_score_delta_monotonic_in_file_count() -> None:
    assert score_delta(0, 0, "none") == 0.0
    assert score_delta(3, 0, "none") < score_delta(5, 0, "none")
    # bounty adds a flat bonus
    assert score_delta(3, 0, "immunefi") == pytest.approx(score_delta(3, 0, "none") + 2.0)
    # code additions DOMINATE (file count is only a 0.5 breadth weight) and are
    # bounded (capped at 30): one file with huge additions outscores file count.
    assert score_delta(1, 100_000, "none") == pytest.approx(0.5 + 30.0)
    # additions outweigh breadth: 1 big-change file > 5 trivial files
    assert score_delta(1, 300, "none") > score_delta(5, 0, "none")


# ---------------------------------------------------------------------------
# Watchlist + state
# ---------------------------------------------------------------------------


def test_load_watchlist_parses_seed() -> None:
    wl = load_watchlist()
    slugs = {t.slug for t in wl}
    assert "omnipair" in slugs
    omni = next(t for t in wl if t.slug == "omnipair")
    assert omni.audited_at_commit == "a927600"
    assert Chain.SOLANA in omni.chains
    assert Language.RUST in omni.languages


def test_load_watchlist_parses_extra_keywords() -> None:
    wl = load_watchlist()
    strata = next((t for t in wl if t.slug == "strata-markets"), None)
    assert strata is not None
    assert "accounting" in strata.extra_keywords
    assert "strateg" in strata.extra_keywords
    # targets without the field default to empty — no global keyword pollution
    omni = next(t for t in wl if t.slug == "omnipair")
    assert omni.extra_keywords == []


def test_state_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    assert load_state(p) == {}
    state = {"omnipair": {"last_checked_commit": "abc", "last_checked_date": "2026-06-01"}}
    save_state(state, p)
    assert load_state(p) == state


def test_load_state_tolerates_garbage(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    assert load_state(p) == {}


# ---------------------------------------------------------------------------
# check_target (mock the GitHub layer)
# ---------------------------------------------------------------------------


def _target() -> WatchTarget:
    return WatchTarget(
        slug="omnipair",
        display_name="Omnipair",
        github="https://github.com/omnipair/omnipair-rs",
        chains=[Chain.SOLANA],
        languages=[Language.RUST],
        audited_at_commit="a927600",
        audited_at_date=date(2026, 4, 7),
        bounty_program="none",
    )


async def test_check_target_flags_fund_path_changes() -> None:
    comparison = RepoComparison(
        base="a927600",
        head="head1",
        total_commits=3,
        commits=[
            CommitInfo("s1", "fix(omnipair): validate borrow token identity", "2026-05-26"),
            CommitInfo("s2", "feat: liquidity-delta-circuit-breaker", "2026-05-28"),
            CommitInfo("s3", "docs: readme", "2026-05-31"),
        ],
        files=[
            ChangedFile("src/instructions/lending/borrow.rs", "modified", 219, 12),
            ChangedFile("src/utils/liquidity_delta_circuit_breaker.rs", "added", 405, 0),
            ChangedFile("README.md", "modified", 5, 2),
            ChangedFile("tests/test_borrow.rs", "modified", 60, 0),
        ],
    )
    state: dict[str, dict[str, str]] = {}
    with patch(
        "tvl_scanner.delta_watch.fetch_delta",
        return_value=("main", "head1", comparison),
    ):
        result = await check_target(_target(), state)

    assert result is not None
    assert result.baseline_source == "audited_commit"
    assert result.baseline_commit == "a927600"
    assert result.head_commit == "head1"
    assert result.total_commits == 3
    # borrow.rs + circuit_breaker matched; README + test excluded
    assert result.fund_path_files_changed == 2
    assert result.fund_path_additions == 219 + 405
    assert result.has_delta is True
    # notable commits: 2 mention fund-path keywords (borrow, liquidity), not docs
    assert len(result.notable_commits) == 2
    # state recorded the new HEAD for next run
    assert state["omnipair"]["last_checked_commit"] == "head1"


async def test_check_target_first_run_records_baseline() -> None:
    """No audited_at_commit + no prior state → first run, no delta, base recorded."""
    t = WatchTarget(
        slug="newproto",
        display_name="New Proto",
        github="https://github.com/x/y",
    )
    state: dict[str, dict[str, str]] = {}
    with patch(
        "tvl_scanner.delta_watch.fetch_delta",
        return_value=("main", "firsthead", None),
    ):
        result = await check_target(t, state)
    assert result is not None
    assert result.baseline_source == "first_run"
    assert result.total_commits == 0
    assert result.has_delta is False
    assert state["newproto"]["last_checked_commit"] == "firsthead"


async def test_check_target_uses_last_checked_when_no_audit_commit() -> None:
    t = WatchTarget(slug="p", display_name="P", github="https://github.com/x/y")
    state = {"p": {"last_checked_commit": "prevhead", "last_checked_date": "2026-05-01"}}
    captured: dict[str, str | None] = {}

    async def fake_fetch(repo_url: str, base: str | None, *, branch=None, client=None):  # type: ignore[no-untyped-def]
        captured["base"] = base
        return ("main", "newhead", None)

    with patch("tvl_scanner.delta_watch.fetch_delta", side_effect=fake_fetch):
        result = await check_target(t, state)
    assert captured["base"] == "prevhead"  # diffed from last-checked
    assert result is not None
    assert result.baseline_source == "last_checked"


async def test_check_target_passes_branch_override() -> None:
    """A target with a `branch` override watches that ref, not the default branch."""
    t = WatchTarget(
        slug="marginfi",
        display_name="marginfi",
        github="https://github.com/0dotxyz/marginfi-v2",
        branch="0.1.9-main",
        audited_at_commit="843aa82d",
    )
    captured: dict[str, str | None] = {}

    async def fake_fetch(repo_url: str, base: str | None, *, branch=None, client=None):  # type: ignore[no-untyped-def]
        captured["branch"] = branch
        captured["base"] = base
        return ("0.1.9-main", "newhead", None)

    state: dict[str, dict[str, str]] = {}
    with patch("tvl_scanner.delta_watch.fetch_delta", side_effect=fake_fetch):
        result = await check_target(t, state)
    assert captured["branch"] == "0.1.9-main"
    assert captured["base"] == "843aa82d"
    assert result is not None
    assert result.default_branch == "0.1.9-main"


async def test_check_target_extra_keywords_are_per_target() -> None:
    """extra_keywords flag a target's domain files; a target WITHOUT them does not
    (proves per-target isolation — no global pollution)."""
    files = [
        ChangedFile("contracts/tranches/DYSAccounting.sol", "modified", 80, 5),  # extra 'accounting'
        ChangedFile("contracts/tranches/oracles/AprProvider.sol", "added", 30, 0),  # global 'oracle'
        ChangedFile("contracts/tranches/Errors.sol", "modified", 4, 1),  # no keyword at all
    ]
    comparison = RepoComparison(
        base="b0", head="h1", total_commits=1,
        commits=[CommitInfo("s1", "feat(accounting): true-up", "2026-05-01")],
        files=files,
    )

    async def run(extra: list[str]) -> set[str]:
        t = WatchTarget(
            slug="strata-markets", display_name="Strata", github="https://github.com/x/y",
            audited_at_commit="b0", extra_keywords=extra,
        )
        state: dict[str, dict[str, str]] = {}
        with patch("tvl_scanner.delta_watch.fetch_delta", return_value=("tranches", "h1", comparison)):
            res = await check_target(t, state)
        assert res is not None
        return {c.path for c in res.fund_path_changes}

    with_extra = await run(["accounting", "strateg"])
    assert "contracts/tranches/DYSAccounting.sol" in with_extra      # caught by extra
    assert "contracts/tranches/oracles/AprProvider.sol" in with_extra  # caught by global 'oracle'
    assert "contracts/tranches/Errors.sol" not in with_extra          # no keyword

    without_extra = await run([])
    assert "contracts/tranches/DYSAccounting.sol" not in without_extra  # global list alone misses it
    assert "contracts/tranches/oracles/AprProvider.sol" in without_extra  # global still works


async def test_check_target_inaccessible_repo_returns_none() -> None:
    state: dict[str, dict[str, str]] = {}
    with patch("tvl_scanner.delta_watch.fetch_delta", return_value=None):
        result = await check_target(_target(), state)
    assert result is None


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------


def _result(slug: str, fund_files: int, score: float) -> DeltaWatchResult:
    return DeltaWatchResult(
        target_name=slug,
        display_name=slug.title(),
        chains=[Chain.SOLANA],
        github_repo=f"https://github.com/x/{slug}",
        default_branch="main",
        baseline_commit="base1",
        baseline_source="audited_commit",
        head_commit="head1",
        total_commits=5,
        fund_path_files_changed=fund_files,
        fund_path_additions=fund_files * 100,
        delta_score=score,
        why_interesting="test",
        checked_date=date(2026, 6, 1),
    )


def test_write_delta_report_creates_summary_and_records(tmp_path: Path) -> None:
    results = [_result("alpha", 3, 11.0), _result("beta", 0, 0.0)]
    summary, records = write_delta_report(results, date(2026, 6, 1), reports_dir=tmp_path)
    assert summary.exists()
    assert summary.name == "2026-06-01-delta-watch.md"
    assert len(records) == 2
    text = summary.read_text()
    assert "Delta-Watch Report" in text
    assert "alpha" in text and "beta" in text
    # per-target records carry vault-liftable YAML frontmatter
    alpha_rec = next(r for r in records if "alpha" in r.name)
    body = alpha_rec.read_text()
    assert body.startswith("---")
    assert "target_name: alpha" in body
    assert "baseline_commit: base1" in body
    assert "git diff base1..head1" in body


async def test_run_delta_watch_end_to_end(tmp_path: Path) -> None:
    """Full orchestration with a stubbed GitHub layer + isolated state/reports."""
    comparison = RepoComparison(
        base="a927600",
        head="head1",
        total_commits=2,
        commits=[CommitInfo("s1", "fix: borrow guard", "2026-05-26")],
        files=[ChangedFile("src/lending/borrow.rs", "modified", 219, 12)],
    )
    state_path = tmp_path / "state.json"
    with (
        patch(
            "tvl_scanner.delta_watch.load_watchlist",
            return_value=[_target()],
        ),
        patch(
            "tvl_scanner.delta_watch.fetch_delta",
            return_value=("main", "head1", comparison),
        ),
        patch("tvl_scanner.delta_watch._github_headers", return_value={}),
    ):
        summary = await run_delta_watch(
            scan_date=date(2026, 6, 1),
            reports_dir=tmp_path / "reports",
            state_path=state_path,
        )
    assert summary.exists()
    assert "Delta-Watch Report" in summary.read_text()
    # state persisted
    assert load_state(state_path)["omnipair"]["last_checked_commit"] == "head1"
