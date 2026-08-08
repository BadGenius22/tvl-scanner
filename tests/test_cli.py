"""Tests for CLI helpers and the immunefi-scan filter wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from tvl_scanner.cli import _describe_filters, _parse_exclude_slugs, app
from tvl_scanner.enrich.immunefi_filter import ProgramFilter
from tvl_scanner.models import Language

_CAPTURED: list[ProgramFilter] = []


def _captured_filters() -> ProgramFilter:
    """The ProgramFilter the CLI handed to run_immunefi_scan."""
    assert _CAPTURED, 'run_immunefi_scan was never called'
    return _CAPTURED[-1]


@pytest.fixture(autouse=True)
def _stub_immunefi_scan() -> Any:
    """Capture the filter instead of running a scan — this is a wiring test."""
    _CAPTURED.clear()

    async def _fake(chains: Any = None, **kwargs: Any) -> Path:
        _CAPTURED.append(kwargs['filters'])
        return Path('/dev/null')

    with patch('tvl_scanner.pipeline.run_immunefi_scan', new=AsyncMock(side_effect=_fake)):
        yield


def test_parse_exclude_slugs_plain_lines() -> None:
    text = "aave-v3\ncamelot-v3\n\n# comment line\n"
    assert _parse_exclude_slugs(text) == {"aave-v3", "camelot-v3"}


def test_parse_exclude_slugs_markdown_table_rows_skip_rank_column() -> None:
    """A ranked-report row's first cell is the rank number — the protocol name
    in the next cell must win, not the numeric rank (regression: the parser
    used to grab '1' and stop, so nothing was ever excluded)."""
    text = (
        "| Rank | Protocol | Chain |\n"
        "|------|----------|-------|\n"
        "| 1 | Aave V3 | arbitrum |\n"
        "| 12 | Camelot V3 | arbitrum |\n"
    )
    slugs = _parse_exclude_slugs(text)
    assert "aave-v3" in slugs
    assert "camelot-v3" in slugs
    assert "1" not in slugs
    assert "12" not in slugs


def test_parse_exclude_slugs_display_names_slugify_with_hyphens() -> None:
    assert _parse_exclude_slugs("Strata Markets\n") == {"strata-markets"}


def test_parse_exclude_slugs_empty_input() -> None:
    assert _parse_exclude_slugs("") == set()
    assert _parse_exclude_slugs("# only comments\n") == set()


# ---- immunefi-scan filter wiring ----


def test_immunefi_scan_flags_build_the_expected_filter() -> None:
    """Every flag must actually reach ProgramFilter — a dropped one silently
    widens the scan, which is the failure mode a filter exists to prevent."""
    result = CliRunner().invoke(
        app,
        [
            "immunefi-scan",
            "--min-tvl", "1000000",
            "--min-bounty", "100000",
            "--min-critical-floor", "25000",
            "--min-payout-ratio", "1.5",
            "--updated-within", "180",
            "--max-program-age", "365",
            "--max-known-issues", "3",
            "--audit-older-than", "540",
            "--under-audited-only",
            "--min-scope", "3",
            "--max-scope", "60",
            "--fresh-scope", "90",
            "--languages", "solidity,rust",
            "--no-kyc",
            "--exclude-boosted",
            "--require-vault",
            "--exclude-invite-only",
            "--exclude", "twyne,onre",
        ],
    )
    assert result.exit_code == 0, result.output

    captured = _captured_filters()
    assert captured.min_tvl_usd == 1_000_000
    assert captured.min_max_bounty_usd == 100_000
    assert captured.min_critical_floor_usd == 25_000
    assert captured.min_payout_ratio_pct == 1.5
    assert captured.updated_within_days == 180
    assert captured.max_program_age_days == 365
    assert captured.max_known_issues == 3
    assert captured.audit_older_than_days == 540
    assert captured.under_audited_only is True
    assert captured.min_scope_contracts == 3
    assert captured.max_scope_contracts == 60
    assert captured.fresh_scope_days == 90
    assert captured.languages == {Language.SOLIDITY, Language.RUST}
    assert captured.kyc is False
    assert captured.exclude_boosted is True
    assert captured.require_vault is True
    assert captured.exclude_invite_only is True
    assert captured.exclude_slugs == {"twyne", "onre"}
    # Closed programs stay excluded unless explicitly asked for.
    assert captured.include_closed is False


def test_immunefi_scan_defaults_to_an_inactive_filter() -> None:
    result = CliRunner().invoke(app, ["immunefi-scan", "--include-closed"])
    assert result.exit_code == 0, result.output
    captured = _captured_filters()
    assert captured.is_active is False
    assert captured.include_closed is True


def test_describe_filters_echoes_the_active_constraints() -> None:
    text = _describe_filters(
        ProgramFilter(
            min_max_bounty_usd=100_000,
            fresh_scope_days=90,
            languages={Language.RUST},
            kyc=False,
            exclude_boosted=True,
            exclude_slugs={"a", "b"},
        )
    )
    assert "open programs only" in text
    assert "min-bounty=$100,000" in text
    assert "fresh-scope=90d" in text
    assert "languages=rust" in text
    assert "no-kyc" in text
    assert "no-boosted" in text
    assert "exclude=2 slug(s)" in text


def test_describe_filters_calls_out_included_closed_programs() -> None:
    assert "including CLOSED programs" in _describe_filters(ProgramFilter(include_closed=True))


def test_pay_to_submit_and_premium_flags_reach_the_filter() -> None:
    result = CliRunner().invoke(
        app, ["immunefi-scan", "--exclude-pay-to-submit", "--exclude-premium"]
    )
    assert result.exit_code == 0, result.output
    captured = _captured_filters()
    assert captured.exclude_pay_to_submit is True
    assert captured.exclude_premium is True
    assert "no-pay-to-submit" in _describe_filters(captured)
    assert "no-premium" in _describe_filters(captured)
