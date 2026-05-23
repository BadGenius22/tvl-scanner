"""Tests for the EVM factory-attribution enricher (Batch N)."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

from tvl_scanner.enrich.evm_factory_check import (
    KNOWN_DIRECT_CONTRACTS,
    KNOWN_FACTORIES,
    _decode_address_word,
    check_factory_attribution,
)
from tvl_scanner.models import Chain


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────────────────────────────────────


def test_decode_address_word_strips_padding() -> None:
    """eth_call return values are 32-byte words; an address is the last 20 bytes."""
    word = "0x0000000000000000000000001f98431c8ad98523631ae4a59f267346ea31f984"
    assert _decode_address_word(word) == "0x1f98431c8ad98523631ae4a59f267346ea31f984"


def test_decode_address_word_returns_none_for_zero() -> None:
    """An all-zero word means factory() returned address(0) — not a real factory."""
    assert _decode_address_word("0x" + "0" * 64) is None


def test_decode_address_word_returns_none_for_malformed() -> None:
    assert _decode_address_word(None) is None
    assert _decode_address_word("not-hex") is None
    assert _decode_address_word("0xabcd") is None  # too short


# ─────────────────────────────────────────────────────────────────────────────
# KNOWN_FACTORIES table integrity
# ─────────────────────────────────────────────────────────────────────────────


def test_known_factories_keys_are_lowercase_addresses() -> None:
    """The eth_call decoder returns lowercase. Lookup must match exactly."""
    for chain, table in KNOWN_FACTORIES.items():
        for addr, entry in table.items():
            assert addr == addr.lower(), f"{chain}/{addr} not lowercased"
            assert addr.startswith("0x") and len(addr) == 42
            assert entry.name and entry.upstream_protocol


def test_known_factories_covers_uniswap_v3_on_major_chains() -> None:
    """Uniswap V3 deploys the SAME factory address on Ethereum, Arbitrum, OP,
    Polygon (0x1F98...). Regression guard against an entry being dropped."""
    UNI_V3 = "0x1f98431c8ad98523631ae4a59f267346ea31f984"
    for chain in (Chain.ETHEREUM, Chain.ARBITRUM, Chain.OPTIMISM, Chain.POLYGON):
        assert UNI_V3 in KNOWN_FACTORIES.get(chain, {}), (
            f"Uniswap V3 factory missing from {chain.value}"
        )


def test_known_factories_excludes_solana() -> None:
    """Solana has no eth_call analog and uses different program addresses."""
    assert Chain.SOLANA not in KNOWN_FACTORIES


# ─────────────────────────────────────────────────────────────────────────────
# check_factory_attribution — orchestration
# ─────────────────────────────────────────────────────────────────────────────


async def test_check_factory_attribution_solana_returns_none() -> None:
    """Solana contracts must short-circuit before any eth_call attempt."""
    result = await check_factory_attribution(
        Chain.SOLANA, "SoSomeProgram111111111111111111111111111111"
    )
    assert result is None


async def test_check_factory_attribution_invalid_address_returns_none() -> None:
    """Synthetic addresses like 'defillama:slug' must be rejected cleanly."""
    result = await check_factory_attribution(Chain.ETHEREUM, "defillama:sodex")
    assert result is None


async def test_check_factory_attribution_matches_uniswap_v3_pool() -> None:
    """End-to-end: a Uniswap V3 pool's factory() returns the V3 factory address,
    which is in our table, and we emit a FactoryMatch. This is the rank-1
    false-positive case from the v0.6.0 scan — the WBTC/WETH pool was misclassified
    as under-audited because no other signal fired."""
    POOL = "0x4585fe77225b41b697c938b018e2ac67ac5a20c0"  # actual V3 WBTC/WETH pool
    UNI_V3_FACTORY = "0x1f98431c8ad98523631ae4a59f267346ea31f984"

    async def mock_rpc(url, method, params, client):
        assert method == "eth_call"
        # Calldata is the factory() selector
        assert params[0]["data"] == "0xc45a0155"
        # Return the factory address, padded to 32 bytes
        return "0x" + "0" * 24 + UNI_V3_FACTORY[2:]

    with patch.dict(os.environ, {"TVL_SCANNER_RPC_ETHEREUM": "https://rpc.test/"}):
        with patch(
            "tvl_scanner.enrich.evm_factory_check._rpc_call",
            new=AsyncMock(side_effect=mock_rpc),
        ):
            result = await check_factory_attribution(Chain.ETHEREUM, POOL)

    assert result is not None
    assert result.contract_address == POOL
    assert result.factory_address == UNI_V3_FACTORY
    assert result.entry.name == "Uniswap V3"
    assert result.entry.upstream_protocol == "uniswap-v3"


async def test_check_factory_attribution_unknown_factory_returns_none() -> None:
    """A factory() call that returns an address NOT in our curated table must
    NOT emit a match — we'd rather miss the attribution than falsely credit
    audits to an unknown factory."""
    POOL = "0xabcdef1234567890abcdef1234567890abcdef12"
    UNKNOWN_FACTORY = "0xdeadbeef1234567890deadbeef1234567890dead"

    async def mock_rpc(url, method, params, client):
        return "0x" + "0" * 24 + UNKNOWN_FACTORY[2:]

    with patch.dict(os.environ, {"TVL_SCANNER_RPC_ETHEREUM": "https://rpc.test/"}):
        with patch(
            "tvl_scanner.enrich.evm_factory_check._rpc_call",
            new=AsyncMock(side_effect=mock_rpc),
        ):
            result = await check_factory_attribution(Chain.ETHEREUM, POOL)

    assert result is None


async def test_check_factory_attribution_eth_call_revert_returns_none() -> None:
    """A regular ERC20 contract has no factory() function — eth_call reverts
    or returns 0x. Must produce None, not a phantom match."""
    POOL = "0xabcdef1234567890abcdef1234567890abcdef12"

    async def mock_rpc(url, method, params, client):
        return None  # _rpc_call returns None on revert/error

    with patch.dict(os.environ, {"TVL_SCANNER_RPC_ETHEREUM": "https://rpc.test/"}):
        with patch(
            "tvl_scanner.enrich.evm_factory_check._rpc_call",
            new=AsyncMock(side_effect=mock_rpc),
        ):
            result = await check_factory_attribution(Chain.ETHEREUM, POOL)

    assert result is None


async def test_check_factory_attribution_direct_match_v4_poolmanager() -> None:
    """Uniswap V4 PoolManager on Arbitrum is matched by its OWN address —
    not via factory() — because V4 pools live as state inside one singleton,
    not as separate contracts. This is the second prong of factory attribution.

    Regression guard for v0.6.0+: the V4 PoolManager surfaced as rank 5 in
    the scan tagged 'unknown protocol, 0d old' because none of the per-pool
    signals fired."""
    POOL_MANAGER = "0x360e68faccca8ca495c1b759fd9eee466db9fb32"

    # Mock _rpc_call to verify direct-match path skips the eth_call entirely
    eth_call_invoked = False

    async def mock_rpc(*args, **kwargs):
        nonlocal eth_call_invoked
        eth_call_invoked = True
        return None

    with patch(
        "tvl_scanner.enrich.evm_factory_check._rpc_call",
        new=AsyncMock(side_effect=mock_rpc),
    ):
        result = await check_factory_attribution(Chain.ARBITRUM, POOL_MANAGER)

    assert result is not None
    assert result.contract_address == POOL_MANAGER
    assert result.entry.name == "Uniswap V4 PoolManager"
    assert eth_call_invoked is False, (
        "direct-match path should not invoke eth_call"
    )


def test_known_direct_contracts_covers_v4_on_major_chains() -> None:
    """V4 PoolManager is deployed on every chain we scan. Regression guard."""
    for chain in (
        Chain.ETHEREUM,
        Chain.ARBITRUM,
        Chain.BASE,
        Chain.OPTIMISM,
        Chain.POLYGON,
        Chain.BSC,
    ):
        table = KNOWN_DIRECT_CONTRACTS.get(chain, {})
        has_v4 = any(e.upstream_protocol == "uniswap-v4" for e in table.values())
        assert has_v4, f"Uniswap V4 PoolManager missing from {chain.value}"


async def test_check_factory_attribution_no_rpc_url_returns_none() -> None:
    """Missing both env override and Alchemy key → silent None."""
    env_clean = {
        k: v for k, v in os.environ.items() if not k.startswith("TVL_SCANNER_RPC_")
    }
    with patch.dict(os.environ, env_clean, clear=True):
        with patch(
            "tvl_scanner.enrich.evm_factory_check.get_secret", return_value=None
        ):
            result = await check_factory_attribution(
                Chain.ETHEREUM, "0xabcdef1234567890abcdef1234567890abcdef12"
            )
            assert result is None
