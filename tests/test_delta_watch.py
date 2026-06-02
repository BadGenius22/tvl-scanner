"""Tests for the delta-watch orchestrator."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from tvl_scanner.config import settings
from tvl_scanner.delta_watch import (
    WatchTarget,
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


def test_score_delta_monotonic_in_file_count() -> None:
    assert score_delta(0, 0, "none") == 0.0
    assert score_delta(3, 0, "none") < score_delta(5, 0, "none")
    # bounty adds a flat bonus
    assert score_delta(3, 0, "immunefi") == pytest.approx(score_delta(3, 0, "none") + 2.0)
    # additions add a bounded bonus (capped at 5)
    assert score_delta(1, 100_000, "none") == pytest.approx(3.0 + 5.0)


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

    async def fake_fetch(repo_url: str, base: str | None, *, client=None):  # type: ignore[no-untyped-def]
        captured["base"] = base
        return ("main", "newhead", None)

    with patch("tvl_scanner.delta_watch.fetch_delta", side_effect=fake_fetch):
        result = await check_target(t, state)
    assert captured["base"] == "prevhead"  # diffed from last-checked
    assert result is not None
    assert result.baseline_source == "last_checked"


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
