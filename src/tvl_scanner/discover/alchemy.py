"""Alchemy-based fresh contract deployment discovery.

For each EVM chain, sample blocks from the last N days, fetch all transaction
receipts per sampled block via `alchemy_getTransactionReceipts`, filter for
successful contract creations (`contractAddress != null AND status == '0x1'`),
then batch-check each new contract's native-token balance via `eth_getBalance`.
Contracts whose `balance × native_price_usd >= MIN_TVL_USD` survive.

Design decisions:
  - We SAMPLE blocks rather than walk every block. A full 7-day scan would be
    ~50k blocks/chain × 200ms/call = ~3 hours/chain. Sampling 50 blocks keeps
    it to ~10 seconds/chain and still catches roughly 0.1% of all deployments
    which is plenty given the TVL filter kills 99% of noise anyway.
  - Only the NATIVE token balance is checked. Most DeFi holds user ERC20s
    (USDC, WETH) so native balance is zero for them — those miss. But LSD
    wrappers, liquid restaking, leveraged-ETH, bridges, and pure-native vaults
    DO hold native, and those are exactly the classes GeckoTerminal misses.
    Treat this as a complementary source, not a replacement.
  - Failures (RPC outage, rate limit) degrade to [] per chain, never raise.

Each Alchemy URL is constructed from the API key + chain subdomain:
    https://{subdomain}.g.alchemy.com/v2/{API_KEY}
where subdomain is eth-mainnet / arb-mainnet / base-mainnet / opt-mainnet /
polygon-mainnet / bnb-mainnet (unfortunately not a uniform naming scheme).
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import date, datetime
from typing import Any

import httpx

from tvl_scanner.config import get_secret, settings
from tvl_scanner.enrich.prices import PriceCache
from tvl_scanner.http import HttpError, make_client
from tvl_scanner.models import Chain, DiscoveredContract, DiscoverySource

log = logging.getLogger(__name__)


# Alchemy subdomain mapping. Solana is skipped — Alchemy supports it but its
# program model is different enough that shoehorning here would be misleading.
CHAIN_TO_ALCHEMY_SUBDOMAIN: dict[Chain, str] = {
    Chain.ETHEREUM: "eth-mainnet",
    Chain.ARBITRUM: "arb-mainnet",
    Chain.BASE: "base-mainnet",
    Chain.OPTIMISM: "opt-mainnet",
    Chain.POLYGON: "polygon-mainnet",
    Chain.BSC: "bnb-mainnet",
}


# Approximate block times in seconds. Used to convert "N days of history" to
# a block count. Exact values don't matter; being off by 20% just changes the
# sampling window slightly.
BLOCK_TIME_SECONDS: dict[Chain, float] = {
    Chain.ETHEREUM: 12.0,
    Chain.ARBITRUM: 0.26,
    Chain.BASE: 2.0,
    Chain.OPTIMISM: 2.0,
    Chain.POLYGON: 2.1,
    Chain.BSC: 3.0,
}


# Tunables. Kept as module constants rather than in Settings so they don't
# pollute the non-secret .env file.
#
# BATCH G FIX #2: v1 used sample_blocks=50 + concurrency 10/20 which saturated
# Alchemy's free-tier compute unit budget (300 CU/sec, ~10 req/s sustained).
# Lowered to 25/3/5 so a full-chain run stays under the bucket and actually
# completes. The tradeoff: ~half the sample coverage, but we were catching 0
# candidates anyway with the old settings due to 429 storms, so this is
# strictly better until we move to a paid tier.
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_SAMPLE_BLOCKS = 25
RECEIPT_CONCURRENCY = 3
BALANCE_CHECK_CONCURRENCY = 5


def _alchemy_url(chain: Chain) -> str | None:
    subdomain = CHAIN_TO_ALCHEMY_SUBDOMAIN.get(chain)
    if not subdomain:
        return None
    api_key = get_secret("alchemy", required=False)
    if not api_key:
        return None
    return f"https://{subdomain}.g.alchemy.com/v2/{api_key}"


async def _rpc_call(
    url: str, method: str, params: list, client: httpx.AsyncClient
) -> Any:
    """Make a single JSON-RPC call. Returns the `result` field or None on error."""
    try:
        response = await client.post(
            url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data.get("result")
        return None
    except (httpx.HTTPError, ValueError, HttpError) as exc:
        log.debug("alchemy rpc %s failed: %s", method, exc)
        return None


def _hex_to_int(h: str | None) -> int:
    if not h or not isinstance(h, str):
        return 0
    try:
        return int(h, 16)
    except ValueError:
        return 0


async def _latest_block(url: str, client: httpx.AsyncClient) -> int:
    result = await _rpc_call(url, "eth_blockNumber", [], client)
    return _hex_to_int(result) if isinstance(result, str) else 0


def _sample_blocks(latest: int, chain: Chain, *, lookback_days: int, samples: int) -> list[int]:
    """Pick `samples` distinct block numbers spread over the last `lookback_days`."""
    if latest <= 0:
        return []
    block_time = BLOCK_TIME_SECONDS.get(chain, 12.0)
    window_blocks = int(lookback_days * 86400 / block_time)
    window_start = max(0, latest - window_blocks)
    if samples >= window_blocks:
        return list(range(window_start, latest))
    rng = random.Random(latest)  # seeded for reproducibility within a scan
    return sorted(rng.sample(range(window_start, latest), samples))


async def _get_receipts_for_block(
    url: str, block_number: int, client: httpx.AsyncClient
) -> list[dict]:
    """Fetch all tx receipts for a block via alchemy_getTransactionReceipts."""
    params = [{"blockNumber": hex(block_number)}]
    result = await _rpc_call(url, "alchemy_getTransactionReceipts", params, client)
    if isinstance(result, dict):
        receipts = result.get("receipts") or []
        return receipts if isinstance(receipts, list) else []
    if isinstance(result, list):
        return result
    return []


async def _get_balance(
    url: str, address: str, client: httpx.AsyncClient
) -> int:
    """Return the address's current native balance in wei."""
    result = await _rpc_call(url, "eth_getBalance", [address, "latest"], client)
    return _hex_to_int(result) if isinstance(result, str) else 0


