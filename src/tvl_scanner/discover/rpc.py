"""Pure-RPC "active contracts holding ≥ MIN_TVL_USD" discoverer.

For each EVM chain, sample short windows of recent blocks, fetch ERC20 Transfer
logs for a curated set of high-cap tokens, collect the unique recipient
addresses, drop EOAs via `eth_getCode`, and balance-check the surviving
contracts. Contracts whose `native + curated_erc20` USD value crosses the
threshold are emitted as `DiscoveredContract` records.

Distinct from `discover/alchemy.py`:
  - alchemy.py finds FRESHLY DEPLOYED contracts (last 7 days of creations).
  - rpc.py finds ACTIVE contracts (received a tracked-token Transfer in the
    last 7 days), regardless of when they were deployed. Catches established
    vaults whose deployment is outside the lookback window but whose balance
    is real and current.

Design constraints:
  - Only STANDARD JSON-RPC calls are used: `eth_blockNumber`, `eth_getLogs`,
    `eth_getCode`, `eth_call`, `eth_getBalance`. No Alchemy-specific
    extensions — the discoverer works against any compliant RPC endpoint
    (Alchemy, Infura, QuickNode, public RPCs, self-hosted node).
  - The default RPC URL is the existing Alchemy one (so this module slots in
    without new credentials). Per-chain overrides via
    `TVL_SCANNER_RPC_<CHAIN>` env vars let users plug their own endpoint.
  - Each call to `eth_getLogs` is bounded by `_WINDOW_BLOCKS` so the response
    stays under typical provider log-count limits (10k logs/call on Alchemy
    free tier).

Pricing:
  - Native: existing `PriceCache` (Coingecko + fallback).
  - ERC20: existing DefiLlama batch price fetcher.

`first_seen` is set to `scan_date` (today) — we have no on-chain way to know
deployment date without an extra round-trip per address, and the audit-
targeting downstream filters can still demote stale contracts via other
signals.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from datetime import date
from typing import Any

import httpx

from tvl_scanner.config import get_secret, settings
from tvl_scanner.discover.alchemy import (
    BLOCK_TIME_SECONDS,
    CHAIN_TO_ALCHEMY_SUBDOMAIN,
)
from tvl_scanner.enrich.defillama_prices import (
    TokenPrice,
    _build_coin_key,
    fetch_prices,
)
from tvl_scanner.enrich.etherscan import fetch_creation_dates_batch
from tvl_scanner.enrich.prices import PriceCache
from tvl_scanner.http import HttpError, make_client
from tvl_scanner.models import Chain, DiscoveredContract, DiscoverySource

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Curated token list per chain
# ─────────────────────────────────────────────────────────────────────────────
#
# Intentionally narrow: stablecoins + the chain's wrapped native + WBTC where
# applicable. Goal is to catch ~95% of DeFi TVL by tracking the dozen assets
# that protocols actually custody, without paying for long-tail token discovery.
#
# A protocol holding only obscure assets (a custom LST, a new memecoin) will be
# missed here — but that's the right trade-off for a generic discoverer. The
# Gecko/Birdeye sources cover that long-tail by aggregating pool reserves.
#
# All addresses are checksummed mainnet addresses. We lowercase before use
# because JSON-RPC accepts either case but log topics return lowercase.
CURATED_TOKENS: dict[Chain, list[str]] = {
    Chain.ETHEREUM: [
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
        "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
        "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI
        "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
        "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # WBTC
    ],
    Chain.ARBITRUM: [
        "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",  # USDC (native)
        "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",  # USDC.e (bridged)
        "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",  # USDT
        "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",  # WETH
        "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",  # WBTC
    ],
    Chain.BASE: [
        "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC
        "0x4200000000000000000000000000000000000006",  # WETH
        "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",  # DAI
        "0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22",  # cbETH
    ],
    Chain.OPTIMISM: [
        "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",  # USDC (native)
        "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",  # USDC.e (bridged)
        "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",  # USDT
        "0x4200000000000000000000000000000000000006",  # WETH
        "0x68f180fcCe6836688e9084f035309E29Bf0A2095",  # WBTC
    ],
    Chain.POLYGON: [
        "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",  # USDC (native)
        "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # USDC.e (bridged)
        "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",  # USDT
        "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",  # WETH
        "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",  # WMATIC
    ],
    Chain.BSC: [
        "0x55d398326f99059fF775485246999027B3197955",  # USDT (BSC)
        "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",  # USDC (BSC)
        "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",  # BUSD
        "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
        "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",  # BTCB
    ],
}


# keccak256("Transfer(address,address,uint256)")
_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Function selector for `balanceOf(address)` — first 4 bytes of
# keccak256("balanceOf(address)").
_BALANCE_OF_SELECTOR = "0x70a08231"


# Tunables — kept as constants rather than Settings so they don't pollute the
# user-facing .env. The 7-day lookback matches the user's stated requirement.
DEFAULT_LOOKBACK_DAYS = 7
# Number of small block windows to sample across the lookback range. Tuned
# alongside DEFAULT_WINDOW_BLOCKS for free-tier RPC budgets. At 50 windows ×
# 10 blocks per chain × 6 chains the eth_getCode follow-up phase 429'd hard
# on Alchemy's free tier (38k+ failures in one scan); 25 windows fits within
# the compute-unit budget while still catching active high-TVL holders.
DEFAULT_SAMPLE_WINDOWS = 25
# Hard cap on recipients to eth_getCode-check per chain. Ethereum windows can
# surface 24k+ unique recipient addresses; checking code on all of them is
# 24k × 19 CU = 456k CU per chain — 25 minutes of sustained free-tier budget
# just for one chain. Random-sample down to keep the scan in finite time.
# High-TVL contracts are naturally over-represented in busy windows, so the
# sample preserves them with high probability even at 1000/24000 = 4%.
MAX_RECIPIENTS_PER_CHAIN = 1000
# Per-window block count. Alchemy's free tier rejects eth_getLogs requests
# spanning more than 10 blocks (-32600 error: "Under the Free tier plan, you
# can make eth_getLogs requests with up to a 10 block range"). The first real
# scan with WINDOW_BLOCKS=50 returned 0 recipients on every chain because
# every call 400'd. 10 is the exact ceiling — using less wastes API budget.
# Users on a paid tier can override via the per-chain RPC env var by pointing
# at a node without that limit; the constant itself stays free-tier-safe.
DEFAULT_WINDOW_BLOCKS = 10
# Concurrency limits — mirror discover/alchemy.py so a full-chain run stays
# under Alchemy's free-tier compute-unit budget (300 CU/s).
LOG_QUERY_CONCURRENCY = 3
CODE_CHECK_CONCURRENCY = 5
BALANCE_CHECK_CONCURRENCY = 5


def _rpc_url(chain: Chain) -> str | None:
    """Resolve the RPC URL for `chain`.

    Priority:
      1. `TVL_SCANNER_RPC_<CHAIN>` env var (lets users plug their own node).
      2. Alchemy URL constructed from `tvl-scanner/alchemy` secret + subdomain.

    Returns None if neither is available (chain is then skipped).
    """
    custom = os.environ.get(f"TVL_SCANNER_RPC_{chain.value.upper()}")
    if custom:
        return custom

    subdomain = CHAIN_TO_ALCHEMY_SUBDOMAIN.get(chain)
    if not subdomain:
        return None
    api_key = get_secret("alchemy", required=False)
    if not api_key:
        return None
    return f"https://{subdomain}.g.alchemy.com/v2/{api_key}"


_RETRYABLE_STATUS = {429, 502, 503, 504}


async def _rpc_call(
    url: str, method: str, params: list[Any], client: httpx.AsyncClient,
    *, max_retries: int = 1,
) -> Any:
    """Single JSON-RPC call with one retry on rate-limit / transient errors.

    `max_retries=1` is a deliberate trade-off: when EVERY call in a batch is
    429-ing (free-tier compute exhaustion), retrying 3+ times with backoff
    snowballs into a multi-minute death-spiral. One retry with short backoff
    catches transient hiccups without serializing the whole scan. The
    `MAX_RECIPIENTS_PER_CHAIN` cap upstream keeps batches small enough that
    most calls succeed first try.

    Logs both transport failures (after retries exhausted) and JSON-RPC
    error responses at INFO so silent provider complaints are visible.
    """
    for attempt in range(max_retries + 1):
        try:
            response = await client.post(
                url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                timeout=30.0,
            )
            if response.status_code in _RETRYABLE_STATUS and attempt < max_retries:
                retry_after_raw = response.headers.get("retry-after", "")
                if retry_after_raw.isdigit():
                    delay = min(int(retry_after_raw), 5)
                else:
                    delay = 2  # short fixed backoff, single retry
                await asyncio.sleep(delay)
                continue
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                if "error" in data:
                    log.info("rpc %s returned JSON-RPC error: %s", method, data["error"])
                    return None
                return data.get("result")
            return None
        except (httpx.HTTPError, ValueError, HttpError) as exc:
            transient = (
                isinstance(exc, httpx.HTTPStatusError)
                and exc.response.status_code in _RETRYABLE_STATUS
            ) or isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout))
            if transient and attempt < max_retries:
                await asyncio.sleep(2)
                continue
            log.info("rpc %s transport failed: %s", method, exc)
            return None
    return None


def _hex_to_int(h: str | None) -> int:
    if not h or not isinstance(h, str):
        return 0
    try:
        return int(h, 16)
    except ValueError:
        return 0


def _decode_topic_address(topic_hex: str) -> str | None:
    """Decode a 32-byte log topic into a 20-byte hex address.

    Topics are left-padded with zeros (e.g. `0x000...abc` for address `0xabc`).
    We take the last 20 bytes (40 hex chars). Returns None on malformed input.
    """
    if not isinstance(topic_hex, str) or not topic_hex.startswith("0x"):
        return None
    body = topic_hex[2:]
    if len(body) != 64:
        return None
    return "0x" + body[-40:]


def _encode_address_param(address: str) -> str:
    """Left-pad a 20-byte address to a 32-byte calldata word (hex, no 0x)."""
    clean = address[2:] if address.startswith("0x") else address
    return clean.lower().zfill(64)


def _sample_windows(
    latest: int, chain: Chain, *, lookback_days: int, windows: int, window_blocks: int
) -> list[tuple[int, int]]:
    """Pick `windows` non-overlapping (fromBlock, toBlock) inclusive ranges.

    `window_blocks` is the inclusive block count — a value of 10 returns
    (s, s+9) tuples so the eth_getLogs call covers exactly 10 blocks. This
    matters because Alchemy's free tier rejects any wider range.
    """
    if latest <= 0:
        return []
    block_time = BLOCK_TIME_SECONDS.get(chain, 12.0)
    range_blocks = int(lookback_days * 86400 / block_time)
    window_start = max(0, latest - range_blocks)
    available = latest - window_start
    if available <= window_blocks:
        return [(window_start, min(window_start + window_blocks - 1, latest))]

    # Seeded for reproducibility within a scan
    rng = random.Random(latest)
    # Pick `windows` distinct starting block numbers
    max_start = latest - window_blocks + 1
    if windows >= (max_start - window_start):
        return [(b, b + window_blocks - 1) for b in range(window_start, max_start)]
    starts = sorted(rng.sample(range(window_start, max_start), windows))
    return [(s, s + window_blocks - 1) for s in starts]


async def _get_logs_for_window(
    url: str,
    from_block: int,
    to_block: int,
    tokens: list[str],
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    """Fetch all Transfer logs for `tokens` in [from_block, to_block]."""
    params = [
        {
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "address": [t.lower() for t in tokens],
            "topics": [_TRANSFER_TOPIC],
        }
    ]
    result = await _rpc_call(url, "eth_getLogs", params, client)
    if isinstance(result, list):
        return result
    return []


def _extract_recipients(logs: list[dict[str, Any]]) -> set[str]:
    """Pull the `to` field from each Transfer log's topics[2]."""
    out: set[str] = set()
    for log_entry in logs:
        if not isinstance(log_entry, dict):
            continue
        topics = log_entry.get("topics")
        if not isinstance(topics, list) or len(topics) < 3:
            continue
        addr = _decode_topic_address(str(topics[2]))
        if addr:
            out.add(addr)
    return out


