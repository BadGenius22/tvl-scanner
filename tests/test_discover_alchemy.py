"""Tests for the Alchemy fresh-deployment discoverer."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tvl_scanner.discover.alchemy import (
    BLOCK_TIME_SECONDS,
    CHAIN_TO_ALCHEMY_SUBDOMAIN,
    _extract_creations,
    _hex_to_int,
    _sample_blocks,
    fetch_fresh_deployments,
)
from tvl_scanner.enrich.prices import PriceCache
from tvl_scanner.models import Chain, DiscoverySource


def test_hex_to_int_handles_various_forms() -> None:
    assert _hex_to_int("0x0") == 0
    assert _hex_to_int("0x1") == 1
    assert _hex_to_int("0x1234") == 4660
    assert _hex_to_int(None) == 0
    assert _hex_to_int("not-a-hex") == 0


def test_extract_creations_filters_successful_only() -> None:
    """Only receipts with contractAddress AND status 0x1 should count."""
    receipts = [
        {"contractAddress": "0xAAA", "status": "0x1"},       # kept
        {"contractAddress": "0xBBB", "status": "0x0"},       # reverted - dropped
        {"contractAddress": None, "status": "0x1"},          # normal tx - dropped
        {"contractAddress": "0xCCC", "status": "0x1"},       # kept
        {"status": "0x1"},                                   # no addr - dropped
    ]
    result = _extract_creations(receipts, Chain.ARBITRUM)
    assert result == ["0xAAA", "0xCCC"]


def test_sample_blocks_returns_distinct_sorted_range() -> None:
    latest = 200_000_000
    # Arbitrum has 0.26s block time — 7 days = ~2.3M blocks
    blocks = _sample_blocks(latest, Chain.ARBITRUM, lookback_days=7, samples=50)
    assert len(blocks) == 50
    assert blocks == sorted(blocks)
    assert len(set(blocks)) == 50  # all distinct
    # All within last 7 days of window
    block_time = BLOCK_TIME_SECONDS[Chain.ARBITRUM]
    window = int(7 * 86400 / block_time)
    assert all(latest - window <= b <= latest for b in blocks)


def test_sample_blocks_reproducible_within_scan() -> None:
    """Seeding on `latest` means two calls in the same scan return identical blocks."""
    blocks_a = _sample_blocks(123_456, Chain.ETHEREUM, lookback_days=1, samples=10)
    blocks_b = _sample_blocks(123_456, Chain.ETHEREUM, lookback_days=1, samples=10)
    assert blocks_a == blocks_b


def test_sample_blocks_zero_latest_returns_empty() -> None:
    """A failed eth_blockNumber lookup (latest=0) should yield empty sample list."""
    assert _sample_blocks(0, Chain.ETHEREUM, lookback_days=7, samples=50) == []


def test_chain_mapping_skips_solana() -> None:
    """Alchemy module intentionally excludes Solana (different program model)."""
    assert Chain.SOLANA not in CHAIN_TO_ALCHEMY_SUBDOMAIN
    for evm in (Chain.ETHEREUM, Chain.ARBITRUM, Chain.BASE, Chain.OPTIMISM,
                Chain.POLYGON, Chain.BSC):
        assert evm in CHAIN_TO_ALCHEMY_SUBDOMAIN


async def test_fetch_fresh_deployments_no_api_key_returns_empty() -> None:
    """Missing Alchemy key should degrade to [], not raise."""
    with patch("tvl_scanner.discover.alchemy.get_secret", return_value=None):
        cache = PriceCache()
        result = await fetch_fresh_deployments(Chain.ARBITRUM, price_cache=cache)
        assert result == []


async def test_fetch_fresh_deployments_solana_returns_empty() -> None:
    """Solana is not in the Alchemy subdomain map → empty without HTTP."""
    with patch("tvl_scanner.discover.alchemy.get_secret", return_value="test-key"):
        cache = PriceCache()
        result = await fetch_fresh_deployments(Chain.SOLANA, price_cache=cache)
        assert result == []


async def test_fetch_fresh_deployments_happy_path() -> None:
    """End-to-end: block num → receipts → creations → balance → USD filter → records.

    We patch the low-level RPC calls directly since Alchemy responses are JSON-RPC
    POST bodies which pytest-httpx handles awkwardly. Tests the orchestration
    without testing httpx.
    """
    # Mock responses:
    # - latest block = 100
    # - sampled block 95 has receipts with 2 creations: one kept, one below threshold
    # - sampled block 90 has no creations

    async def mock_rpc(url, method, params, client):
        if method == "eth_blockNumber":
            return "0x64"  # 100
        if method == "alchemy_getTransactionReceipts":
            block_hex = params[0]["blockNumber"]
            block = int(block_hex, 16)
            if block == 95 or block == 90:
                return {
                    "receipts": [
                        {"contractAddress": "0xHigh", "status": "0x1"},
                        {"contractAddress": "0xLow", "status": "0x1"},
                    ]
                }
            return {"receipts": []}
        if method == "eth_getBalance":
            addr = params[0]
            if addr == "0xHigh":
                return hex(50 * 10**18)  # 50 ETH
            if addr == "0xLow":
                return hex(1 * 10**17)  # 0.1 ETH
            return "0x0"
        if method == "alchemy_getTokenBalances":
            # Return empty token holdings for both addrs — this test exercises
            # the native-only path. A separate test covers the ERC20 path.
            return {"tokenBalances": []}
        return None

    price_cache = PriceCache()
    # Pre-seed the price cache so we don't hit Coingecko
    price_cache._prices[Chain.ARBITRUM] = 3000.0

    with (
        patch("tvl_scanner.discover.alchemy.get_secret", return_value="test-key"),
        patch("tvl_scanner.discover.alchemy._rpc_call", new=AsyncMock(side_effect=mock_rpc)),
        patch(
            "tvl_scanner.discover.alchemy._sample_blocks",
            return_value=[95, 90],  # deterministic for this test
        ),
    ):
        # No ERC20 tokens → fetch_prices is never called, no mock needed
        result = await fetch_fresh_deployments(
            Chain.ARBITRUM,
            price_cache=price_cache,
            lookback_days=7,
            sample_blocks=2,
        )

    # 50 ETH × $3000 = $150k > $100k threshold → kept
    # 0.1 ETH × $3000 = $300 < $100k → dropped
    # But receipt list has duplicates across 2 blocks → 2 kept records
    assert len(result) == 2
    addrs = {r.address for r in result}
    assert addrs == {"0xHigh"}  # deduped across blocks
    assert all(r.source == DiscoverySource.ALCHEMY_DEPLOYMENTS for r in result)
    assert all(r.tvl_usd == pytest.approx(150000.0) for r in result)
    assert all(r.chain == Chain.ARBITRUM for r in result)


async def test_fetch_fresh_deployments_counts_erc20_holdings() -> None:
    """Batch I fix #3: contracts holding USDC/WETH should now pass the TVL filter
    even when they have zero native balance.
    """
    from tvl_scanner.enrich.defillama_prices import TokenPrice

    USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"  # real USDC address
    WETH = "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"  # example

    async def mock_rpc(url, method, params, client):
        if method == "eth_blockNumber":
            return "0x64"
        if method == "alchemy_getTransactionReceipts":
            return {"receipts": [{"contractAddress": "0xDeFiContract", "status": "0x1"}]}
        if method == "eth_getBalance":
            return "0x0"  # zero native balance
        if method == "alchemy_getTokenBalances":
            return {
                "tokenBalances": [
                    # 150,000 USDC = 150_000 × 10^6
                    {"contractAddress": USDC, "tokenBalance": hex(150_000 * 10**6)},
                    # 0.5 WETH = 5 × 10^17
                    {"contractAddress": WETH, "tokenBalance": hex(5 * 10**17)},
                ]
            }
        return None

    mock_prices = {
        f"arbitrum:{USDC.lower()}": TokenPrice(
            symbol="USDC", price=1.0, decimals=6, confidence=1.0
        ),
        f"arbitrum:{WETH.lower()}": TokenPrice(
            symbol="WETH", price=3000.0, decimals=18, confidence=1.0
        ),
    }

    price_cache = PriceCache()
    price_cache._prices[Chain.ARBITRUM] = 3000.0

    with (
        patch("tvl_scanner.discover.alchemy.get_secret", return_value="test-key"),
        patch("tvl_scanner.discover.alchemy._rpc_call", new=AsyncMock(side_effect=mock_rpc)),
        patch("tvl_scanner.discover.alchemy._sample_blocks", return_value=[95]),
        patch(
            "tvl_scanner.discover.alchemy.fetch_prices",
            new=AsyncMock(return_value=mock_prices),
        ),
    ):
        result = await fetch_fresh_deployments(
            Chain.ARBITRUM,
            price_cache=price_cache,
            lookback_days=7,
            sample_blocks=1,
        )

    # USDC: 150,000 × $1.0 = $150,000
    # WETH: 0.5 × $3,000 = $1,500
    # Native: 0 × $3,000 = $0
    # Total: $151,500 > $100k → kept
    assert len(result) == 1
    assert result[0].address == "0xDeFiContract"
    assert result[0].tvl_usd == pytest.approx(151500.0, rel=0.001)


async def test_fetch_fresh_deployments_skips_unknown_tokens() -> None:
    """Tokens that DefiLlama can't price should be silently skipped, not crash."""
    UNKNOWN = "0xDeadBeefDeadBeefDeadBeefDeadBeefDeadBeef"

    async def mock_rpc(url, method, params, client):
        if method == "eth_blockNumber":
            return "0x64"
        if method == "alchemy_getTransactionReceipts":
            return {"receipts": [{"contractAddress": "0xNoPriceToken", "status": "0x1"}]}
        if method == "eth_getBalance":
            return hex(40 * 10**18)  # 40 ETH = $120k native → above threshold
        if method == "alchemy_getTokenBalances":
            return {
                "tokenBalances": [
                    {"contractAddress": UNKNOWN, "tokenBalance": hex(10**18)},
                ]
            }
        return None

    price_cache = PriceCache()
    price_cache._prices[Chain.ARBITRUM] = 3000.0

    with (
        patch("tvl_scanner.discover.alchemy.get_secret", return_value="test-key"),
        patch("tvl_scanner.discover.alchemy._rpc_call", new=AsyncMock(side_effect=mock_rpc)),
        patch("tvl_scanner.discover.alchemy._sample_blocks", return_value=[95]),
        patch(
            "tvl_scanner.discover.alchemy.fetch_prices",
            new=AsyncMock(return_value={}),  # no prices returned
        ),
    ):
        result = await fetch_fresh_deployments(
            Chain.ARBITRUM,
            price_cache=price_cache,
            lookback_days=7,
            sample_blocks=1,
        )

    # Only native balance counted (ERC20 unknown → skipped), 40 ETH × $3000 = $120k
    assert len(result) == 1
    assert result[0].tvl_usd == pytest.approx(120000.0)


