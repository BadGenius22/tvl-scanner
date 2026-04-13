"""Etherscan V2 verification enrichment.

Etherscan V2 (2024+) is a **unified API across all supported EVM chains** via
a `chainid` query parameter. One API key works for:

    Ethereum (1), Optimism (10), BSC (56), Polygon (137), Base (8453),
    Arbitrum (42161), and ~50 other L1s / L2s.

Endpoint: https://api.etherscan.io/v2/api

This module:
  1. Given an EVM candidate with a primary contract address, calls
     `getsourcecode` to fetch verification status, contract name, compiler
     version, and proxy metadata.
  2. Detects EIP-1967 proxies by inspecting the returned `Proxy` + `Implementation`
     fields, which Etherscan populates when the storage slot is set.
  3. Returns a structured result that the enricher folds into EnrichedCandidate.

Rate limit: free tier is 5 req/s, 100k req/day. One call per candidate per
scan = well under bound.

Solana records are not Etherscan-addressable and are skipped entirely.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from tvl_scanner.config import get_secret, settings
from tvl_scanner.http import HttpError, get_json
from tvl_scanner.models import Chain

log = logging.getLogger(__name__)


# Etherscan V2 chain IDs for the chains we care about. Solana is intentionally
# absent — Solana has its own explorer (Solscan, solana.fm) with a different API.
CHAIN_TO_ETHERSCAN_ID: dict[Chain, int] = {
    Chain.ETHEREUM: 1,
    Chain.OPTIMISM: 10,
    Chain.BSC: 56,
    Chain.POLYGON: 137,
    Chain.BASE: 8453,
    Chain.ARBITRUM: 42161,
}


@dataclass
class VerificationResult:
    """Parsed response from Etherscan V2 getsourcecode."""

    is_verified: bool
    contract_name: str | None = None
    compiler_version: str | None = None
    is_proxy: bool = False
    proxy_impl_address: str | None = None


_EMPTY_NOT_VERIFIED = VerificationResult(is_verified=False)


def _is_evm_address(address: str) -> bool:
    """Rough EVM address check. Synthetic `defillama:<slug>` addresses fail this."""
    return (
        address.startswith("0x")
        and len(address) == 42
        and all(c in "0123456789abcdefABCDEF" for c in address[2:])
    )


def _parse_etherscan_result(item: dict) -> VerificationResult:
    """Parse one result entry from Etherscan's getsourcecode response.

    Etherscan returns an array with a single item; if the contract is NOT
    verified, the item has empty strings for ContractName/SourceCode/etc.
    The `Proxy` field is "1" if it's a proxy and `Implementation` contains
    the current implementation address (0x000... if unset).
    """
    contract_name_raw = item.get("ContractName") or ""
    source_code_raw = item.get("SourceCode") or ""
    is_verified = bool(contract_name_raw and source_code_raw)

    if not is_verified:
        return _EMPTY_NOT_VERIFIED

    proxy_flag = str(item.get("Proxy") or "0") == "1"
    impl_raw = item.get("Implementation") or ""
    # Etherscan uses `0x0000...` or empty string for "no impl set"
    impl = impl_raw if _is_evm_address(impl_raw) and int(impl_raw, 16) != 0 else None

    return VerificationResult(
        is_verified=True,
        contract_name=str(contract_name_raw),
        compiler_version=str(item.get("CompilerVersion") or "") or None,
        is_proxy=proxy_flag,
        proxy_impl_address=impl,
    )


async def check_verification(
    chain: Chain, address: str, *, client: httpx.AsyncClient | None = None
) -> VerificationResult:
    """Query Etherscan V2 for the verification status of `address` on `chain`.

    Returns a VerificationResult with `is_verified=False` on any non-success
    path (unsupported chain, missing key, HTTP failure, malformed response).
    Failures are logged but never raised — missing Etherscan data must not
    break the overall scan.
    """
    if chain not in CHAIN_TO_ETHERSCAN_ID:
        return _EMPTY_NOT_VERIFIED

    if not _is_evm_address(address):
        return _EMPTY_NOT_VERIFIED

    api_key = get_secret("etherscan", required=False)
    if not api_key:
        log.info("etherscan skipped: no API key in pass store")
        return _EMPTY_NOT_VERIFIED

    s = settings()
    url = "https://api.etherscan.io/v2/api"
    params = {
        "chainid": CHAIN_TO_ETHERSCAN_ID[chain],
        "module": "contract",
        "action": "getsourcecode",
        "address": address,
        "apikey": api_key,
    }

    try:
        payload = await get_json(url, params=params, client=client)
    except HttpError as exc:
        log.info("etherscan verification fetch failed for %s: %s", address, exc)
        return _EMPTY_NOT_VERIFIED

    if not isinstance(payload, dict):
        return _EMPTY_NOT_VERIFIED

    # Etherscan standard response: {"status": "1", "message": "OK", "result": [...]}
    status = str(payload.get("status") or "")
    result = payload.get("result")

    if status != "1" or not isinstance(result, list) or not result:
        return _EMPTY_NOT_VERIFIED

    return _parse_etherscan_result(result[0])