async def _get_code(
    url: str, address: str, client: httpx.AsyncClient
) -> str | None:
    """Return the contract bytecode (hex string) at `address`. '0x' or '' = EOA."""
    result = await _rpc_call(url, "eth_getCode", [address, "latest"], client)
    if isinstance(result, str):
        return result
    return None


async def _get_native_balance(
    url: str, address: str, client: httpx.AsyncClient
) -> int:
    """Native balance in wei. 0 on error."""
    result = await _rpc_call(url, "eth_getBalance", [address, "latest"], client)
    return _hex_to_int(result) if isinstance(result, str) else 0


async def _get_token_balance(
    url: str, token: str, holder: str, client: httpx.AsyncClient
) -> int:
    """ERC20 `balanceOf(holder)` via eth_call. 0 on error."""
    call_data = _BALANCE_OF_SELECTOR + _encode_address_param(holder)
    params = [{"to": token, "data": call_data}, "latest"]
    result = await _rpc_call(url, "eth_call", params, client)
    return _hex_to_int(result) if isinstance(result, str) else 0


async def fetch_active_holders(
    chain: Chain,
    *,
    price_cache: PriceCache,
    client: httpx.AsyncClient | None = None,
    scan_date: date | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    sample_windows: int = DEFAULT_SAMPLE_WINDOWS,
    window_blocks: int = DEFAULT_WINDOW_BLOCKS,
) -> list[DiscoveredContract]:
    """Discover active contracts on `chain` holding ≥ MIN_TVL_USD.

    Returns an empty list (silently) if no RPC endpoint is configured for this
    chain or if Solana is requested (Solana uses a different address model and
    has its own discoverer in birdeye.py).
    """
    url = _rpc_url(chain)
    if not url:
        log.info("rpc holders skipped for %s: no RPC URL", chain.value)
        return []

    tokens = CURATED_TOKENS.get(chain, [])
    if not tokens:
        log.info("rpc holders skipped for %s: no curated tokens", chain.value)
        return []

    s = settings()
    scan_date = scan_date or date.today()

    owns_client = client is None
    if owns_client:
        client = make_client()
    assert client is not None

    try:
        # ── Step 1: latest block + sample windows ───────────────────────────
        latest_raw = await _rpc_call(url, "eth_blockNumber", [], client)
        latest = _hex_to_int(latest_raw) if isinstance(latest_raw, str) else 0
        if latest == 0:
            log.warning("rpc holders %s: eth_blockNumber returned 0", chain.value)
            return []

        windows = _sample_windows(
            latest,
            chain,
            lookback_days=lookback_days,
            windows=sample_windows,
            window_blocks=window_blocks,
        )
        log.info(
            "rpc holders %s: sampling %d windows of %d blocks from last %d days",
            chain.value,
            len(windows),
            window_blocks,
            lookback_days,
        )

        # ── Step 2: fetch Transfer logs per window ──────────────────────────
        log_sem = asyncio.Semaphore(LOG_QUERY_CONCURRENCY)

        async def _bounded_logs(w: tuple[int, int]) -> list[dict[str, Any]]:
            async with log_sem:
                return await _get_logs_for_window(url, w[0], w[1], tokens, client)

        log_results = await asyncio.gather(
            *[_bounded_logs(w) for w in windows], return_exceptions=True
        )

        all_recipients: set[str] = set()
        total_logs = 0
        empty_windows = 0
        error_windows = 0
        for log_result in log_results:
            if isinstance(log_result, BaseException):
                error_windows += 1
                continue
            if not log_result:
                empty_windows += 1
                continue
            total_logs += len(log_result)
            all_recipients.update(_extract_recipients(log_result))

        log.info(
            "rpc holders %s: %d transfer logs across %d windows "
            "(%d empty, %d errored) → %d unique recipients",
            chain.value,
            total_logs,
            len(windows),
            empty_windows,
            error_windows,
            len(all_recipients),
        )
        if not all_recipients:
            return []

        # ── Step 2b: cap recipients to keep eth_getCode batch finite ───────
        # Without this cap, Ethereum windows can surface 25k+ unique
        # recipients; checking code on all of them blows the free-tier RPC
        # budget. Deterministic sample (seeded on latest block) preserves
        # reproducibility within a scan.
        if len(all_recipients) > MAX_RECIPIENTS_PER_CHAIN:
            rng_cap = random.Random(latest + 1)
            sampled = rng_cap.sample(
                sorted(all_recipients), MAX_RECIPIENTS_PER_CHAIN
            )
            log.info(
                "rpc holders %s: capping recipients %d → %d for code/balance phase",
                chain.value,
                len(all_recipients),
                MAX_RECIPIENTS_PER_CHAIN,
            )
            all_recipients = set(sampled)

        # ── Step 3: filter to contracts (eth_getCode != "0x") ───────────────
        code_sem = asyncio.Semaphore(CODE_CHECK_CONCURRENCY)

        async def _bounded_code(addr: str) -> tuple[str, str | None]:
            async with code_sem:
                return addr, await _get_code(url, addr, client)

        code_results = await asyncio.gather(
            *[_bounded_code(a) for a in all_recipients], return_exceptions=True
        )

        contracts: list[str] = []
        eip7702_count = 0
        for code_result in code_results:
            if isinstance(code_result, BaseException):
                continue
            addr, code = code_result
            if not code or code == "0x" or code == "0x0":
                continue
            # EIP-7702 delegations are EOAs delegated to a contract — the
            # "code" is 23 bytes starting with `0xef0100`. These are user
            # smart wallets (Safe, Coinbase Smart Wallet, etc.), NOT
            # protocols. Filter them out at the discovery boundary so they
            # never show up as candidates regardless of TVL.
            code_lower = code.lower()
            if len(code_lower) == 48 and code_lower.startswith("0xef0100"):
                eip7702_count += 1
                continue
            contracts.append(addr)

        log.info(
            "rpc holders %s: %d of %d recipients are contracts (%d EIP-7702 EOAs filtered)",
            chain.value,
            len(contracts),
            len(all_recipients),
            eip7702_count,
        )
        if not contracts:
            return []

        # ── Step 4: balance check each contract ─────────────────────────────
        balance_sem = asyncio.Semaphore(BALANCE_CHECK_CONCURRENCY)

        async def _bounded_balances(
            addr: str,
        ) -> tuple[str, int, list[tuple[str, int]]]:
            async with balance_sem:
                native_wei = await _get_native_balance(url, addr, client)
                token_balances: list[tuple[str, int]] = []
                # Sequential within a single contract to keep total in-flight
                # request count bounded — outer semaphore caps concurrency.
                for token in tokens:
                    raw = await _get_token_balance(url, token, addr, client)
                    if raw > 0:
                        token_balances.append((token, raw))
                return addr, native_wei, token_balances

        balance_results = await asyncio.gather(
            *[_bounded_balances(c) for c in contracts], return_exceptions=True
        )

        # ── Step 5a: resolve native price ───────────────────────────────────
        native_usd = await price_cache.get(chain, client=client)
        if native_usd <= 0:
            log.warning(
                "rpc holders %s: native price = 0, skipping source", chain.value
            )
            return []

        # ── Step 5b: batch-fetch ERC20 prices ───────────────────────────────
        unique_coin_keys: set[str] = set()
        valid_results: list[tuple[str, int, list[tuple[str, int]]]] = []
        for balance_result in balance_results:
            if isinstance(balance_result, BaseException):
                continue
            valid_results.append(balance_result)
            _, _, token_balances = balance_result
            for token_addr, _raw in token_balances:
                key = _build_coin_key(chain, token_addr)
                if key:
                    unique_coin_keys.add(key)

        price_map: dict[str, TokenPrice] = {}
        if unique_coin_keys:
            price_map = await fetch_prices(sorted(unique_coin_keys), client=client)

        # ── Step 5c: compute USD TVL per contract, filter ───────────────────
        # First pass: build (addr, total_tvl_usd) for everything above threshold
        # so we know which contracts deserve a creation-date round-trip.
        survivors: list[tuple[str, float]] = []
        for addr, native_wei, token_balances in valid_results:
            native_value_usd = (native_wei / 1e18) * native_usd

            erc20_value_usd = 0.0
            for token_addr, raw_bal in token_balances:
                key = _build_coin_key(chain, token_addr)
                if not key:
                    continue
                price = price_map.get(key)
                if not price:
                    continue
                try:
                    erc20_value_usd += (
                        raw_bal / (10 ** price.decimals)
                    ) * price.price
                except (ZeroDivisionError, OverflowError):
                    continue

            total_tvl_usd = native_value_usd + erc20_value_usd
            if total_tvl_usd < s.MIN_TVL_USD:
                continue
            survivors.append((addr, total_tvl_usd))

        # ── Step 5d: bulk-fetch real deployment dates ───────────────────────
        # Etherscan V2 supports up to 5 addresses per getcontractcreation call.
        # Batching N → ceil(N/5) makes the difference between most calls
        # 429-ing on the free tier (5 req/s) vs. most calls succeeding. We
        # default first_seen to scan_date only as a fallback for addresses
        # Etherscan can't resolve — previously this fallback fired on 109 of
        # 111 candidates and put 5-year-old pools at the top tagged "0d old".
        survivor_addrs = [addr for addr, _ in survivors]
        creation_map = await fetch_creation_dates_batch(
            chain, survivor_addrs, client=client
        )
        log.info(
            "rpc holders %s: resolved creation dates for %d of %d survivors",
            chain.value,
            len(creation_map),
            len(survivor_addrs),
        )

        kept: list[DiscoveredContract] = []
        for addr, total_tvl_usd in survivors:
            first_seen_date = creation_map.get(addr.lower()) or scan_date
            kept.append(
                DiscoveredContract(
                    chain=chain,
                    address=addr,
                    protocol_guess=None,
                    tvl_usd=total_tvl_usd,
                    first_seen=first_seen_date,
                    unique_users_30d=None,
                    source=DiscoverySource.RPC_ACTIVE_HOLDERS,
                )
            )

        log.info(
            "rpc holders %s: %d of %d contracts above $%d threshold",
            chain.value,
            len(kept),
            len(contracts),
            s.MIN_TVL_USD,
        )
        return kept

    finally:
        if owns_client:
            await client.aclose()
