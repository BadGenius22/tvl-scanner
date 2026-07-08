"""Tests for CLI helpers (no typer invocation — pure parsing logic)."""

from __future__ import annotations

from tvl_scanner.cli import _parse_exclude_slugs


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
