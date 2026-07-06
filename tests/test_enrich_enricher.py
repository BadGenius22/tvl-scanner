"""Tests for the Stage 2 enrichment orchestrator."""

from __future__ import annotations

import contextlib
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from tvl_scanner.enrich.defillama import DefiLlamaCatalog
from tvl_scanner.enrich.enricher import (
    _derive_languages,
    _display_name,
    _protocol_type,
    _target_slug,
    enrich_all,
    enrich_one,
)
from tvl_scanner.enrich.github import RepoMetadata
from tvl_scanner.models import (
    Chain,
    DiscoveredContract,
    DiscoverySource,
    EnrichedCandidate,
    Language,
)


def _contract(
    chain: Chain = Chain.ARBITRUM,
    guess: str | None = "Camelot V3",
    address: str = "0xABC123def4567890abc123def4567890abc12301",
) -> DiscoveredContract:
    return DiscoveredContract(
        chain=chain,
        address=address,
        protocol_guess=guess,
        tvl_usd=250000,
        first_seen=date(2026, 3, 15),
        unique_users_30d=6000,
        source=DiscoverySource.GECKOTERMINAL,
    )


def _dl_match() -> dict:
    return {
        "slug": "camelot-v3",
        "name": "Camelot V3",
        "category": "Dexes",
        "github": ["https://github.com/CamelotLabs/camelot-v3"],
        "audit_links": ["https://example.com/camelot-audit.pdf"],
    }


def test_display_name_prefers_defillama_name() -> None:
    assert _display_name(_contract(), _dl_match()) == "Camelot V3"


def test_display_name_falls_back_to_protocol_guess() -> None:
    c = _contract(guess="Raydium CLMM")
    assert _display_name(c, None) == "Raydium CLMM"


def test_display_name_falls_back_to_truncated_address() -> None:
    c = _contract(guess=None, address="0xFA7CAFE000000000000000000000000000000001")
    name = _display_name(c, None)
    # _display_name uses address[:10] (10 chars total including "0x")
    assert name.startswith("arbitrum:")
    assert "0xFA7CAFE0" in name
    assert name.endswith("…")


def test_protocol_type_uses_category() -> None:
    assert _protocol_type(_contract(), _dl_match()) == "Dexes on arbitrum"


def test_protocol_type_unknown_when_no_match() -> None:
    assert _protocol_type(_contract(), None) == "unknown protocol on arbitrum"


def test_target_slug_prefers_defillama_slug() -> None:
    assert _target_slug(_contract(), _dl_match()) == "camelot-v3"


def test_target_slug_falls_back_to_chain_address() -> None:
    c = _contract(address="0xFA7CAFE000000000000000000000000000000001")
    slug = _target_slug(c, None)
    assert slug.startswith("arbitrum-")
    assert "fa7cafe" in slug.lower()


def test_derive_languages_uses_chain_default() -> None:
    assert _derive_languages(Chain.ARBITRUM, None) == [Language.SOLIDITY]
    assert _derive_languages(Chain.SOLANA, None) == [Language.RUST]


def test_derive_languages_augments_with_github_data() -> None:
    repo = RepoMetadata(
        owner="foo",
        repo="bar",
        url="https://github.com/foo/bar",
        exists=True,
        languages={"Solidity": 100000, "Rust": 5000, "TypeScript": 2000},
    )
    langs = _derive_languages(Chain.ARBITRUM, repo)
    # Chain default (Solidity) plus Rust from GitHub
    assert Language.SOLIDITY in langs
    assert Language.RUST in langs
    assert Language.MOVE not in langs


async def test_enrich_one_happy_path_with_defillama_match() -> None:
    """A contract matched to DefiLlama + GitHub enrichment → full EnrichedCandidate."""
    catalog = DefiLlamaCatalog()
    catalog._protocols = [_dl_match()]
    catalog._loaded = True

    mock_repo = RepoMetadata(
        owner="CamelotLabs",
        repo="camelot-v3",
        url="https://github.com/CamelotLabs/camelot-v3",
        exists=True,
        default_branch="main",
        loc_estimate=3500,
        audits_folder_exists=True,
        languages={"Solidity": 100000},
    )

    with patch(
        "tvl_scanner.enrich.enricher.enrich_repo", new=AsyncMock(return_value=mock_repo)
    ):
        result = await enrich_one(_contract(), catalog)

    assert result.display_name == "Camelot V3"
    assert result.target_name == "camelot-v3"
    assert result.protocol_type == "Dexes on arbitrum"
    assert result.loc_estimate == 3500
    assert str(result.github_repo) == "https://github.com/CamelotLabs/camelot-v3"
    assert result.defillama_slug == "camelot-v3"
    assert len(result.defillama_audit_links) == 1


