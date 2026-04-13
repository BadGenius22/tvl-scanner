"""Tests for OtterSec reproducible-build verification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.ottersec import (
    _is_solana_program_id,
    _parse_ottersec_response,
    check_ottersec_verification,
)

FIXTURES = Path(__file__).parent / "fixtures"

# Valid Solana program IDs for testing (real-looking base58 strings)
JITO_PROGRAM = "Jito4APyf642JPZPx3hGc6WWJ8zPKtRbRs4P815Awbb"
DRIFT_PROGRAM = "dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH"
SHORT_INVALID = "tooshort"
EVM_ADDR = "0xABCdef1234567890abcdef1234567890abcdef12"
SYNTHETIC_ADDR = "defillama:jito-liquid-staking"


@pytest.fixture
def verified() -> dict:
    return json.loads((FIXTURES / "ottersec_verified.json").read_text())


@pytest.fixture
def unverified() -> dict:
    return json.loads((FIXTURES / "ottersec_unverified.json").read_text())


# ---- Address validator ----


def test_is_solana_program_id_accepts_real_base58() -> None:
    assert _is_solana_program_id(JITO_PROGRAM)
    assert _is_solana_program_id(DRIFT_PROGRAM)


def test_is_solana_program_id_rejects_evm() -> None:
    assert not _is_solana_program_id(EVM_ADDR)


def test_is_solana_program_id_rejects_synthetic() -> None:
    assert not _is_solana_program_id(SYNTHETIC_ADDR)


def test_is_solana_program_id_rejects_too_short() -> None:
    assert not _is_solana_program_id(SHORT_INVALID)
    assert not _is_solana_program_id("")


def test_is_solana_program_id_rejects_too_long() -> None:
    assert not _is_solana_program_id("a" * 50)


def test_is_solana_program_id_rejects_invalid_base58_chars() -> None:
    # 0, O, I, l are not in the base58 alphabet
    assert not _is_solana_program_id("1111111111111111111111111111110l")
    assert not _is_solana_program_id("0123456789012345678901234567890O")


# ---- Parser unit tests ----


def test_parse_verified_response() -> None:
    payload = {
        "is_verified": True,
        "commit": "abc123def456789abcdef0123456789abcdef012",
        "repo_url": "https://github.com/foo/bar",
        "signer": "xyz",
    }
    result = _parse_ottersec_response(payload)
    assert result.is_verified is True
    assert result.compiler_version == "solana-verify@abc123def456"
    assert result.is_proxy is False
    assert result.contract_name is None


def test_parse_unverified_response() -> None:
    payload = {"is_verified": False, "message": "not found"}
    result = _parse_ottersec_response(payload)
    assert result.is_verified is False
    assert result.compiler_version is None


def test_parse_verified_without_commit() -> None:
    """Edge case: is_verified=True but commit is missing. Shouldn't crash."""
    payload = {"is_verified": True}
    result = _parse_ottersec_response(payload)
    assert result.is_verified is True
    assert result.compiler_version == "solana-verify"  # no commit suffix


def test_parse_missing_is_verified_treated_as_false() -> None:
    """is_verified not present in response → default to False."""
    result = _parse_ottersec_response({"message": "unknown"})
    assert result.is_verified is False


# ---- Live HTTP path tests ----


async def test_check_ottersec_verified(
    httpx_mock: HTTPXMock, verified: dict
) -> None:
    httpx_mock.add_response(
        url=f"https://verify.osec.io/status/{JITO_PROGRAM}",
        json=verified,
    )
    result = await check_ottersec_verification(JITO_PROGRAM)
    assert result.is_verified is True
    # commit[:12] = "abc123def456"
    assert result.compiler_version == "solana-verify@abc123def456"


async def test_check_ottersec_unverified(
    httpx_mock: HTTPXMock, unverified: dict
) -> None:
    httpx_mock.add_response(
        url=f"https://verify.osec.io/status/{DRIFT_PROGRAM}",
        json=unverified,
    )
    result = await check_ottersec_verification(DRIFT_PROGRAM)
    assert result.is_verified is False


async def test_check_ottersec_skips_evm_address() -> None:
    """EVM addresses must not generate HTTP calls against OtterSec."""
    # Not using httpx_mock — if the function makes a call, it'll fail loudly
    result = await check_ottersec_verification(EVM_ADDR)
    assert result.is_verified is False


async def test_check_ottersec_skips_synthetic_address() -> None:
    """Synthetic `defillama:<slug>` addresses must not hit OtterSec."""
    result = await check_ottersec_verification(SYNTHETIC_ADDR)
    assert result.is_verified is False


async def test_check_ottersec_http_404_returns_empty(httpx_mock: HTTPXMock) -> None:
    """OtterSec returns 404 for programs that were never submitted. Normal case."""
    httpx_mock.add_response(
        url=f"https://verify.osec.io/status/{JITO_PROGRAM}",
        status_code=404,
        json={"error": "not found"},
        is_reusable=True,
    )
    result = await check_ottersec_verification(JITO_PROGRAM)
    assert result.is_verified is False


async def test_check_ottersec_http_5xx_returns_empty(httpx_mock: HTTPXMock) -> None:
    """Upstream outage should degrade to empty, not raise."""
    httpx_mock.add_response(
        url=f"https://verify.osec.io/status/{JITO_PROGRAM}",
        status_code=503,
        text="upstream unavailable",
        is_reusable=True,
    )
    result = await check_ottersec_verification(JITO_PROGRAM)
    assert result.is_verified is False


async def test_check_ottersec_non_dict_payload_returns_empty(
    httpx_mock: HTTPXMock,
) -> None:
    """If OtterSec returns an unexpected type (list, string) we degrade."""
    httpx_mock.add_response(
        url=f"https://verify.osec.io/status/{JITO_PROGRAM}",
        json=["unexpected", "list", "response"],
    )
    result = await check_ottersec_verification(JITO_PROGRAM)
    assert result.is_verified is False
