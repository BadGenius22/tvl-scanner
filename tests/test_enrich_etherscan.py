"""Tests for Etherscan V2 verification enrichment."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.etherscan import (
    CHAIN_TO_ETHERSCAN_ID,
    _is_evm_address,
    _parse_etherscan_result,
    check_verification,
)
from tvl_scanner.models import Chain

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def verified() -> dict:
    return json.loads((FIXTURES / "etherscan_verified.json").read_text())


@pytest.fixture
def unverified() -> dict:
    return json.loads((FIXTURES / "etherscan_unverified.json").read_text())


@pytest.fixture
def proxy() -> dict:
    return json.loads((FIXTURES / "etherscan_proxy.json").read_text())


# ---- Address validator ----


def test_is_evm_address_valid_checksum() -> None:
    assert _is_evm_address("0xABCdef1234567890abcdef1234567890abcdef12")
    assert _is_evm_address("0x0000000000000000000000000000000000000000")


def test_is_evm_address_rejects_solana() -> None:
    assert not _is_evm_address("SoLbIrd1eYePaIrAdDrEsS000000000000000000001")


def test_is_evm_address_rejects_synthetic_defillama() -> None:
    assert not _is_evm_address("defillama:aave-v3")


def test_is_evm_address_rejects_wrong_length() -> None:
    assert not _is_evm_address("0xABC")
    assert not _is_evm_address("0x" + "a" * 41)  # 41 chars after 0x, total 43


# ---- Parser unit tests ----


def test_parse_verified_result() -> None:
    item = {
        "SourceCode": "contract Foo {}",
        "ContractName": "Foo",
        "CompilerVersion": "v0.8.20+commit.a1b79de6",
        "Proxy": "0",
        "Implementation": "",
    }
    result = _parse_etherscan_result(item)
    assert result.is_verified is True
    assert result.contract_name == "Foo"
    assert result.compiler_version == "v0.8.20+commit.a1b79de6"
    assert result.is_proxy is False
    assert result.proxy_impl_address is None


def test_parse_unverified_result() -> None:
    """Unverified: empty SourceCode and empty ContractName."""
    item = {
        "SourceCode": "",
        "ContractName": "",
        "CompilerVersion": "",
        "Proxy": "0",
        "Implementation": "",
    }
    result = _parse_etherscan_result(item)
    assert result.is_verified is False
    assert result.contract_name is None


def test_parse_proxy_with_implementation() -> None:
    item = {
        "SourceCode": "contract Proxy {}",
        "ContractName": "TransparentUpgradeableProxy",
        "CompilerVersion": "v0.8.20",
        "Proxy": "1",
        "Implementation": "0xDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF",
    }
    result = _parse_etherscan_result(item)
    assert result.is_verified is True
    assert result.is_proxy is True
    assert result.proxy_impl_address == "0xDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF"


def test_parse_proxy_with_zero_impl() -> None:
    """Proxy=1 but Implementation=0x00...0 means slot is unset — not a usable impl."""
    item = {
        "SourceCode": "contract Proxy {}",
        "ContractName": "UninitializedProxy",
        "CompilerVersion": "v0.8.20",
        "Proxy": "1",
        "Implementation": "0x0000000000000000000000000000000000000000",
    }
    result = _parse_etherscan_result(item)
    assert result.is_proxy is True
    assert result.proxy_impl_address is None


# ---- Live HTTP path tests ----


async def test_check_verification_happy_path_verified(
    httpx_mock: HTTPXMock, verified: dict
) -> None:
    httpx_mock.add_response(
        url="https://api.etherscan.io/v2/api?chainid=42161&module=contract&action=getsourcecode&address=0xABCdef1234567890abcdef1234567890abcdef12&apikey=test-key",
        json=verified,
    )
    with patch("tvl_scanner.enrich.etherscan.get_secret", return_value="test-key"):
        result = await check_verification(
            Chain.ARBITRUM, "0xABCdef1234567890abcdef1234567890abcdef12"
        )
    assert result.is_verified is True
    assert result.contract_name == "FooVault"
    assert result.compiler_version == "v0.8.20+commit.a1b79de6"
    assert result.is_proxy is False


async def test_check_verification_unverified(
    httpx_mock: HTTPXMock, unverified: dict
) -> None:
    httpx_mock.add_response(
        url="https://api.etherscan.io/v2/api?chainid=8453&module=contract&action=getsourcecode&address=0xABCdef1234567890abcdef1234567890abcdef12&apikey=test-key",
        json=unverified,
    )
    with patch("tvl_scanner.enrich.etherscan.get_secret", return_value="test-key"):
        result = await check_verification(
            Chain.BASE, "0xABCdef1234567890abcdef1234567890abcdef12"
        )
    assert result.is_verified is False
    assert result.contract_name is None


async def test_check_verification_proxy(httpx_mock: HTTPXMock, proxy: dict) -> None:
    httpx_mock.add_response(
        url="https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getsourcecode&address=0xABCdef1234567890abcdef1234567890abcdef12&apikey=test-key",
        json=proxy,
    )
    with patch("tvl_scanner.enrich.etherscan.get_secret", return_value="test-key"):
        result = await check_verification(
            Chain.ETHEREUM, "0xABCdef1234567890abcdef1234567890abcdef12"
        )
    assert result.is_verified is True
    assert result.is_proxy is True
    assert result.proxy_impl_address == "0xDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF"


async def test_check_verification_skips_solana() -> None:
    """Solana records have non-EVM addresses — should return empty without HTTP."""
    with patch("tvl_scanner.enrich.etherscan.get_secret", return_value="test-key"):
        result = await check_verification(
            Chain.SOLANA, "SoLbIrd1eYePaIrAdDrEsS000000000000000000001"
        )
    assert result.is_verified is False


async def test_check_verification_skips_synthetic_defillama_address() -> None:
    """Catalog-sourced records with `defillama:slug` addresses should not hit Etherscan."""
    with patch("tvl_scanner.enrich.etherscan.get_secret", return_value="test-key"):
        result = await check_verification(Chain.ARBITRUM, "defillama:aave-v3")
    assert result.is_verified is False


async def test_check_verification_no_key_returns_empty() -> None:
    """Missing API key should degrade silently, not raise."""
    with patch("tvl_scanner.enrich.etherscan.get_secret", return_value=None):
        result = await check_verification(
            Chain.ARBITRUM, "0xABCdef1234567890abcdef1234567890abcdef12"
        )
    assert result.is_verified is False


async def test_check_verification_http_error_returns_empty(httpx_mock: HTTPXMock) -> None:
    """A persistent upstream 500 should degrade to is_verified=False, not raise."""
    httpx_mock.add_response(
        url="https://api.etherscan.io/v2/api?chainid=42161&module=contract&action=getsourcecode&address=0xABCdef1234567890abcdef1234567890abcdef12&apikey=test-key",
        status_code=500,
        text="upstream error",
        is_reusable=True,
    )
    with patch("tvl_scanner.enrich.etherscan.get_secret", return_value="test-key"):
        result = await check_verification(
            Chain.ARBITRUM, "0xABCdef1234567890abcdef1234567890abcdef12"
        )
    assert result.is_verified is False


async def test_check_verification_status_not_ok_returns_empty(
    httpx_mock: HTTPXMock,
) -> None:
    """status!='1' (e.g. NOTOK) should yield empty VerificationResult.

    Batch N.8: check_verification now retries once on NOTOK (Etherscan
    rate-limiting comes back as HTTP 200 with status=0, not a 429, so http.py's
    retry doesn't catch it). The mock needs to be reusable to satisfy both
    calls.
    """
    httpx_mock.add_response(
        url="https://api.etherscan.io/v2/api?chainid=42161&module=contract&action=getsourcecode&address=0xABCdef1234567890abcdef1234567890abcdef12&apikey=test-key",
        json={"status": "0", "message": "NOTOK", "result": "Invalid address"},
        is_reusable=True,
    )
    with patch("tvl_scanner.enrich.etherscan.get_secret", return_value="test-key"):
        result = await check_verification(
            Chain.ARBITRUM, "0xABCdef1234567890abcdef1234567890abcdef12"
        )
    assert result.is_verified is False


def test_chain_coverage_has_all_main_evm() -> None:
    """Make sure all configured EVM chains have an Etherscan V2 chainid."""
    for chain in (
        Chain.ETHEREUM,
        Chain.ARBITRUM,
        Chain.BASE,
        Chain.OPTIMISM,
        Chain.POLYGON,
        Chain.BSC,
    ):
        assert chain in CHAIN_TO_ETHERSCAN_ID
    # Solana should NOT be in the mapping
    assert Chain.SOLANA not in CHAIN_TO_ETHERSCAN_ID
