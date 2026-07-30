"""On-chain TVL measurement — the fallback for when DefiLlama has no figure."""

from __future__ import annotations

import pytest

from tvl_scanner.enrich.onchain_tvl import (
    SWEEP_SANITY_CAP_USD,
    _to_address,
    _to_int,
    measure_onchain_tvl,
)
from tvl_scanner.models import Chain

VAULT = "0x1111111111111111111111111111111111111111"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


def _word(value: int) -> str:
    return "0x" + f"{value:064x}"


def test_to_int_and_to_address_reject_junk() -> None:
    assert _to_int(_word(1234)) == 1234
    assert _to_int("0x") is None
    assert _to_int(None) is None
    assert _to_int("not-hex") is None
    assert _to_address(_word(int(USDC, 16))).lower() == USDC.lower()
    # The zero address means "not implemented", not a real token.
    assert _to_address(_word(0)) is None


async def test_solana_is_never_attempted() -> None:
    """A Solana program owns no balances; a fabricated number is worse than None."""
    assert await measure_onchain_tvl(Chain.SOLANA, ["SomeProgram1111"]) is None


async def test_no_addresses_returns_none() -> None:
    assert await measure_onchain_tvl(Chain.ETHEREUM, []) is None


async def test_erc4626_total_assets_priced(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier 1: totalAssets() x asset() price. 250 USDC of 6-decimal units."""
    monkeypatch.setattr(
        "tvl_scanner.enrich.onchain_tvl._alchemy_url", lambda chain: "https://rpc.test"
    )

    async def fake_post(url, *, json_body, headers=None, client=None):
        data = json_body["params"][0]["data"]
        if data == "0x01e1d114":  # totalAssets()
            return {"result": _word(250_000_000)}
        if data == "0x38d52e0f":  # asset()
            return {"result": _word(int(USDC, 16))}
        return {"result": "0x"}

    async def fake_get(url, *, client=None, **kw):
        return {
            "coins": {
                f"ethereum:{USDC}": {"price": 1.0, "decimals": 6, "confidence": 0.99}
            }
        }

    monkeypatch.setattr("tvl_scanner.enrich.onchain_tvl.post_json", fake_post)
    monkeypatch.setattr("tvl_scanner.enrich.onchain_tvl.get_json", fake_get)

    result = await measure_onchain_tvl(Chain.ETHEREUM, [VAULT])
    assert result is not None
    value, note = result
    assert value == pytest.approx(250.0)
    assert "erc4626" in note


async def test_low_confidence_price_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spam tokens carry a low DefiLlama confidence — they must not inflate TVL."""
    monkeypatch.setattr(
        "tvl_scanner.enrich.onchain_tvl._alchemy_url", lambda chain: "https://rpc.test"
    )

    async def fake_post(url, *, json_body, headers=None, client=None):
        data = json_body["params"][0]["data"]
        if data == "0x01e1d114":
            return {"result": _word(10**30)}
        if data == "0x38d52e0f":
            return {"result": _word(int(USDC, 16))}
        return {"result": "0x"}

    async def fake_get(url, *, client=None, **kw):
        return {
            "coins": {
                f"ethereum:{USDC}": {"price": 1.0, "decimals": 6, "confidence": 0.10}
            }
        }

    monkeypatch.setattr("tvl_scanner.enrich.onchain_tvl.post_json", fake_post)
    monkeypatch.setattr("tvl_scanner.enrich.onchain_tvl.get_json", fake_get)

    assert await measure_onchain_tvl(Chain.ETHEREUM, [VAULT]) is None


def test_sweep_sanity_cap_is_set() -> None:
    """A balance sweep over junk tokens must have an upper bound."""
    assert SWEEP_SANITY_CAP_USD > 0
