"""Tests for GitHub commit-delta access (delta-watch)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.github_delta import (
    compare_commits,
    fetch_delta,
    get_default_branch,
    get_head_sha,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def gh_compare() -> dict:
    return json.loads((FIXTURES / "github_compare_sample.json").read_text())


@pytest.fixture(autouse=True)
def _no_auth() -> None:
    """Stub the GitHub token so tests don't touch pass/env."""
    with patch("tvl_scanner.enrich.github_delta._auth_headers", return_value={}):
        yield


async def test_get_default_branch(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs",
        json={"default_branch": "main"},
    )
    assert await get_default_branch("omnipair", "omnipair-rs") == "main"


async def test_get_default_branch_gone_repo(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/ghost/gone",
        status_code=404,
        json={"message": "Not Found"},
    )
    assert await get_default_branch("ghost", "gone") is None


async def test_get_head_sha(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/commits/main",
        json={"sha": "deadbeef00000000000000000000000000000000"},
    )
    sha = await get_head_sha("omnipair", "omnipair-rs", "main")
    assert sha == "deadbeef00000000000000000000000000000000"


async def test_compare_commits_parses_commits_and_files(
    httpx_mock: HTTPXMock, gh_compare: dict
) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/compare/a927600...deadbeef",
        json=gh_compare,
    )
    result = await compare_commits("omnipair", "omnipair-rs", "a927600", "deadbeef")
    assert result is not None
    assert result.total_commits == 3
    assert len(result.commits) == 3
    assert result.commits[0].subject == "fix(omnipair): validate borrow token identity"
    assert len(result.files) == 5
    borrow = next(f for f in result.files if f.filename.endswith("borrow.rs"))
    assert borrow.additions == 219
    assert borrow.status == "modified"
    assert result.truncated is False


async def test_compare_commits_unknown_ref_returns_none(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/compare/badref...main",
        status_code=404,
        json={"message": "Not Found"},
    )
    assert await compare_commits("omnipair", "omnipair-rs", "badref", "main") is None


async def test_fetch_delta_full_flow(httpx_mock: HTTPXMock, gh_compare: dict) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs",
        json={"default_branch": "main"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/commits/main",
        json={"sha": "deadbeef"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/compare/a927600...deadbeef",
        json=gh_compare,
    )
    out = await fetch_delta("https://github.com/omnipair/omnipair-rs", "a927600")
    assert out is not None
    branch, head, comparison = out
    assert branch == "main"
    assert head == "deadbeef"
    assert comparison is not None
    assert comparison.total_commits == 3


async def test_fetch_delta_first_run_no_baseline(httpx_mock: HTTPXMock) -> None:
    """base=None → records head, returns no comparison (first run)."""
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs",
        json={"default_branch": "main"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/commits/main",
        json={"sha": "headsha"},
    )
    out = await fetch_delta("https://github.com/omnipair/omnipair-rs", None)
    assert out is not None
    _branch, head, comparison = out
    assert head == "headsha"
    assert comparison is None  # no diff on first run


async def test_fetch_delta_base_equals_head_no_diff(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs",
        json={"default_branch": "main"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/commits/main",
        json={"sha": "samesha"},
    )
    out = await fetch_delta("https://github.com/omnipair/omnipair-rs", "samesha")
    assert out is not None
    _, head, comparison = out
    assert head == "samesha"
    assert comparison is None  # base == head → no comparison call needed


async def test_fetch_delta_unparseable_url() -> None:
    assert await fetch_delta("https://gitlab.com/foo/bar", "abc") is None
