"""Tests for Solana wrapper-program detection (Batch J1) and on-chain LST TVL
sanity check (Batch J2).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tvl_scanner.enrich.solana_wrapper_check import (
    LstRegistryEntry,
    WrapperMatch,
    WrapperProgramEntry,
    check_lst_wrapper,
    check_wrapper_program,
    compute_on_chain_lst_tvl,
    fetch_lst_supply,
    load_lst_mint_registry,
    load_wrapper_registry,
)


def test_load_wrapper_registry_includes_spl_stake_pool() -> None:
    """The registry must contain the SPL stake pool program — that's the
    primary Batch J1 use case (JagPool detection).
    """
    load_wrapper_registry.cache_clear()
    registry = load_wrapper_registry()
    assert "SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy" in registry
    spl = registry["SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy"]
    assert spl.audit_count >= 1
    assert "stake pool" in spl.name.lower()


def test_load_lst_mint_registry_includes_jagpool() -> None:
    """JagPool must be in the LST mint registry — it's the canonical false-
    positive example we're protecting against.
    """
    load_lst_mint_registry.cache_clear()
    registry = load_lst_mint_registry()
    assert "jagpool-staked-sol" in registry
    entry = registry["jagpool-staked-sol"]
    assert entry.mint == "jag7A2z4QNacNi61AXpyRiyUppx5GeLbGEKAapuKCRs"
    assert entry.stake_pool == "jagPCXWPBwoah9K4PxzHoh8z7aSru4Vbxq7GKUeEzgY"


async def test_check_wrapper_program_skips_synthetic_addresses() -> None:
    """defillama: prefix and 0x prefix should short-circuit without HTTP."""
    result = await check_wrapper_program("defillama:jagpool-staked-sol")
    assert result is None
    result = await check_wrapper_program("0xABCdef1234567890abcdef1234567890abcdef12")
    assert result is None
    result = await check_wrapper_program("")
    assert result is None


async def test_check_wrapper_program_owner_match_returns_match() -> None:
    """If RPC returns an owner that's in the registry, build a WrapperMatch."""
    fake_rpc_response = {
        "value": {
            "owner": "SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy",
            "lamports": 5143440,
            "executable": False,
        }
    }
    with patch(
        "tvl_scanner.enrich.solana_wrapper_check._rpc",
        new=AsyncMock(return_value=fake_rpc_response),
    ):
        result = await check_wrapper_program("jagPCXWPBwoah9K4PxzHoh8z7aSru4Vbxq7GKUeEzgY")
    assert result is not None
    assert result.account_owner == "SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy"
    assert "stake pool" in result.entry.name.lower()


async def test_check_wrapper_program_unknown_owner_returns_none() -> None:
    """An owner not in the registry should yield None (a custom protocol)."""
    fake_rpc_response = {
        "value": {"owner": "SomeRandomProgram111111111111111111111111111"}
    }
    with patch(
        "tvl_scanner.enrich.solana_wrapper_check._rpc",
        new=AsyncMock(return_value=fake_rpc_response),
    ):
        result = await check_wrapper_program("SomeRealAccount111111111111111111111111111")
    assert result is None


async def test_fetch_lst_supply_parses_ui_amount() -> None:
    fake_response = {"value": {"uiAmount": 0.109421433, "decimals": 9}}
    with patch(
        "tvl_scanner.enrich.solana_wrapper_check._rpc",
        new=AsyncMock(return_value=fake_response),
    ):
        supply = await fetch_lst_supply("jag7A2z4QNacNi61AXpyRiyUppx5GeLbGEKAapuKCRs")
    assert supply == pytest.approx(0.109421433)


async def test_compute_on_chain_lst_tvl_uses_real_supply() -> None:
    """Verifies the JagPool-style TVL discrepancy detection."""
    load_lst_mint_registry.cache_clear()
    fake_response = {"value": {"uiAmount": 0.109, "decimals": 9}}
    with patch(
        "tvl_scanner.enrich.solana_wrapper_check._rpc",
        new=AsyncMock(return_value=fake_response),
    ):
        tvl = await compute_on_chain_lst_tvl("jagpool-staked-sol", native_token_usd=150.0)
    # 0.109 SOL × $150 ≈ $16.35
    assert tvl == pytest.approx(0.109 * 150.0, abs=0.01)


async def test_compute_on_chain_lst_tvl_unknown_slug_returns_none() -> None:
    load_lst_mint_registry.cache_clear()
    tvl = await compute_on_chain_lst_tvl("not-a-real-protocol", native_token_usd=150.0)
    assert tvl is None


async def test_check_lst_wrapper_resolves_via_stake_pool_address() -> None:
    """The bridge from slug → stake pool address → wrapper match."""
    load_lst_mint_registry.cache_clear()
    fake_response = {
        "value": {"owner": "SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy"}
    }
    with patch(
        "tvl_scanner.enrich.solana_wrapper_check._rpc",
        new=AsyncMock(return_value=fake_response),
    ):
        result = await check_lst_wrapper("jagpool-staked-sol")
    assert result is not None
    assert "stake pool" in result.entry.name.lower()


async def test_check_lst_wrapper_unknown_slug_returns_none() -> None:
    load_lst_mint_registry.cache_clear()
    result = await check_lst_wrapper("totally-unknown-protocol-xyz")
    assert result is None