def _extract_creations(receipts: list[dict], chain: Chain) -> list[str]:
    """Pull successful contract-creation addresses from a list of receipts."""
    creations: list[str] = []
    for r in receipts:
        if not isinstance(r, dict):
            continue
        contract_addr = r.get("contractAddress")
        status = r.get("status")
        if contract_addr and status == "0x1":
            creations.append(str(contract_addr))
    return creations


async def fetch_fresh_deployments(
    chain: Chain,
    *,
    price_cache: PriceCache,
    client: httpx.AsyncClient | None = None,
    scan_date: date | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    sample_blocks: int = DEFAULT_SAMPLE_BLOCKS,
) -> list[DiscoveredContract]:
    """Discover fresh contract deployments on `chain` with native balance above threshold.

    Returns an empty list (silently) if Alchemy is not configured for this
    chain or the API key is missing.
    """
    url = _alchemy_url(chain)
    if not url:
        log.info("alchemy skipped for %s: no subdomain or no API key", chain.value)
        return []

    s = settings()
    scan_date = scan_date or date.today()

    owns_client = client is None
    if owns_client:
        client = make_client()
    assert client is not None

    try:
        # Step 1: get latest block + sample blocks from the lookback window
        latest = await _latest_block(url, client)
        if latest == 0:
            log.warning("alchemy %s: eth_blockNumber returned 0 — skipping", chain.value)
            return []

        sampled = _sample_blocks(
            latest, chain, lookback_days=lookback_days, samples=sample_blocks
        )
        log.info(
            "alchemy %s: sampling %d blocks from last %d days (window %d..%d)",
            chain.value,
            len(sampled),
            lookback_days,
            sampled[0] if sampled else 0,
            sampled[-1] if sampled else 0,
        )

        # Step 2: fetch receipts per sampled block in parallel with bounded concurrency
        receipt_sem = asyncio.Semaphore(RECEIPT_CONCURRENCY)

        async def _bounded_receipts(block_num: int) -> tuple[int, list[dict]]:
            async with receipt_sem:
                return block_num, await _get_receipts_for_block(url, block_num, client)

        receipt_tasks = [_bounded_receipts(b) for b in sampled]
        receipt_results = await asyncio.gather(*receipt_tasks, return_exceptions=True)

        # Step 3: extract contract creations
        creations_by_block: dict[int, list[str]] = {}
        for result in receipt_results:
            if isinstance(result, BaseException):
                continue
            block_num, receipts = result
            addrs = _extract_creations(receipts, chain)
            if addrs:
                creations_by_block[block_num] = addrs

        total_creations = sum(len(v) for v in creations_by_block.values())
        log.info(
            "alchemy %s: found %d contract creations in %d blocks",
            chain.value,
            total_creations,
            len(creations_by_block),
        )
        if total_creations == 0:
            return []

        # Step 4: batch check balances
        all_creations = [
            (block, addr) for block, addrs in creations_by_block.items() for addr in addrs
        ]
        balance_sem = asyncio.Semaphore(BALANCE_CHECK_CONCURRENCY)

        async def _bounded_balance(block: int, addr: str) -> tuple[int, str, int]:
            async with balance_sem:
                wei = await _get_balance(url, addr, client)
                return block, addr, wei

        balance_tasks = [_bounded_balance(b, a) for (b, a) in all_creations]
        balance_results = await asyncio.gather(*balance_tasks, return_exceptions=True)

        # Step 5: convert balance to USD and filter
        native_usd = await price_cache.get(chain, client=client)
        if native_usd <= 0:
            log.warning(
                "alchemy %s: native price = 0, cannot threshold — skipping this source",
                chain.value,
            )
            return []

        block_time = BLOCK_TIME_SECONDS.get(chain, 12.0)

        kept: list[DiscoveredContract] = []
        for bal_result in balance_results:
            if isinstance(bal_result, BaseException):
                continue
            block, addr, wei = bal_result
            balance_eth = wei / 1e18
            balance_usd = balance_eth * native_usd
            if balance_usd < s.MIN_TVL_USD:
                continue

            # Estimate deployment date from block number
            blocks_ago = latest - block
            seconds_ago = blocks_ago * block_time
            deployed_at = datetime.fromtimestamp(
                datetime.now().timestamp() - seconds_ago
            ).date()

            kept.append(
                DiscoveredContract(
                    chain=chain,
                    address=addr,
                    protocol_guess=None,  # no name available at discovery time
                    tvl_usd=balance_usd,
                    first_seen=deployed_at,
                    unique_users_30d=None,  # unknown
                    source=DiscoverySource.ALCHEMY_DEPLOYMENTS,
                )
            )

        log.info(
            "alchemy %s: %d of %d fresh deployments above $%d threshold",
            chain.value,
            len(kept),
            total_creations,
            s.MIN_TVL_USD,
        )
        return kept

    finally:
        if owns_client:
            await client.aclose()
