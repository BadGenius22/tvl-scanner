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

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

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
    # Batch N.5: protocol identifier scraped from verified source comments
    # (`@author`, `@title`). Useful when contract_name is generic like
    # "ERC1967Proxy" or "Proxy" but the actual deployed protocol is named
    # in a Solidity doc comment.
    source_author: str | None = None
    source_title: str | None = None
    # Batch N.7: project directory name extracted from source file paths
    # (`src/moolah/...` → "moolah"). Often the most reliable protocol
    # identifier when contract names are generic ("StableSwapPool",
    # "ERC1967Proxy").
    source_project_dir: str | None = None


_EMPTY_NOT_VERIFIED = VerificationResult(is_verified=False)

# Etherscan free tier: 5 req/sec across the entire account, NOT per endpoint.
# When the scan fans out per-chain enrichment (3-6 chains × N candidates ×
# 2 calls each — verification + creation date — plus impl-verification fetches
# in the @author/@title attribution path), we easily blow past this and get
# silent NOTOK responses with status=0. A module-level semaphore + minimum
# spacing keeps us under the ceiling without slowing the rest of the pipeline.
_ETHERSCAN_MAX_CONCURRENT = 2
_ETHERSCAN_MIN_INTERVAL_SEC = 0.35
_etherscan_semaphore: asyncio.Semaphore | None = None
_etherscan_last_call: float = 0.0
_etherscan_lock: asyncio.Lock | None = None


def _get_etherscan_semaphore() -> asyncio.Semaphore:
    global _etherscan_semaphore
    if _etherscan_semaphore is None:
        _etherscan_semaphore = asyncio.Semaphore(_ETHERSCAN_MAX_CONCURRENT)
    return _etherscan_semaphore


def _get_etherscan_lock() -> asyncio.Lock:
    global _etherscan_lock
    if _etherscan_lock is None:
        _etherscan_lock = asyncio.Lock()
    return _etherscan_lock


