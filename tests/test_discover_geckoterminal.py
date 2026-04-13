"""Tests for GeckoTerminal new-pools discovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.discover.geckoterminal import fetch_new_pools
from tvl_scanner.models import Chain, DiscoverySource

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def gt_arbitrum_page1() -> dict:
    return json.loads((FIXTURES / "geckoterminal_arbitrum_page1.json").read_text())


@pytest.fixture
def gt_arbitrum_page2() -> dict:
    return json.loads((FIXTURES / "geckoterminal_arbitrum_page2.json").read_text())


async def test_fetch_new_pools_applies_tvl_threshold(
    httpx_mock: HTTPXMock, gt_arbitrum_page1: dict
) -> None:
    """Pools below MIN_TVL_USD (100k default) are dropped at parse time."""
    httpx_mock.add_response(
        url="https://api.geckoterminal.com/api/v2/networks/arbitrum/new_pools?page=1&include=dex",
        json=gt_arbitrum_page1,
    )

    results = await fetch_new_pools(Chain.ARBITRUM)

    # Fixture has 3 pools: $250k (kept), $500 (dropped), $1.5M (kept).
    assert len(results) == 2
    addresses = {r.address for r in results}
    assert "0xABC123def4567890abc123def4567890abc12301" in addresses
    assert "0xFA7CAFE000000000000000000000000000000001" in addresses
    assert "0xDEADbeefDEADbeefDEADbeefDEADbeefDEADbeef" not in addresses


async def test_fetch_new_pools_parses_metadata(
    httpx_mock: HTTPXMock, gt_arbitrum_page1: dict
) -> None:
    """Pool metadata (tvl, creation date, source tag) should round-trip correctly."""
    httpx_mock.add_response(
        url="https://api.geckoterminal.com/api/v2/networks/arbitrum/new_pools?page=1&include=dex",
        json=gt_arbitrum_page1,
    )

    results = await fetch_new_pools(Chain.ARBITRUM)

    first = next(r for r in results if r.address.startswith("0xABC"))
    assert first.tvl_usd == 250000.5
    assert first.first_seen.isoformat() == "2026-03-15"
    assert first.source == DiscoverySource.GECKOTERMINAL
    assert first.chain == Chain.ARBITRUM
    # _extract_dex_slug prefers the human-readable `name` from included.attributes
    assert first.protocol_guess == "Camelot V3"
    # buyers(120) + sellers(95) = 215; × 30 = 6450
    assert first.unique_users_30d == 6450


async def test_fetch_new_pools_empty_stops_pagination(
    httpx_mock: HTTPXMock, gt_arbitrum_page2: dict
) -> None:
    """An empty `data` array should terminate pagination cleanly."""
    httpx_mock.add_response(
        url="https://api.geckoterminal.com/api/v2/networks/arbitrum/new_pools?page=1&include=dex",
        json=gt_arbitrum_page2,
    )

    results = await fetch_new_pools(Chain.ARBITRUM)
    assert results == []


async def test_fetch_new_pools_unsupported_chain_returns_empty() -> None:
    """Chains with no GeckoTerminal network mapping should short-circuit to []."""
    # Simulate by patching the mapping — no HTTP call should be made.
    from tvl_scanner.discover import geckoterminal

    original = geckoterminal.CHAIN_TO_GT_NETWORK.copy()
    try:
        geckoterminal.CHAIN_TO_GT_NETWORK.pop(Chain.BSC, None)
        result = await fetch_new_pools(Chain.BSC)
        assert result == []
    finally:
        geckoterminal.CHAIN_TO_GT_NETWORK.update(original)
