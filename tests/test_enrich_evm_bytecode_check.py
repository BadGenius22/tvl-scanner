"""Tests for the EVM bytecode hash check (Batch J3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from tvl_scanner.enrich.evm_bytecode_check import (
    BytecodePatternEntry,
    check_bytecode_match,
    fetch_contract_code,
    keccak256_hex,
    load_bytecode_registry,
)
from tvl_scanner.models import Chain


def test_keccak_returns_hex_with_0x_prefix() -> None:
    """Whatever hash algorithm we use, the output format must be deterministic."""
    h = keccak256_hex(b"hello")
    assert h.startswith("0x")
    assert len(h) == 66  # 0x + 32 bytes hex
    # Same input → same output
    h2 = keccak256_hex(b"hello")
    assert h == h2


def test_keccak_different_inputs_produce_different_hashes() -> None:
    assert keccak256_hex(b"hello") != keccak256_hex(b"world")


def test_load_bytecode_registry_handles_empty_file() -> None:
    """The seed file is currently empty (no real bytecode hashes registered yet).
    Loader must handle an empty list gracefully and return an empty dict.
    """
    load_bytecode_registry.cache_clear()
    registry = load_bytecode_registry()
    assert isinstance(registry, dict)
    # The current seed file has no entries, so the registry is empty.
    # When entries are added, this test should still pass (just won't be empty).


async def test_check_bytecode_match_empty_registry_returns_none() -> None:
    """With an empty registry, no match is possible regardless of bytecode."""
    load_bytecode_registry.cache_clear()
    with patch(
        "tvl_scanner.enrich.evm_bytecode_check.fetch_contract_code",
        new=AsyncMock(return_value=b"\xff\xfe\xfd"),
    ):
        result = await check_bytecode_match(
            Chain.ARBITRUM, "0xABCdef1234567890abcdef1234567890abcdef12"
        )
    assert result is None


async def test_check_bytecode_match_with_seeded_registry() -> None:
    """If we manually seed the registry and provide matching bytecode,
    check_bytecode_match should return the entry.
    """
    load_bytecode_registry.cache_clear()
    fake_bytecode = b"\xde\xad\xbe\xef"
    expected_hash = keccak256_hex(fake_bytecode)

    fake_entry = BytecodePatternEntry(
        bytecode_hash=expected_hash,
        name="Test Pool",
        upstream_protocol="test-dex",
        audit_count=5,
        audit_url="https://example.com/audit.pdf",
    )

    # Patch the registry loader to return our fake entry
    with patch(
        "tvl_scanner.enrich.evm_bytecode_check.load_bytecode_registry",
        return_value={expected_hash: fake_entry},
    ), patch(
        "tvl_scanner.enrich.evm_bytecode_check.fetch_contract_code",
        new=AsyncMock(return_value=fake_bytecode),
    ):
        result = await check_bytecode_match(
            Chain.ARBITRUM, "0xABCdef1234567890abcdef1234567890abcdef12"
        )
    assert result is not None
    assert result.entry.upstream_protocol == "test-dex"
    assert result.entry.audit_count == 5


async def test_check_bytecode_match_no_code_returns_none() -> None:
    """fetch_contract_code returns None for EOAs / no Alchemy key. Must not crash."""
    load_bytecode_registry.cache_clear()
    with patch(
        "tvl_scanner.enrich.evm_bytecode_check.fetch_contract_code",
        new=AsyncMock(return_value=None),
    ):
        result = await check_bytecode_match(
            Chain.ARBITRUM, "0xABCdef1234567890abcdef1234567890abcdef12"
        )
    assert result is None


async def test_fetch_contract_code_no_alchemy_key_returns_none() -> None:
    with patch("tvl_scanner.enrich.evm_bytecode_check.get_secret", return_value=None):
        result = await fetch_contract_code(
            Chain.ARBITRUM, "0xABCdef1234567890abcdef1234567890abcdef12"
        )
    assert result is None


async def test_fetch_contract_code_solana_chain_returns_none() -> None:
    """Solana isn't in CHAIN_TO_ALCHEMY_SUBDOMAIN — returns None without RPC."""
    with patch("tvl_scanner.enrich.evm_bytecode_check.get_secret", return_value="test-key"):
        result = await fetch_contract_code(Chain.SOLANA, "SoLanaAddr111")
    assert result is None