async def test_enrich_one_defillama_miss_still_produces_candidate() -> None:
    """A DefiLlama miss is a positive signal — the candidate should still flow through."""
    catalog = DefiLlamaCatalog()
    catalog._protocols = []  # empty catalog → every lookup misses
    catalog._loaded = True

    result = await enrich_one(_contract(guess="UnknownLeverageVault"), catalog)

    assert result is not None
    assert result.display_name == "UnknownLeverageVault"
    assert result.protocol_type == "unknown protocol on arbitrum"
    assert result.github_repo is None
    assert result.loc_estimate is None
    assert result.defillama_slug is None
    assert result.defillama_audit_links == []
    assert result.bounty_program == "none"


async def test_enrich_one_no_github_url_skips_github_call() -> None:
    """A DL match without a github URL should not trigger enrich_repo."""
    catalog = DefiLlamaCatalog()
    catalog._protocols = [
        {"slug": "no-github", "name": "NoGitHub", "category": "Yield", "github": []}
    ]
    catalog._loaded = True

    with patch(
        "tvl_scanner.enrich.enricher.enrich_repo", new=AsyncMock()
    ) as mock_enrich:
        result = await enrich_one(_contract(guess="NoGitHub"), catalog)
        mock_enrich.assert_not_called()

    assert result.github_repo is None
    assert result.display_name == "NoGitHub"


def _enriched(name: str, address: str) -> EnrichedCandidate:
    return EnrichedCandidate(
        chain=Chain.ARBITRUM,
        address=address,
        tvl_usd=250000,
        first_seen=date(2026, 3, 15),
        source=DiscoverySource.GECKOTERMINAL,
        target_name=name.lower(),
        display_name=name,
        protocol_type="unknown protocol on arbitrum",
        languages=[Language.SOLIDITY],
    )


@contextlib.asynccontextmanager
async def _fake_client():
    yield MagicMock()


async def test_enrich_all_isolates_a_single_candidate_failure() -> None:
    """One candidate raising must drop only that candidate, not abort the stage.

    Regression guard for the return_exceptions=True fault isolation in
    enrich_all — matches Stage 1's per-source resilience.
    """
    good = _contract(guess="GoodProto", address="0x" + "1" * 40)
    bad = _contract(guess="BadProto", address="0x" + "2" * 40)

    async def fake_enrich_one(contract: DiscoveredContract, catalog: object, *, client: object = None) -> EnrichedCandidate:
        if contract.protocol_guess == "BadProto":
            raise RuntimeError("simulated upstream failure")
        return _enriched("GoodProto", contract.address)

    with (
        patch("tvl_scanner.enrich.enricher.make_client", _fake_client),
        patch.object(DefiLlamaCatalog, "load", new=AsyncMock()),
        patch("tvl_scanner.enrich.enricher.enrich_one", side_effect=fake_enrich_one),
    ):
        results = await enrich_all([good, bad])

    # The stage returns the survivor rather than raising.
    assert len(results) == 1
    assert results[0].display_name == "GoodProto"


async def test_enrich_all_returns_empty_when_all_fail() -> None:
    """If every candidate fails, the stage returns [] instead of raising."""
    contracts = [
        _contract(guess="A", address="0x" + "a" * 40),
        _contract(guess="B", address="0x" + "b" * 40),
    ]

    with (
        patch("tvl_scanner.enrich.enricher.make_client", _fake_client),
        patch.object(DefiLlamaCatalog, "load", new=AsyncMock()),
        patch(
            "tvl_scanner.enrich.enricher.enrich_one",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        results = await enrich_all(contracts)

    assert results == []
