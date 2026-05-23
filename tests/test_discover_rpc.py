"""Tests for the pure-RPC active-holder discoverer."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from tvl_scanner.discover.rpc import (
    CURATED_TOKENS,
    _decode_topic_address,
    _encode_address_param,
    _extract_recipients,
    _hex_to_int,
    _rpc_url,
    _sample_windows,
    fetch_active_holders,
)
from tvl_scanner.enrich.prices import PriceCache
from tvl_scanner.models import Chain, DiscoverySource

# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────────────────────────────────────


def test_hex_to_int_handles_various_forms() -> None:
    assert _hex_to_int("0x0") == 0
    assert _hex_to_int("0x1") == 1
    assert _hex_to_int("0x1234") == 4660
    assert _hex_to_int(None) == 0
    assert _hex_to_int("not-a-hex") == 0


def test_decode_topic_address_strips_left_padding() -> None:
    """Topics are 32 bytes; an address is the last 20 bytes."""
    topic = "0x000000000000000000000000a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    assert _decode_topic_address(topic) == "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"


def test_decode_topic_address_rejects_malformed() -> None:
    assert _decode_topic_address("0xtoo-short") is None
    assert _decode_topic_address("missing-prefix-0000") is None
    assert _decode_topic_address(None) is None  # type: ignore[arg-type]


def test_encode_address_param_zero_pads_to_32_bytes() -> None:
    """balanceOf(address) calldata: 4-byte selector + 32-byte zero-padded address."""
    encoded = _encode_address_param("0xABCD")
    assert len(encoded) == 64
    assert encoded.endswith("abcd")
    assert set(encoded[: 64 - 4]) == {"0"}  # leading 60 hex chars are zeros


def test_encode_address_param_lowercases() -> None:
    """Checksummed addresses must be lowercased — RPC ignores case but log
    comparisons rely on consistent casing."""
    encoded = _encode_address_param("0xABcDeF1234567890ABCDEF1234567890ABCDEF12")
    assert encoded == "0" * 24 + "abcdef1234567890abcdef1234567890abcdef12"


def test_extract_recipients_pulls_topic_two() -> None:
    """Transfer event: topics = [Transfer_sig, from_addr, to_addr]. We want to_addr."""
    logs = [
        {
            "topics": [
                "0xddf252ad",
                "0x" + "0" * 24 + "aa" * 20,  # from
                "0x" + "0" * 24 + "bb" * 20,  # to (what we want)
            ]
        },
        {
            "topics": [
                "0xddf252ad",
                "0x" + "0" * 24 + "cc" * 20,
                "0x" + "0" * 24 + "dd" * 20,
            ]
        },
        # Malformed: too few topics — must be skipped silently
        {"topics": ["0xddf252ad", "0x000"]},
        # Malformed: not a dict — must be skipped silently
        "not-a-log",
    ]
    recipients = _extract_recipients(logs)  # type: ignore[arg-type]
    assert recipients == {
        "0x" + "bb" * 20,
        "0x" + "dd" * 20,
    }


def test_extract_recipients_dedupes() -> None:
    """Same recipient in multiple Transfer logs should collapse to one entry."""
    to_addr = "0x" + "0" * 24 + "ee" * 20
    logs = [
        {"topics": ["0xddf252ad", "0x" + "0" * 24 + "aa" * 20, to_addr]},
        {"topics": ["0xddf252ad", "0x" + "0" * 24 + "bb" * 20, to_addr]},
        {"topics": ["0xddf252ad", "0x" + "0" * 24 + "cc" * 20, to_addr]},
    ]
    assert _extract_recipients(logs) == {"0x" + "ee" * 20}


# ─────────────────────────────────────────────────────────────────────────────
# Window sampling
# ─────────────────────────────────────────────────────────────────────────────


def test_sample_windows_returns_distinct_non_overlapping_ranges() -> None:
    latest = 200_000_000
    windows = _sample_windows(
        latest, Chain.ARBITRUM, lookback_days=7, windows=20, window_blocks=50
    )
    assert len(windows) == 20
    # Each window is exactly 50 blocks
    for from_b, to_b in windows:
        assert to_b - from_b == 50
    # Sorted (ascending)
    assert windows == sorted(windows)
    # All within the last 7 days of blocks
    block_time = 0.26
    range_blocks = int(7 * 86400 / block_time)
    for from_b, to_b in windows:
        assert latest - range_blocks <= from_b
        assert to_b <= latest


def test_sample_windows_reproducible_for_same_latest() -> None:
    a = _sample_windows(
        123_456, Chain.ETHEREUM, lookback_days=7, windows=10, window_blocks=50
    )
    b = _sample_windows(
        123_456, Chain.ETHEREUM, lookback_days=7, windows=10, window_blocks=50
    )
    assert a == b


def test_sample_windows_zero_latest_returns_empty() -> None:
    assert _sample_windows(0, Chain.ETHEREUM, lookback_days=7, windows=10, window_blocks=50) == []


# ─────────────────────────────────────────────────────────────────────────────
# RPC URL resolution
# ─────────────────────────────────────────────────────────────────────────────


def test_rpc_url_prefers_env_override_over_alchemy() -> None:
    """A user-set TVL_SCANNER_RPC_<CHAIN> must short-circuit Alchemy lookup —
    this is the seam that lets users plug their own node without changing code."""
    with patch.dict(os.environ, {"TVL_SCANNER_RPC_BASE": "https://my.node/rpc"}):
        with patch("tvl_scanner.discover.rpc.get_secret", return_value="alchemy-key"):
            assert _rpc_url(Chain.BASE) == "https://my.node/rpc"


def test_rpc_url_falls_back_to_alchemy_when_no_env() -> None:
    # Ensure no env override
    env_clean = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("TVL_SCANNER_RPC_")
    }
    with patch.dict(os.environ, env_clean, clear=True):
        with patch("tvl_scanner.discover.rpc.get_secret", return_value="alchemy-key"):
            url = _rpc_url(Chain.BASE)
            assert url is not None
            assert url.startswith("https://base-mainnet.g.alchemy.com/")
            assert url.endswith("alchemy-key")


def test_rpc_url_returns_none_when_no_credentials_and_no_env() -> None:
    env_clean = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("TVL_SCANNER_RPC_")
    }
    with patch.dict(os.environ, env_clean, clear=True):
        with patch("tvl_scanner.discover.rpc.get_secret", return_value=None):
            assert _rpc_url(Chain.BASE) is None


def test_rpc_url_skips_solana() -> None:
    """Solana has its own address model — not handled by this RPC discoverer."""
    with patch("tvl_scanner.discover.rpc.get_secret", return_value="alchemy-key"):
        assert _rpc_url(Chain.SOLANA) is None


# ─────────────────────────────────────────────────────────────────────────────
# Curated token catalog
# ─────────────────────────────────────────────────────────────────────────────


def test_curated_tokens_covers_all_evm_chains() -> None:
    """Every EVM chain in the Chain enum must have at least 3 curated tokens —
    fewer and we'd miss too many DeFi vaults whose balances are split across
    stables + WETH."""
    for chain in (
        Chain.ETHEREUM,
        Chain.ARBITRUM,
        Chain.BASE,
        Chain.OPTIMISM,
        Chain.POLYGON,
        Chain.BSC,
    ):
        tokens = CURATED_TOKENS.get(chain, [])
        assert len(tokens) >= 3, f"{chain} has only {len(tokens)} curated tokens"
        # All addresses are valid hex (0x + 40 chars)
        for t in tokens:
            assert t.startswith("0x") and len(t) == 42


def test_curated_tokens_excludes_solana() -> None:
    """Solana uses SPL tokens via base58, not ERC20 — not in scope here."""
    assert Chain.SOLANA not in CURATED_TOKENS


# ─────────────────────────────────────────────────────────────────────────────
# fetch_active_holders — orchestration
# ─────────────────────────────────────────────────────────────────────────────


async def test_fetch_active_holders_no_rpc_url_returns_empty() -> None:
    """Missing both env override and Alchemy key → silent [] return, no raise."""
    env_clean = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("TVL_SCANNER_RPC_")
    }
    with patch.dict(os.environ, env_clean, clear=True):
        with patch("tvl_scanner.discover.rpc.get_secret", return_value=None):
            result = await fetch_active_holders(Chain.BASE, price_cache=PriceCache())
            assert result == []


async def test_fetch_active_holders_solana_returns_empty() -> None:
    """Solana is intentionally out of scope — must short-circuit cleanly."""
    with patch("tvl_scanner.discover.rpc.get_secret", return_value="key"):
        result = await fetch_active_holders(Chain.SOLANA, price_cache=PriceCache())
        assert result == []


async def test_fetch_active_holders_happy_path() -> None:
    """End-to-end: blockNumber → getLogs → recipients → eth_getCode filter →
    balance check → USD price → threshold. We patch _rpc_call directly so this
    test exercises the orchestration without going through httpx."""

    # The "to" addresses we'll see in the Transfer logs
    contract_addr = "0x" + "11" * 20
    eoa_addr = "0x" + "22" * 20
    poor_contract = "0x" + "33" * 20

    # Use the real USDC address from Arbitrum's curated list so _build_coin_key
    # succeeds and our fetch_prices mock receives the expected key
    usdc_arb = "0xaf88d065e77c8cc2239327c5edb3a432268e5831"

    async def mock_rpc(url, method, params, client):
        if method == "eth_blockNumber":
            return "0x64"  # latest = 100
        if method == "eth_getLogs":
            # Return one Transfer-to-contract, one Transfer-to-EOA, one
            # Transfer-to-poor-contract. Each window returns the same list —
            # dedup will collapse them.
            return [
                {
                    "topics": [
                        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                        "0x" + "0" * 24 + "ff" * 20,
                        "0x" + "0" * 24 + contract_addr[2:],
                    ]
                },
                {
                    "topics": [
                        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                        "0x" + "0" * 24 + "ff" * 20,
                        "0x" + "0" * 24 + eoa_addr[2:],
                    ]
                },
                {
                    "topics": [
                        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                        "0x" + "0" * 24 + "ff" * 20,
                        "0x" + "0" * 24 + poor_contract[2:],
                    ]
                },
            ]
        if method == "eth_getCode":
            addr = params[0]
            if addr == eoa_addr:
                return "0x"  # EOA — must be filtered out
            return "0x6080604052"  # contract bytecode (any non-empty value)
        if method == "eth_getBalance":
            addr = params[0]
            if addr == contract_addr:
                return hex(10 * 10**18)  # 10 ETH = $30k native
            return "0x0"
        if method == "eth_call":
            # balanceOf(holder) — calldata is selector + padded holder
            data = params[0]["data"]
            token = params[0]["to"].lower()
            holder_padded = data[10:]  # strip selector
            if token == usdc_arb and holder_padded.endswith(contract_addr[2:]):
                # 150,000 USDC = 150_000 × 10^6 = $150k (passes threshold)
                return hex(150_000 * 10**6)
            if token == usdc_arb and holder_padded.endswith(poor_contract[2:]):
                # 1 USDC = $1 (way below threshold)
                return hex(1 * 10**6)
            return "0x0"
        return None

    async def mock_fetch_prices(keys, *, client=None):
        from tvl_scanner.enrich.defillama_prices import TokenPrice
        return {
            f"arbitrum:{usdc_arb}": TokenPrice(
                symbol="USDC", price=1.0, decimals=6, confidence=0.99
            )
        }

    price_cache = PriceCache()
    price_cache._prices[Chain.ARBITRUM] = 3000.0  # pre-seed ETH price

    with patch.dict(os.environ, {"TVL_SCANNER_RPC_ARBITRUM": "https://rpc.test/"}), patch(
        "tvl_scanner.discover.rpc._rpc_call",
        new=AsyncMock(side_effect=mock_rpc),
    ), patch(
        "tvl_scanner.discover.rpc.fetch_prices",
        new=AsyncMock(side_effect=mock_fetch_prices),
    ), patch(
        "tvl_scanner.discover.rpc._sample_windows",
        return_value=[(50, 100)],  # deterministic single window
    ):
        result = await fetch_active_holders(
            Chain.ARBITRUM,
            price_cache=price_cache,
            sample_windows=1,
            window_blocks=50,
        )

    # Expectations:
    #  - eoa_addr filtered out by eth_getCode == "0x"
    #  - poor_contract: $1 USDC + 0 native = $1, below threshold → dropped
    #  - contract_addr: 150k USDC + (10 ETH × $3000 = $30k) = $180k → kept
    assert len(result) == 1
    record = result[0]
    assert record.address == contract_addr
    assert record.source == DiscoverySource.RPC_ACTIVE_HOLDERS
    assert record.chain == Chain.ARBITRUM
    assert record.tvl_usd == pytest.approx(180_000.0)


async def test_fetch_active_holders_drops_below_threshold() -> None:
    """A contract holding only $50k (below default $100k threshold) must not
    appear in the result list."""
    contract_addr = "0x" + "44" * 20
    base_usdc = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"  # BASE USDC, lowercased

    async def mock_rpc(url, method, params, client):
        if method == "eth_blockNumber":
            return "0x64"
        if method == "eth_getLogs":
            return [
                {
                    "topics": [
                        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                        "0x" + "0" * 24 + "ff" * 20,
                        "0x" + "0" * 24 + contract_addr[2:],
                    ]
                }
            ]
        if method == "eth_getCode":
            return "0x6080604052"
        if method == "eth_getBalance":
            return "0x0"
        if method == "eth_call":
            # Only USDC returns a balance — keeps the test arithmetic simple.
            # All other curated tokens (WETH, DAI, cbETH) return zero.
            token = params[0]["to"].lower()
            if token == base_usdc:
                return hex(50_000 * 10**6)  # 50,000 USDC = $50k
            return "0x0"
        return None

    async def mock_fetch_prices(keys, *, client=None):
        from tvl_scanner.enrich.defillama_prices import TokenPrice
        return {
            f"base:{base_usdc}": TokenPrice(
                symbol="USDC", price=1.0, decimals=6, confidence=0.99
            )
        }

    price_cache = PriceCache()
    price_cache._prices[Chain.BASE] = 3000.0

    with patch.dict(os.environ, {"TVL_SCANNER_RPC_BASE": "https://rpc.test/"}), patch(
        "tvl_scanner.discover.rpc._rpc_call", new=AsyncMock(side_effect=mock_rpc)
    ), patch(
        "tvl_scanner.discover.rpc.fetch_prices",
        new=AsyncMock(side_effect=mock_fetch_prices),
    ), patch(
        "tvl_scanner.discover.rpc._sample_windows",
        return_value=[(50, 100)],
    ):
        result = await fetch_active_holders(
            Chain.BASE,
            price_cache=price_cache,
            sample_windows=1,
            window_blocks=50,
        )

    assert result == []


async def test_fetch_active_holders_no_recipients_short_circuits() -> None:
    """If eth_getLogs returns empty across all sampled windows, the function
    must short-circuit before doing any eth_getCode / balance calls."""
    call_log: list[str] = []

    async def mock_rpc(url, method, params, client):
        call_log.append(method)
        if method == "eth_blockNumber":
            return "0x64"
        if method == "eth_getLogs":
            return []
        return None

    with patch.dict(os.environ, {"TVL_SCANNER_RPC_OPTIMISM": "https://rpc.test/"}), patch(
        "tvl_scanner.discover.rpc._rpc_call", new=AsyncMock(side_effect=mock_rpc)
    ), patch(
        "tvl_scanner.discover.rpc._sample_windows",
        return_value=[(50, 100), (150, 200)],
    ):
        result = await fetch_active_holders(
            Chain.OPTIMISM,
            price_cache=PriceCache(),
            sample_windows=2,
            window_blocks=50,
        )

    assert result == []
    # We expect eth_blockNumber + 2× eth_getLogs, but NO eth_getCode/balance/call
    assert "eth_getCode" not in call_log
    assert "eth_getBalance" not in call_log
    assert "eth_call" not in call_log
