"""Tests for GitHub repo metadata enrichment."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.github import (
    _estimate_loc,
    enrich_repo,
    parse_github_url,
)

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

    with patch("tvl_scanner.enrich.github.get_secret", return_value="test-pat"):
        result = await enrich_repo("https://github.com/CamelotLabs/camelot-v3")

    assert result is not None
    assert result.exists is True
    assert result.default_branch == "main"
    assert result.audits_folder_exists is True
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

    with patch("tvl_scanner.enrich.github.get_secret", return_value="test-pat"):
        result = await enrich_repo("https://github.com/CamelotLabs/camelot-v3")

    assert result is not None
    assert result.exists is True
    assert result.audits_folder_exists is False


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
