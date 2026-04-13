"""Tests for Birdeye pair/pool discovery."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.discover.birdeye import fetch_top_pairs
from tvl_scanner.models import Chain, DiscoverySource

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def birdeye_solana() -> dict:
    return json.loads((FIXTURES / "birdeye_solana.json").read_text())


async def test_fetch_top_pairs_no_api_key_returns_empty() -> None:
    """Birdeye is optional — missing API key should silently return []."""
    with patch("tvl_scanner.discover.birdeye.get_secret", return_value=None):
        result = await fetch_top_pairs(Chain.SOLANA)
        assert result == []


BIRDEYE_URL = "https://public-api.birdeye.so/defi/v2/tokens/new_listing?limit=20"


async def test_fetch_top_pairs_parses_string_iso_date(
    httpx_mock: HTTPXMock, birdeye_solana: dict
) -> None:
    """Items with an ISO-8601 `created_at` string should parse correctly."""
    httpx_mock.add_response(url=BIRDEYE_URL, json=birdeye_solana)
    with patch("tvl_scanner.discover.birdeye.get_secret", return_value="test-key"):
        results = await fetch_top_pairs(Chain.SOLANA)

    # Fixture has 3 items: $425k (kept, iso date), $12k (dropped <100k),
    # $890k (kept, unix ts). Expect 2 survivors.
    assert len(results) == 2
    kept = {r.address: r for r in results}
    assert "SoLbIrd1eYePaIrAdDrEsS000000000000000000001" in kept
    assert "SoLbIrd1eYePaIrAdDrEsS000000000000000000003" in kept
    first = kept["SoLbIrd1eYePaIrAdDrEsS000000000000000000001"]
    assert first.tvl_usd == 425000.75
    assert first.source == DiscoverySource.BIRDEYE
    assert first.protocol_guess == "raydium"
    assert first.first_seen.isoformat() == "2026-02-10"


async def test_fetch_top_pairs_parses_unix_timestamp(
    httpx_mock: HTTPXMock, birdeye_solana: dict
) -> None:
    """Unix-timestamp `created_at` should also parse — Birdeye uses both forms."""
    httpx_mock.add_response(url=BIRDEYE_URL, json=birdeye_solana)
    with patch("tvl_scanner.discover.birdeye.get_secret", return_value="test-key"):
        results = await fetch_top_pairs(Chain.SOLANA)

    ts_record = next(
        r for r in results if r.address == "SoLbIrd1eYePaIrAdDrEsS000000000000000000003"
    )
    assert ts_record.first_seen.year == 2025
    assert ts_record.tvl_usd == 890000.0


async def test_fetch_top_pairs_http_failure_returns_empty(httpx_mock: HTTPXMock) -> None:
    """A persistent upstream failure should degrade to [], not raise."""
    httpx_mock.add_response(
        url=BIRDEYE_URL,
        status_code=500,
        text="internal error",
        is_reusable=True,
    )
    with patch("tvl_scanner.discover.birdeye.get_secret", return_value="test-key"):
        results = await fetch_top_pairs(Chain.SOLANA)
        assert results == []


async def test_fetch_top_pairs_unsupported_chain_no_request() -> None:
    """Unsupported chain should not make any HTTP call."""
    from tvl_scanner.discover import birdeye as be_mod

    original = be_mod.CHAIN_TO_BIRDEYE.copy()
    try:
        be_mod.CHAIN_TO_BIRDEYE.pop(Chain.OPTIMISM, None)
        with patch("tvl_scanner.discover.birdeye.get_secret", return_value="test-key"):
            result = await fetch_top_pairs(Chain.OPTIMISM)
            assert result == []
    finally:
        be_mod.CHAIN_TO_BIRDEYE.update(original)
