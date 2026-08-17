"""Tests for the DefiLlama catalog cache and name matcher."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.defillama import DefiLlamaCatalog, _slugify

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def dl_sample() -> list[dict]:
    return json.loads((FIXTURES / "defillama_protocols_sample.json").read_text())


def test_slugify_normalizes_punctuation_and_case() -> None:
    assert _slugify("Camelot V3") == "camelot-v3"
    assert _slugify("Uniswap V3") == "uniswap-v3"
    assert _slugify("  Factor.Finance  ") == "factor-finance"
    assert _slugify("SushiSwap") == "sushiswap"


async def test_catalog_load_populates(
    httpx_mock: HTTPXMock, dl_sample: list[dict]
) -> None:
    httpx_mock.add_response(url="https://api.llama.fi/protocols", json=dl_sample)
    catalog = DefiLlamaCatalog()
    assert not catalog.is_loaded()
    await catalog.load()
    assert catalog.is_loaded()


async def test_catalog_lookup_exact_slug(
    httpx_mock: HTTPXMock, dl_sample: list[dict]
) -> None:
    httpx_mock.add_response(url="https://api.llama.fi/protocols", json=dl_sample)
    catalog = DefiLlamaCatalog()
    await catalog.load()

    match = catalog.lookup("Camelot V3")
    assert match is not None
    assert match["slug"] == "camelot-v3"
    assert match["category"] == "Dexes"


async def test_catalog_lookup_substring_name(
    httpx_mock: HTTPXMock, dl_sample: list[dict]
) -> None:
    """A partial match like 'factor' should still find 'Factor Finance'."""
    httpx_mock.add_response(url="https://api.llama.fi/protocols", json=dl_sample)
    catalog = DefiLlamaCatalog()
    await catalog.load()

    match = catalog.lookup("factor")
    assert match is not None
    assert match["slug"] == "factor"


async def test_catalog_lookup_miss_returns_none(
    httpx_mock: HTTPXMock, dl_sample: list[dict]
) -> None:
    """No match → None. This is the 'potentially under-audited' signal."""
    httpx_mock.add_response(url="https://api.llama.fi/protocols", json=dl_sample)
    catalog = DefiLlamaCatalog()
    await catalog.load()

    assert catalog.lookup("some-random-unknown-protocol") is None
    assert catalog.lookup("") is None


async def test_catalog_handles_fetch_failure_gracefully(httpx_mock: HTTPXMock) -> None:
    """Upstream failure should leave catalog loaded-but-empty, not raise."""
    httpx_mock.add_response(
        url="https://api.llama.fi/protocols",
        status_code=503,
        text="service unavailable",
        is_reusable=True,
    )
    catalog = DefiLlamaCatalog()
    await catalog.load()
    assert catalog.is_loaded()
    assert catalog.lookup("uniswap") is None


def test_lookup_prefers_the_row_on_the_requested_chain() -> None:
    """Two protocols share a name; the Immunefi scope chain must win."""
    catalog = DefiLlamaCatalog()
    catalog._loaded = True
    catalog._protocols = [
        {
            "slug": "katana-sol",
            "name": "Katana",
            "chains": ["Solana"],
            "chainTvls": {"Solana": 1_446_469.0},
            "tvl": 1_446_469.0,
        },
        {
            "slug": "katana",
            "name": "Katana",
            "chains": ["Ethereum"],
            "chainTvls": {"Ethereum": 1_500_000.0},
            "tvl": 1_500_000.0,
        },
    ]
    from tvl_scanner.models import Chain

    match = catalog.lookup("Katana", prefer_chain=Chain.ETHEREUM)
    assert match is not None
    assert match["slug"] == "katana"


def test_lookup_drops_weak_hits_on_the_wrong_chain() -> None:
    """Prefix match to a different-chain leftover must not bind.

    TruYields (Solana) used to inherit trufin-legacy-vaults ($7 on Ethereum)
    via slug prefix `trufin`, which then scored as a 400,000% payout ratio.
    """
    catalog = DefiLlamaCatalog()
    catalog._loaded = True
    catalog._protocols = [
        {
            "slug": "trufin-legacy-vaults",
            "name": "TruFin Legacy Vaults",
            "chains": ["Ethereum"],
            "chainTvls": {"Ethereum": 7.0},
            "tvl": 7.0,
        }
    ]
    from tvl_scanner.models import Chain

    assert catalog.lookup("trufin", prefer_chain=Chain.SOLANA) is None
    # Without a chain hint the prefix still matches (pool-path discovery).
    assert catalog.lookup("trufin")["slug"] == "trufin-legacy-vaults"