async def test_fetch_fresh_deployments_zero_native_price_returns_empty() -> None:
    """If price fetch returns 0 (Coingecko down + no fallback), the scanner should bail."""
    async def mock_rpc(url, method, params, client):
        if method == "eth_blockNumber":
            return "0x64"
        if method == "alchemy_getTransactionReceipts":
            return {"receipts": [{"contractAddress": "0xAAA", "status": "0x1"}]}
        if method == "eth_getBalance":
            return hex(50 * 10**18)
        return None

    price_cache = PriceCache()
    price_cache._prices[Chain.ARBITRUM] = 0.0

    with (
        patch("tvl_scanner.discover.alchemy.get_secret", return_value="test-key"),
        patch("tvl_scanner.discover.alchemy._rpc_call", new=AsyncMock(side_effect=mock_rpc)),
        patch("tvl_scanner.discover.alchemy._sample_blocks", return_value=[95]),
    ):
        result = await fetch_fresh_deployments(
            Chain.ARBITRUM,
            price_cache=price_cache,
            lookback_days=1,
            sample_blocks=1,
        )
    assert result == []


async def test_fetch_fresh_deployments_eth_block_number_failure_returns_empty() -> None:
    """If eth_blockNumber returns 0 (auth failure, RPC down), degrade gracefully."""
    async def mock_rpc(url, method, params, client):
        if method == "eth_blockNumber":
            return None
        return None

    with (
        patch("tvl_scanner.discover.alchemy.get_secret", return_value="test-key"),
        patch("tvl_scanner.discover.alchemy._rpc_call", new=AsyncMock(side_effect=mock_rpc)),
    ):
        result = await fetch_fresh_deployments(
            Chain.ARBITRUM, price_cache=PriceCache()
        )
    assert result == []