async def _throttled_get_json(
    url: str, *, params: dict, client: httpx.AsyncClient | None
) -> object:
    """get_json with a global Etherscan semaphore + min-interval throttle.

    Ensures the free-tier 5 req/sec limit isn't tripped by parallel
    enrichment fan-out (which previously caused silent NOTOK responses
    that left contract verification empty and false positives in the
    under-audited classification).
    """
    global _etherscan_last_call
    sem = _get_etherscan_semaphore()
    lock = _get_etherscan_lock()
    async with sem:
        # Serialize the "wait for min interval" check under a lock — without
        # it, concurrent acquirers all read the same last_call and burst.
        async with lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - _etherscan_last_call
            if elapsed < _ETHERSCAN_MIN_INTERVAL_SEC:
                await asyncio.sleep(_ETHERSCAN_MIN_INTERVAL_SEC - elapsed)
            _etherscan_last_call = asyncio.get_event_loop().time()
        return await get_json(url, params=params, client=client)


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

    # Batch N.5: pull @author / @title tags from NatSpec comments in the
    # verified source. Catches protocols whose contract_name is generic
    # ("ERC1967Proxy", "Proxy") but whose deployed code is uniquely tagged
    # ("@author ether.fi", "@title TopUpDest"). Cap source scan at 200KB to
    # bound CPU on outsized contracts.
    source_code_str = source_code_raw[:200_000] if isinstance(source_code_raw, str) else ""
    author = None
    title = None
    if source_code_str:
        author_match = re.search(
            r"@author\s+([\w.\-]+(?:[\s\-][\w.\-]+){0,3})", source_code_str
        )
        if author_match:
            author = author_match.group(1).strip()
        title_match = re.search(
            r"@title\s+([\w.\-]+(?:[\s\-][\w.\-]+){0,5})", source_code_str
        )
        if title_match:
            title = title_match.group(1).strip()

    # Batch N.7: extract project directory name from source paths. Pattern:
    # `src/<protocol>/...` is overwhelmingly used by Foundry/Hardhat projects.
    # Skip generic prefixes like "interfaces", "libraries", "utils", "test".
    project_dir = None
    if source_code_str:
        # Find all `"src/<name>/..."` and `"contracts/<name>/..."` paths
        path_dirs: dict[str, int] = {}
        for m in re.finditer(
            r'"(?:src|contracts)/([a-z][\w\-]+)/', source_code_str, re.IGNORECASE
        ):
            d = m.group(1).lower()
            if d in {
                "interfaces", "libraries", "utils", "test", "tests",
                "mocks", "lib", "common", "shared", "abstract", "types",
                "errors", "events", "constants",
            }:
                continue
            path_dirs[d] = path_dirs.get(d, 0) + 1
        if path_dirs:
            # Pick the most frequent (the project's own code dominates)
            project_dir = max(path_dirs.items(), key=lambda x: x[1])[0]

    return VerificationResult(
        is_verified=True,
        contract_name=str(contract_name_raw),
        compiler_version=str(item.get("CompilerVersion") or "") or None,
        is_proxy=proxy_flag,
        proxy_impl_address=impl,
        source_author=author,
        source_title=title,
        source_project_dir=project_dir,
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

    # Retry-on-NOTOK loop. Etherscan rate-limits return HTTP 200 with
    # `{"status":"0","message":"NOTOK"}` — http.py's retry doesn't catch
    # that (it's not a 429). We do our own retry here: up to 2 attempts
    # with a sleep that puts us well outside any rate-limit window.
    payload: object | None = None
    for attempt in range(2):
        try:
            payload = await _throttled_get_json(url, params=params, client=client)
        except HttpError as exc:
            log.info("etherscan verification fetch failed for %s: %s", address, exc)
            return _EMPTY_NOT_VERIFIED

        if isinstance(payload, dict):
            status = str(payload.get("status") or "")
            result = payload.get("result")
            if status == "1" and isinstance(result, list) and result:
                break  # success — proceed to parse
            if attempt == 0:
                # NOTOK / partial response — wait + retry once
                await asyncio.sleep(1.5)
                continue
            msg = payload.get("message") or payload.get("result")
            log.info(
                "etherscan getsourcecode returned non-success for %s (chainid %s): %s",
                address, CHAIN_TO_ETHERSCAN_ID.get(chain), str(msg)[:200],
            )
            return _EMPTY_NOT_VERIFIED
        return _EMPTY_NOT_VERIFIED

    if not isinstance(payload, dict):
        return _EMPTY_NOT_VERIFIED
    result = payload.get("result")
    if not isinstance(result, list) or not result:
        return _EMPTY_NOT_VERIFIED

    return _parse_etherscan_result(result[0])


_CREATION_BATCH_SIZE = 5  # Etherscan V2 accepts up to 5 addresses per call


async def fetch_creation_dates_batch(
    chain: Chain, addresses: list[str], *, client: httpx.AsyncClient | None = None
) -> dict[str, date]:
    """Bulk-resolve deployment dates for `addresses` on `chain` via Etherscan V2.

    Etherscan's `contract/getcontractcreation` accepts a comma-separated list
    of up to 5 addresses per call (per V2 docs). Batching this way drops the
    request count from N to ceil(N/5), which is the difference between most
    calls 429-ing on the free tier (5 req/s) versus most calls succeeding.

    Returns a dict mapping (lowercase) address → date for every successfully
    resolved address. Addresses missing from the dict can be defaulted by
    the caller (typically to scan_date). Errors are logged at INFO and
    silently dropped — partial coverage is better than no coverage.
    """
    if chain not in CHAIN_TO_ETHERSCAN_ID:
        return {}
    api_key = get_secret("etherscan", required=False)
    if not api_key:
        return {}

    valid_addrs = [a.lower() for a in addresses if _is_evm_address(a)]
    if not valid_addrs:
        return {}

    url = "https://api.etherscan.io/v2/api"
    chain_id = CHAIN_TO_ETHERSCAN_ID[chain]
    out: dict[str, date] = {}

    for batch_start in range(0, len(valid_addrs), _CREATION_BATCH_SIZE):
        batch = valid_addrs[batch_start : batch_start + _CREATION_BATCH_SIZE]
        params = {
            "chainid": chain_id,
            "module": "contract",
            "action": "getcontractcreation",
            "contractaddresses": ",".join(batch),
            "apikey": api_key,
        }
        try:
            payload = await _throttled_get_json(url, params=params, client=client)
        except HttpError as exc:
            log.info(
                "etherscan creation batch failed (%d addrs on %s): %s",
                len(batch),
                chain.value,
                exc,
            )
            continue

        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status") or "")
        result = payload.get("result")
        if status != "1" or not isinstance(result, list):
            continue

        for entry in result:
            if not isinstance(entry, dict):
                continue
            entry_addr_raw = entry.get("contractAddress")
            ts_raw = entry.get("timestamp")
            if not isinstance(entry_addr_raw, str):
                continue
            try:
                ts = int(ts_raw)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            if ts <= 0:
                continue
            out[entry_addr_raw.lower()] = datetime.fromtimestamp(
                ts, tz=timezone.utc
            ).date()

    return out


async def fetch_creation_date(
    chain: Chain, address: str, *, client: httpx.AsyncClient | None = None
) -> date | None:
    """Single-address creation date lookup — convenience wrapper over the batch.

    Kept for callers that only need one address (and for tests). Batches of
    size 1 still use the same Etherscan endpoint with the same cost as a
    direct query.
    """
    result = await fetch_creation_dates_batch(chain, [address], client=client)
    return result.get(address.lower())
