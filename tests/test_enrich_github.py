"""Tests for GitHub repo metadata enrichment."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.github import (
    _count_audit_reports,
    _estimate_loc,
    enrich_repo,
    parse_github_url,
)


def test_count_audit_reports_counts_reports_and_dirs_only() -> None:
    """Report files (.pdf/.md named for a firm/audit) and version subdirs count;
    non-audit files (README, source) do not."""
    entries = [
        {"name": "Bailsec - V3 Core - Final.pdf", "type": "file"},  # firm + pdf → 1
        {"name": "Certora_Report_final.pdf", "type": "file"},        # report + pdf → 1
        {"name": "v3.1", "type": "dir"},                             # version round → 1
        {"name": "README.md", "type": "file"},                       # not an audit → 0
        {"name": "logo.png", "type": "file"},                        # not a report → 0
    ]
    assert _count_audit_reports(entries) == 3


def test_count_audit_reports_empty_and_non_list() -> None:
    assert _count_audit_reports([]) == 0
    assert _count_audit_reports(None) == 0
    assert _count_audit_reports({"message": "Not Found"}) == 0

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def gh_repo() -> dict:
    return json.loads((FIXTURES / "github_repo_sample.json").read_text())


@pytest.fixture
def gh_langs() -> dict:
    return json.loads((FIXTURES / "github_languages_sample.json").read_text())


@pytest.fixture
def gh_audits_folder() -> list:
    return json.loads((FIXTURES / "github_audits_folder_sample.json").read_text())


def test_parse_github_url_standard_form() -> None:
    assert parse_github_url("https://github.com/CamelotLabs/camelot-v3") == (
        "CamelotLabs",
        "camelot-v3",
    )


def test_parse_github_url_with_subpath() -> None:
    assert parse_github_url(
        "https://github.com/Uniswap/v3-core/tree/main/contracts"
    ) == ("Uniswap", "v3-core")


def test_parse_github_url_git_suffix() -> None:
    assert parse_github_url("git@github.com:FactorDAO/factor-contracts.git") == (
        "FactorDAO",
        "factor-contracts",
    )


def test_parse_github_url_invalid_returns_none() -> None:
    assert parse_github_url("https://gitlab.com/foo/bar") is None
    assert parse_github_url(None) is None
    assert parse_github_url("") is None


def test_estimate_loc_sums_known_languages() -> None:
    """Only smart-contract languages should count toward LOC estimate."""
    langs = {"Solidity": 60000, "TypeScript": 9000, "Shell": 500}
    # 60000/30 + 9000/30 + 0 = 2000 + 300 = 2300
    assert _estimate_loc(langs) == 2300


def test_estimate_loc_ignores_unknown_languages() -> None:
    langs = {"Python": 50000, "Shell": 1000, "Ruby": 5000}
    assert _estimate_loc(langs) == 0


async def test_enrich_repo_full_happy_path(
    httpx_mock: HTTPXMock,
    gh_repo: dict,
    gh_langs: dict,
    gh_audits_folder: list,
) -> None:
    """Repo exists + has languages + has audits folder."""
    httpx_mock.add_response(
        url="https://api.github.com/repos/CamelotLabs/camelot-v3", json=gh_repo
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/CamelotLabs/camelot-v3/languages",
        json=gh_langs,
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/CamelotLabs/camelot-v3/contents/audits",
        json=gh_audits_folder,
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/CamelotLabs/camelot-v3/contents/docs/audits",
        status_code=404,
        json={"message": "Not Found"},
    )

    with patch("tvl_scanner.enrich.github.get_secret", return_value="test-pat"):
        result = await enrich_repo("https://github.com/CamelotLabs/camelot-v3")

    assert result is not None
    assert result.exists is True
    assert result.default_branch == "main"
    assert result.audits_folder_exists is True
    # Both fixture entries are audit reports (trail-of-bits.pdf + sherlock.md).
    assert result.audit_report_count == 2
    assert result.languages == {"Solidity": 90000, "TypeScript": 12000, "Shell": 500}
    # 90000/30 + 12000/30 = 3000 + 400 = 3400
    assert result.loc_estimate == 3400


async def test_enrich_repo_no_audits_folder_is_normal(
    httpx_mock: HTTPXMock, gh_repo: dict, gh_langs: dict
) -> None:
    """A 404 on the audits folder is a normal negative result, not an error."""
    httpx_mock.add_response(
        url="https://api.github.com/repos/CamelotLabs/camelot-v3", json=gh_repo
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/CamelotLabs/camelot-v3/languages",
        json=gh_langs,
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/CamelotLabs/camelot-v3/contents/audits",
        status_code=404,
        json={"message": "Not Found"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/CamelotLabs/camelot-v3/contents/docs/audits",
        status_code=404,
        json={"message": "Not Found"},
    )

    with patch("tvl_scanner.enrich.github.get_secret", return_value="test-pat"):
        result = await enrich_repo("https://github.com/CamelotLabs/camelot-v3")

    assert result is not None
    assert result.exists is True
    assert result.audits_folder_exists is False
    assert result.audit_report_count == 0


async def test_enrich_repo_404_on_main_call(httpx_mock: HTTPXMock) -> None:
    """Repo that returns 404 should yield exists=False, not None."""
    httpx_mock.add_response(
        url="https://api.github.com/repos/ghost/gone",
        status_code=404,
        json={"message": "Not Found"},
    )
    with patch("tvl_scanner.enrich.github.get_secret", return_value="test-pat"):
        result = await enrich_repo("https://github.com/ghost/gone")
    assert result is not None
    assert result.exists is False


async def test_enrich_repo_invalid_url_returns_none() -> None:
    with patch("tvl_scanner.enrich.github.get_secret", return_value="test-pat"):
        assert await enrich_repo("https://gitlab.com/foo/bar") is None
        assert await enrich_repo(None) is None


# ---------------------------------------------------------------------------
# Org-name candidate ordering + org-level audit-repo discovery
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_org_caches():
    """Module-level caches persist across a process; isolate each test."""
    from tvl_scanner.enrich import github as gh

    gh._ORG_NEGATIVE_CACHE.clear()
    gh._ORG_POSITIVE_CACHE.clear()
    gh._ORG_AUDIT_REPO_CACHE.clear()
    gh._RATE_LIMIT_ERRORS = 0
    yield
    gh._ORG_NEGATIVE_CACHE.clear()
    gh._ORG_POSITIVE_CACHE.clear()
    gh._ORG_AUDIT_REPO_CACHE.clear()


def test_org_candidates_try_bare_names_before_suffixes() -> None:
    """Regression: the old nesting was base-major/suffix-minor, so every budget
    slot went to suffix variants of the full slug and the first token was never
    reached. `hyperbeat-usd` produced only hyperbeat-usd{,-protocol,-dao,-finance}.
    """
    from tvl_scanner.enrich.github import _generate_org_candidates

    got = _generate_org_candidates("hyperbeat-usd", "Hyperbeat USD")
    assert got[:3] == ["hyperbeat-usd", "hyperbeat", "hyperbeatusd"]
    # The first token must be reached, and before any suffixed variant.
    assert "hyperbeat" in got
    assert got.index("hyperbeat") < min(
        (i for i, n in enumerate(got) if n.endswith("-protocol")), default=len(got)
    )


def test_org_candidates_include_0x_prefix_form() -> None:
    """`0x<name>` is a common crypto org convention (0xhyperbeat) that no
    suffix variant can reach."""
    from tvl_scanner.enrich.github import _generate_org_candidates

    got = _generate_org_candidates("hyperbeat-usd", "Hyperbeat USD")
    assert "0xhyperbeat" in got


def test_org_candidates_empty_slug() -> None:
    from tvl_scanner.enrich.github import _generate_org_candidates

    assert _generate_org_candidates("", None) == []


def test_audit_repo_name_regex_is_narrow() -> None:
    """Matches dedicated audit-report repos, not code repos that merely
    mention audits."""
    from tvl_scanner.enrich.github import _AUDIT_REPO_NAME_RE as r

    for good in ("Audits", "audits", "audit", "security-audits", "audit-reports"):
        assert r.match(good), good
    for bad in ("audited-vaults", "auditor-tools", "contracts", "audits-v2-core"):
        assert not r.match(bad), bad


async def test_find_org_audit_repo_finds_org_level_repo(httpx_mock: HTTPXMock) -> None:
    """The Hyperbeat case: slug `hyperbeat-usd`, org `0xhyperbeat`, repo `Audits`
    holding one directory per audited component."""
    from tvl_scanner.enrich.github import find_org_audit_repo

    # First candidates miss; the 0x-prefixed org is the one that exists.
    for org in ("hyperbeat-usd", "hyperbeat", "hyperbeatusd", "0xhyperbeat-usd"):
        httpx_mock.add_response(
            url=f"https://api.github.com/users/{org}/repos?sort=updated&per_page=100",
            status_code=404,
            json={"message": "Not Found"},
        )
    httpx_mock.add_response(
        url="https://api.github.com/users/0xhyperbeat/repos?sort=updated&per_page=100",
        json=[
            {"name": "DefiLlama-Adapters", "html_url": "https://github.com/0xhyperbeat/DefiLlama-Adapters"},
            {"name": "Audits", "html_url": "https://github.com/0xhyperbeat/Audits"},
        ],
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/0xhyperbeat/Audits/contents",
        json=[
            {"name": "README.md", "type": "file"},
            {"name": "liquid-bank", "type": "dir"},
            {"name": "USD+", "type": "dir"},
            {"name": "Vault-Infra", "type": "dir"},
        ],
    )

    with patch("tvl_scanner.enrich.github.get_secret", return_value="test-pat"):
        result = await find_org_audit_repo("hyperbeat-usd", "Hyperbeat USD")

    assert result == ("https://github.com/0xhyperbeat/Audits", 3)


async def test_find_org_audit_repo_rejects_empty_audit_repo(
    httpx_mock: HTTPXMock,
) -> None:
    """A repo named `audits` with no report artifacts proves nothing."""
    from tvl_scanner.enrich.github import find_org_audit_repo

    httpx_mock.add_response(
        url="https://api.github.com/users/ghostly/repos?sort=updated&per_page=100",
        json=[{"name": "audits", "html_url": "https://github.com/ghostly/audits"}],
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/ghostly/audits/contents",
        json=[{"name": "README.md", "type": "file"}],
    )
    # Remaining org-name candidates all miss.
    for org in (
        "0xghostly",
        "ghostly-protocol",
        "0xghostly-protocol",
        "ghostly-dao",
        "0xghostly-dao",
    ):
        httpx_mock.add_response(
            url=f"https://api.github.com/users/{org}/repos?sort=updated&per_page=100",
            status_code=404,
            json={"message": "Not Found"},
        )

    with patch("tvl_scanner.enrich.github.get_secret", return_value="test-pat"):
        result = await find_org_audit_repo("ghostly", "Ghostly")

    assert result is None


async def test_find_org_audit_repo_none_slug() -> None:
    from tvl_scanner.enrich.github import find_org_audit_repo

    assert await find_org_audit_repo(None) is None
