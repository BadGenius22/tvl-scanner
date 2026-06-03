"""Tests for DefiLlama catalog protocol-level discovery (Stage 1.5)."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.defillama_protocols import (
    SCANNABLE_CATEGORIES,
    _pick_primary_chain,
    discover_from_defillama_catalog,
)
from tvl_scanner.models import Chain, DiscoverySource

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_detail_404_for_all(httpx_mock: HTTPXMock) -> None:
    """Register catch-all 404 mocks for every /protocol/<slug> detail URL AND
    every protocol homepage URL.

    Batch G wired catalog-discovery through fetch_detail. Batch J/K added a
    homepage scrape that fires for every catalog candidate. Both extra HTTP
    calls need to be mocked here — returning 404 exercises the "fetch failed,
    fall back to flat catalog data" path, which is the exact behavior we
    want under test (we're verifying that catalog discovery still works even
    when both endpoints are unavailable).
    """
    httpx_mock.add_response(
        url=re.compile(r"^https://api\.llama\.fi/protocol/.*$"),
        status_code=404,
        json={"error": "not found"},
        is_reusable=True,
    )
    # Catch-all for protocol homepage URLs (Batch K homepage scrape). Match
    # any HTTPS URL not on api.llama.fi.
    httpx_mock.add_response(
        url=re.compile(r"^https://(?!api\.llama\.fi).*$"),
        status_code=404,
        text="",
        is_reusable=True,
    )


@pytest.fixture
def catalog_sample() -> list[dict]:
    return json.loads((FIXTURES / "defillama_protocols_catalog.json").read_text())


def test_scannable_categories_includes_audit_rich_types() -> None:
    """Sanity: the main categories we care about are in the allowlist."""
    for expected in ("Lending", "Yield", "Leveraged Farming", "CDP", "Bridge",
                     "Liquid Staking", "Derivatives"):
        assert expected in SCANNABLE_CATEGORIES


def test_scannable_categories_excludes_noise() -> None:
    """Chain/CEX/other non-protocol categories must NOT be scanned."""
    for rejected in ("Chain", "CEX", "Indexer", "RWA-Offchain"):
        assert rejected not in SCANNABLE_CATEGORIES


def test_pick_primary_chain_picks_first_configured() -> None:
    protocol = {"chains": ["Polygon", "Arbitrum", "Base"]}
    chain = _pick_primary_chain(protocol, {Chain.ARBITRUM, Chain.BASE})
    # Polygon is first but not in configured set — should skip to Arbitrum
    assert chain == Chain.ARBITRUM


def test_pick_primary_chain_none_if_all_out_of_scope() -> None:
    protocol = {"chains": ["Tron", "Fantom"]}
    assert _pick_primary_chain(protocol, {Chain.ARBITRUM}) is None


async def test_catalog_discovery_filters_by_category(
    httpx_mock: HTTPXMock, catalog_sample: list[dict]
) -> None:
    """Entries with non-scannable category should be dropped."""
    httpx_mock.add_response(url="https://api.llama.fi/protocols", json=catalog_sample)
    _mock_detail_404_for_all(httpx_mock)

    with patch(
        "tvl_scanner.enrich.defillama_protocols.enrich_repo",
        new=AsyncMock(return_value=None),
    ):
        results = await discover_from_defillama_catalog(scan_date=date(2026, 4, 13))

    slugs = {r.target_name for r in results}
    assert "wrong-cat" not in slugs  # Chain category dropped
    assert "too-small" not in slugs  # below MIN_TVL
    assert "wrong-chain" not in slugs  # chain not in scope


async def test_catalog_discovery_keeps_relevant_entries(
    httpx_mock: HTTPXMock, catalog_sample: list[dict]
) -> None:
    """The Lending/Leveraged Farming entries above threshold should all survive."""
    httpx_mock.add_response(url="https://api.llama.fi/protocols", json=catalog_sample)
    _mock_detail_404_for_all(httpx_mock)

    with patch(
        "tvl_scanner.enrich.defillama_protocols.enrich_repo",
        new=AsyncMock(return_value=None),
    ):
        results = await discover_from_defillama_catalog(scan_date=date(2026, 4, 13))

    slugs = {r.target_name for r in results}
    assert "fresh-leverage-vault" in slugs
    assert "lending-fork" in slugs


async def test_catalog_discovery_applies_bounty_match(
    httpx_mock: HTTPXMock, catalog_sample: list[dict]
) -> None:
    """The Aave entry should hit the bounty registry and get bounty_program=immunefi."""
    httpx_mock.add_response(url="https://api.llama.fi/protocols", json=catalog_sample)
    _mock_detail_404_for_all(httpx_mock)

    # Force the lru_cache to reload on this test
    from tvl_scanner.enrich.bounty import load_registry
    load_registry.cache_clear()

    with patch(
        "tvl_scanner.enrich.defillama_protocols.enrich_repo",
        new=AsyncMock(return_value=None),
    ):
        results = await discover_from_defillama_catalog(scan_date=date(2026, 4, 13))

    aave = next((r for r in results if r.target_name == "aave-v3"), None)
    assert aave is not None
    assert aave.bounty_program == "immunefi"
    assert aave.bounty_max_payout_usd == 1_000_000
    assert str(aave.bounty_url).startswith("https://immunefi.com")


async def test_catalog_discovery_populates_audit_count_from_detail(
    httpx_mock: HTTPXMock, catalog_sample: list[dict]
) -> None:
    """Batch G fix #4: catalog-sourced candidates should gain audit_count + audit_note
    from /protocol/{slug} detail calls.
    """
    httpx_mock.add_response(url="https://api.llama.fi/protocols", json=catalog_sample)
    # Catch-all 404 for protocol homepage URLs (Batch K homepage scrape will
    # try to fetch each protocol's `url` field).
    httpx_mock.add_response(
        url=re.compile(r"^https://(?!api\.llama\.fi).*$"),
        status_code=404,
        text="",
        is_reusable=True,
    )
    # Every slug EXCEPT aave-v3 returns 404; aave-v3 returns a successful detail
    # with audit_count=3 and an audit_note.
    httpx_mock.add_response(
        url="https://api.llama.fi/protocol/fresh-leverage-vault",
        status_code=404,
        is_reusable=True,
    )
    httpx_mock.add_response(
        url="https://api.llama.fi/protocol/lending-fork",
        status_code=404,
        is_reusable=True,
    )
    httpx_mock.add_response(
        url="https://api.llama.fi/protocol/aave-v3",
        json={
            "id": "15",
            "name": "Aave",
            "slug": "aave-v3",
            "audits": 3,
            "audit_note": "Last audited 2024-05 by Trail of Bits, ABDK, Certora.",
            "audit_links": ["https://example.com/aave-extra.pdf"],
            "github": ["https://github.com/aave/aave-v3-core"],
        },
        is_reusable=True,
    )

    from tvl_scanner.enrich.bounty import load_registry
    load_registry.cache_clear()

    with patch(
        "tvl_scanner.enrich.defillama_protocols.enrich_repo",
        new=AsyncMock(return_value=None),
    ):
        results = await discover_from_defillama_catalog(scan_date=date(2026, 4, 13))

    aave = next((r for r in results if r.target_name == "aave-v3"), None)
    assert aave is not None
    assert aave.defillama_audit_count == 3
    assert aave.defillama_audit_note is not None
    assert "Trail of Bits" in aave.defillama_audit_note
    # Merged audit_links should contain both the flat link and the detail-only one
    link_strs = [str(u) for u in aave.defillama_audit_links]
    assert any("aave-audit.pdf" in u for u in link_strs)
    assert any("aave-extra.pdf" in u for u in link_strs)


async def test_catalog_discovery_sources_enrichment_metadata(
    httpx_mock: HTTPXMock, catalog_sample: list[dict]
) -> None:
    """Output records should use DEFILLAMA_CATALOG source + defillama: address prefix."""
    httpx_mock.add_response(url="https://api.llama.fi/protocols", json=catalog_sample)
    _mock_detail_404_for_all(httpx_mock)

    with patch(
        "tvl_scanner.enrich.defillama_protocols.enrich_repo",
        new=AsyncMock(return_value=None),
    ):
        results = await discover_from_defillama_catalog(scan_date=date(2026, 4, 13))

    for r in results:
        assert r.source == DiscoverySource.DEFILLAMA_CATALOG
        assert r.address.startswith("defillama:")
        assert r.defillama_slug is not None


def test_parse_detail_address_variants() -> None:
    """True-age fix: parse DefiLlama detail `address` into (chain, evm_addr)."""
    from tvl_scanner.enrich.defillama_protocols import _parse_detail_address

    # bare 0x → implicitly Ethereum
    assert _parse_detail_address("0x584bC13c7D411c00c01A62e8019472dE68768430") == (
        Chain.ETHEREUM,
        "0x584bC13c7D411c00c01A62e8019472dE68768430",
    )
    # chain-qualified
    assert _parse_detail_address("bsc:0xe0e514c71282b6f4e823703a39374cf58dc3ea4f") == (
        Chain.BSC,
        "0xe0e514c71282b6f4e823703a39374cf58dc3ea4f",
    )
    # rejected: Solana base58, unknown chain prefix, wrong length, None
    assert _parse_detail_address("So11111111111111111111111111111111111111112") == (None, None)
    assert _parse_detail_address("avax:0xe0e514c71282b6f4e823703a39374cf58dc3ea4f") == (None, None)
    assert _parse_detail_address("0xshort") == (None, None)
    assert _parse_detail_address(None) == (None, None)


async def test_resolve_true_deploy_dates_overrides_first_seen() -> None:
    """The resolver flips first_seen to the real deploy date for candidates with
    an on-chain address, and leaves address-less candidates at their placeholder."""
    from unittest.mock import AsyncMock as _AsyncMock
    from unittest.mock import patch as _patch

    from tvl_scanner.enrich.defillama_protocols import _resolve_true_deploy_dates
    from tvl_scanner.models import EnrichedCandidate, Language

    placeholder = date(2025, 12, 5)

    def _mk(slug: str, onchain: str | None) -> EnrichedCandidate:
        return EnrichedCandidate(
            chain=Chain.ETHEREUM,
            address=f"defillama:{slug}",
            tvl_usd=1_000_000,
            first_seen=placeholder,
            source=DiscoverySource.DEFILLAMA_CATALOG,
            target_name=slug,
            display_name=slug,
            protocol_type="Test",
            languages=[Language.SOLIDITY],
            onchain_address=onchain,
        )

    cands = [
        _mk("hegic", "ethereum:0x584bc13c7d411c00c01a62e8019472de68768430"),
        _mk("no-addr", None),
    ]
    fake = _AsyncMock(
        return_value={"0x584bc13c7d411c00c01a62e8019472de68768430": date(2020, 8, 8)}
    )
    with _patch(
        "tvl_scanner.enrich.defillama_protocols.fetch_creation_dates_batch", new=fake
    ):
        await _resolve_true_deploy_dates(cands, None)

    assert cands[0].first_seen == date(2020, 8, 8)  # flipped to true deploy date
    assert cands[1].first_seen == placeholder  # no address → unchanged
    fake.assert_awaited_once()  # single ethereum batch


async def test_resolve_true_deploy_dates_noop_without_addresses() -> None:
    """No on-chain addresses → resolver makes no Etherscan call at all (hermetic)."""
    from unittest.mock import AsyncMock as _AsyncMock
    from unittest.mock import patch as _patch

    from tvl_scanner.enrich.defillama_protocols import _resolve_true_deploy_dates
    from tvl_scanner.models import EnrichedCandidate, Language

    cand = EnrichedCandidate(
        chain=Chain.SOLANA,
        address="defillama:jupiter",
        tvl_usd=1_000_000,
        first_seen=date(2025, 12, 5),
        source=DiscoverySource.DEFILLAMA_CATALOG,
        target_name="jupiter",
        display_name="Jupiter",
        protocol_type="Test",
        languages=[Language.RUST],
        onchain_address=None,
    )
    fake = _AsyncMock(return_value={})
    with _patch(
        "tvl_scanner.enrich.defillama_protocols.fetch_creation_dates_batch", new=fake
    ):
        await _resolve_true_deploy_dates([cand], None)

    fake.assert_not_awaited()  # early-return before any chain batch
