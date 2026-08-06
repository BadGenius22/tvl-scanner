"""Tests for contest-platform audit history via GitHub search."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.audit_check.contests import (
    _normalize_query,
    check_all_contests,
    search_org,
)
from tvl_scanner.models import AuditSourceKind

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def gh_search_hit() -> dict:
    return json.loads((FIXTURES / "github_search_sherlock_hit.json").read_text())


@pytest.fixture
def gh_search_empty() -> dict:
    return json.loads((FIXTURES / "github_search_empty.json").read_text())


def test_normalize_query_strips_version_suffix() -> None:
    assert _normalize_query("Camelot V3") == "camelot"
    assert _normalize_query("Uniswap V4") == "uniswap"
    assert _normalize_query("uniswap-v3") == "uniswap"


def test_normalize_query_picks_first_meaningful_token() -> None:
    """Brand name usually comes first; trailing words like 'Finance' are too common."""
    assert _normalize_query("Factor Finance") == "factor"
    assert _normalize_query("A B CamelotLabs") == "camelotlabs"  # single-char tokens dropped


def test_normalize_query_empty_input() -> None:
    assert _normalize_query("") == ""
    assert _normalize_query("   ") == ""
    assert _normalize_query("v3") == ""  # version-only token is filtered out


async def test_search_org_parses_hits(
    httpx_mock: HTTPXMock, gh_search_hit: dict
) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/search/repositories?q=factor+in%3Aname+org%3Asherlock-audit&per_page=10",
        json=gh_search_hit,
    )

    with patch("tvl_scanner.audit_check.contests.get_secret", return_value="test-pat"):
        results = await search_org("factor", AuditSourceKind.SHERLOCK)

    assert len(results) == 2
    assert results[0].kind == AuditSourceKind.SHERLOCK
    assert results[0].repo_full_name == "sherlock-audit/2024-01-factor-finance"
    assert "sherlock-audit" in results[0].html_url


async def test_search_org_short_query_returns_empty() -> None:
    """Query tokens shorter than 3 chars should not issue a request."""
    results = await search_org("ab", AuditSourceKind.SHERLOCK)
    assert results == []


async def test_search_org_http_failure_returns_empty(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/search/repositories?q=factor+in%3Aname+org%3Asherlock-audit&per_page=10",
        status_code=422,
        json={"message": "bad query"},
        is_reusable=True,
    )
    with patch("tvl_scanner.audit_check.contests.get_secret", return_value="test-pat"):
        results = await search_org("factor", AuditSourceKind.SHERLOCK)
    assert results == []


async def test_check_all_contests_deduplicates_across_tokens(
    httpx_mock: HTTPXMock, gh_search_hit: dict, gh_search_empty: dict
) -> None:
    """When display_name and defillama_slug share a token, the same repo should only count once."""
    # The hit fixture is a Factor audit — we'll return it from Sherlock for the
    # "factor" token, and empty for everything else.
    httpx_mock.add_response(
        url="https://api.github.com/search/repositories?q=factor+in%3Aname+org%3Asherlock-audit&per_page=10",
        json=gh_search_hit,
    )
    httpx_mock.add_response(
        url="https://api.github.com/search/repositories?q=factor+in%3Aname+org%3Aspearbit&per_page=10",
        json=gh_search_empty,
    )

    with patch("tvl_scanner.audit_check.contests.get_secret", return_value="test-pat"):
        # display_name "Factor Finance" normalizes to "factor"; slug "factor" also
        # normalizes to "factor" — identical query token, should dedupe to 1 token.
        sources = await check_all_contests(
            "Factor Finance", defillama_slug="factor"
        )

    # Two repos in the fixture, both on Sherlock.
    assert len(sources) == 2
    assert all(s.source == AuditSourceKind.SHERLOCK for s in sources)
    assert all(s.weight == 3 for s in sources)


async def test_check_all_contests_no_query_token_returns_empty() -> None:
    """Empty or trivially-short display name should short-circuit with no HTTP."""
    sources = await check_all_contests("", defillama_slug=None)
    assert sources == []


def test_code4rena_is_not_a_searched_org() -> None:
    """Code4rena was retired from the search map: the `github` fine-grained PAT
    gets HTTP 422 on `org:code-423n4` (org third-party-access policy), so every
    query returned zero hits while still consuming the 30/min search bucket.
    The enum member is kept so historical artifacts still deserialize.
    """
    from tvl_scanner.audit_check.contests import AUDIT_ORGS

    assert AuditSourceKind.CODE4RENA not in AUDIT_ORGS
    assert set(AUDIT_ORGS.values()) == {"sherlock-audit", "spearbit"}
    # Member retained for backward-compatible deserialization.
    assert AuditSourceKind.CODE4RENA.value == "code4rena"


async def test_search_org_retired_kind_makes_no_request() -> None:
    """A stale kind degrades to 'no hits' rather than raising KeyError and
    aborting the whole audit-check stage. No HTTP is issued (httpx_mock absent,
    so any request would error)."""
    assert await search_org("factor", AuditSourceKind.CODE4RENA) == []
