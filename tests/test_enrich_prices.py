"""Tests for the native-token USD price cache."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.prices import FALLBACK_USD, PriceCache
from tvl_scanner.models import Chain


async def test_price_cache_fetches_eth_from_coingecko(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
        json={"ethereum": {"usd": 3421.55}},
    )
    cache = PriceCache()
    price = await cache.get(Chain.ETHEREUM)
    assert price == pytest.approx(3421.55)


async def test_price_cache_shares_eth_across_l2s(httpx_mock: HTTPXMock) -> None:
    """Once ETH is fetched for Ethereum, Arbitrum/Base/Optimism should hit cache."""
    httpx_mock.add_response(
        url="https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
        json={"ethereum": {"usd": 3500.00}},
    )
    cache = PriceCache()
    await cache.get(Chain.ETHEREUM)  # first call populates all ETH L2s
    # Next calls must NOT make HTTP — httpx_mock would fail the test if they did
    assert await cache.get(Chain.ARBITRUM) == 3500.00
    assert await cache.get(Chain.BASE) == 3500.00
    assert await cache.get(Chain.OPTIMISM) == 3500.00


async def test_price_cache_falls_back_on_http_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
        status_code=429,
        text="rate limited",
        is_reusable=True,
    )
    cache = PriceCache()
    price = await cache.get(Chain.ETHEREUM)
    assert price == FALLBACK_USD[Chain.ETHEREUM]


async def test_price_cache_falls_back_on_missing_field(httpx_mock: HTTPXMock) -> None:
    """Coingecko returns payload with missing 'usd' field → use fallback."""
    httpx_mock.add_response(
        url="https://api.coingecko.com/api/v3/simple/price?ids=matic-network&vs_currencies=usd",
        json={"matic-network": {}},
    )
    cache = PriceCache()
    price = await cache.get(Chain.POLYGON)
    assert price == FALLBACK_USD[Chain.POLYGON]


async def test_price_cache_does_not_refetch_within_scan(httpx_mock: HTTPXMock) -> None:
    """Second lookup of the same chain should not hit HTTP again."""
    httpx_mock.add_response(
        url="https://api.coingecko.com/api/v3/simple/price?ids=binancecoin&vs_currencies=usd",
        json={"binancecoin": {"usd": 520.0}},
    )
    cache = PriceCache()
    p1 = await cache.get(Chain.BSC)
    p2 = await cache.get(Chain.BSC)
    assert p1 == p2 == 520.0
