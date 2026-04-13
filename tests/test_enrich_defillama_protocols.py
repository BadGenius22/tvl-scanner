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
    """Register a catch-all 404 mock for every /protocol/<slug> detail URL.

    Batch G wired catalog-discovery through fetch_detail — the existing tests
    didn't anticipate that extra HTTP call. Returning 404 here exercises the
    "detail fetch failed, fall back to flat catalog data" path, which is the
    exact behavior we want under test (we're verifying that catalog discovery
    still works even when the detail endpoint is unavailable).
    """
    httpx_mock.add_response(
        url=re.compile(r"^https://api\.llama\.fi/protocol/.*$"),
        status_code=404,
        json={"error": "not found"},
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
