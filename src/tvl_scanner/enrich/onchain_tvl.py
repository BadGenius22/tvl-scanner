"""On-chain TVL measurement for in-scope bounty contracts.

DefiLlama is the primary TVL source, but it silently fails in two ways that a
bounty scan cannot tolerate:

  1. **Name-match miss.** The Immunefi program name and the DefiLlama protocol
     name differ, so the lookup returns nothing. KAST is listed on DefiLlama as
     "Kast Card"; the scan searched for "KAST" and found nothing.
  2. **Tracked but unpriced.** DefiLlama carries the protocol with `tvl: null` —
     common for anything that is not a classic pool-based DeFi primitive.

Both used to collapse to `tvl_usd = 0.0`, which the report printed as a
confident "$0". That is a false statement about a live protocol, and it is
exactly backwards for target selection: value at risk is the whole point.

This module answers the question directly by reading the chain. It tries three
tiers per in-scope address, cheapest and most precise first:

  Tier 1 — ERC-4626 `totalAssets()` + `asset()`. Broad coverage (every modern
           vault) and it counts assets deployed to strategies, not just idle
           balances. Spark's sUSDC reads $181.5M this way.
  Tier 2 — `getContractValue()` + `token()`. The Idle-CDO shape, which Pareto
           Credit and its forks use; Tier 1 returns nothing for them.
  Tier 3 — Balance sweep: every non-zero ERC-20 the contract holds (via
           Alchemy's `alchemy_getTokenBalances`) plus its native balance. The
           general fallback for contracts exposing no accounting view at all.

Tier 3 measures assets *at rest*, so it undercounts a contract that has
deployed funds elsewhere. That is a floor, not a lie — and the returned method
note says which tier produced the number so a reader can judge it.

USD conversion uses DefiLlama's free `coins.llama.fi` price endpoint (no key).

Solana is deliberately NOT attempted. A program address owns no balances; value
sits in PDAs whose derivation is program-specific, so there is no general read.
Solana candidates stay unresolved rather than get a fabricated number.

Never raises: every failure path returns `None`, leaving TVL unresolved.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from tvl_scanner.config import get_secret
from tvl_scanner.http import get_json, post_json
from tvl_scanner.models import Chain

log = logging.getLogger(__name__)

# Function selectors (cast sig). All are zero-argument views returning a single
# word, so the ABI handling below is a plain 32-byte hex decode.
SEL_TOTAL_ASSETS = "0x01e1d114"  # totalAssets()      ERC-4626
SEL_ASSET = "0x38d52e0f"  # asset()            ERC-4626
SEL_GET_CONTRACT_VALUE = "0xdc82697c"  # getContractValue() Idle-CDO
SEL_TOKEN = "0xfc0c546a"  # token()            Idle-CDO
SEL_DECIMALS = "0x313ce567"  # decimals()         ERC-20

# Alchemy RPC host per chain. Solana is absent by design (see module docstring).
_ALCHEMY_HOSTS: dict[Chain, str] = {
    Chain.ETHEREUM: "eth-mainnet",
    Chain.ARBITRUM: "arb-mainnet",
    Chain.BASE: "base-mainnet",
    Chain.OPTIMISM: "opt-mainnet",
    Chain.POLYGON: "polygon-mainnet",
    Chain.BSC: "bnb-mainnet",
}

# DefiLlama's price-API chain keys. Mostly identical to our enum; `bsc` differs.
_LLAMA_PRICE_CHAINS: dict[Chain, str] = {
    Chain.ETHEREUM: "ethereum",
    Chain.ARBITRUM: "arbitrum",
    Chain.BASE: "base",
    Chain.OPTIMISM: "optimism",
    Chain.POLYGON: "polygon",
    Chain.BSC: "bsc",
}

# Wrapped-native token per chain, used to price a non-zero native balance.
_WRAPPED_NATIVE: dict[Chain, str] = {
    Chain.ETHEREUM: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    Chain.ARBITRUM: "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    Chain.BASE: "0x4200000000000000000000000000000000000006",
    Chain.OPTIMISM: "0x4200000000000000000000000000000000000006",
    Chain.POLYGON: "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
    Chain.BSC: "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
}

# A contract holding more distinct tokens than this is almost certainly a router
# or an airdrop dumping ground rather than a vault; pricing every one wastes
# calls and invites junk-token valuations.
MAX_SWEEP_TOKENS = 25

# Reject prices DefiLlama itself flags as low-confidence — that is how spam
# tokens with fabricated liquidity would otherwise inflate a sweep total.
MIN_PRICE_CONFIDENCE = 0.8

# A sweep total above this from low-quality signals is more likely a mispriced
# junk token than real TVL. Logged and discarded rather than reported.
SWEEP_SANITY_CAP_USD = 50_000_000_000.0


def _alchemy_url(chain: Chain) -> str | None:
    host = _ALCHEMY_HOSTS.get(chain)
    if host is None:
        return None
    key = get_secret("alchemy", required=False)
    if not key:
        return None
    return f"https://{host}.g.alchemy.com/v2/{key}"


def _to_int(hex_word: Any) -> int | None:
    """Decode a JSON-RPC hex quantity/word to int. None on anything unexpected."""
    if not isinstance(hex_word, str) or not hex_word.startswith("0x"):
        return None
    body = hex_word[2:]
    if not body:
        return None
    try:
        return int(body, 16)
    except ValueError:
        return None


def _to_address(hex_word: Any) -> str | None:
    """Decode an ABI-encoded address word (right-aligned in 32 bytes)."""
    if not isinstance(hex_word, str) or not hex_word.startswith("0x"):
        return None
    body = hex_word[2:]
    if len(body) < 40:
        return None
    addr = "0x" + body[-40:]
    if int(addr, 16) == 0:
        return None
    return addr


async def _eth_call(
    url: str, to: str, selector: str, *, client: httpx.AsyncClient | None
) -> str | None:
    """Single zero-arg eth_call. Returns the raw hex result, or None."""
    try:
        res = await post_json(
            url,
            json_body={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_call",
                "params": [{"to": to, "data": selector}, "latest"],
            },
            client=client,
        )
    except Exception as exc:
        log.debug("eth_call %s on %s failed: %s", selector, to, exc)
        return None
    if not isinstance(res, dict) or res.get("error"):
        return None
    out = res.get("result")
    # A reverted/absent view returns "0x" — treat as "not implemented".
    return out if isinstance(out, str) and len(out) > 2 else None


async def _fetch_prices(
    chain: Chain, tokens: list[str], *, client: httpx.AsyncClient | None
) -> dict[str, tuple[float, int]]:
    """Batch-price tokens. Returns {lowercased address: (usd_price, decimals)}."""
    llama_chain = _LLAMA_PRICE_CHAINS.get(chain)
    if not llama_chain or not tokens:
        return {}
    out: dict[str, tuple[float, int]] = {}
    # The endpoint takes a comma-joined list; chunked to keep URLs sane.
    for i in range(0, len(tokens), 25):
        chunk = tokens[i : i + 25]
        keys = ",".join(f"{llama_chain}:{t}" for t in chunk)
        try:
            res = await get_json(f"https://coins.llama.fi/prices/current/{keys}", client=client)
        except Exception as exc:
            log.debug("price fetch failed for %s: %s", keys[:80], exc)
            continue
        if not isinstance(res, dict):
            continue
        for key, val in (res.get("coins") or {}).items():
            if not isinstance(val, dict):
                continue
            price = val.get("price")
            decimals = val.get("decimals")
            confidence = val.get("confidence")
            if not isinstance(price, (int, float)) or price <= 0:
                continue
            if isinstance(confidence, (int, float)) and confidence < MIN_PRICE_CONFIDENCE:
                continue
            if not isinstance(decimals, int):
                continue
            addr = str(key).split(":", 1)[-1].lower()
            out[addr] = (float(price), decimals)
    return out


async def _measure_accounting_view(
    url: str,
    address: str,
    chain: Chain,
    *,
    client: httpx.AsyncClient | None,
) -> tuple[float, str] | None:
    """Tiers 1 and 2: ask the contract what it is worth, then price that unit."""
    for amount_sel, token_sel, tier in (
        (SEL_TOTAL_ASSETS, SEL_ASSET, "erc4626:totalAssets"),
        (SEL_GET_CONTRACT_VALUE, SEL_TOKEN, "idle-cdo:getContractValue"),
    ):
        raw_amount = _to_int(await _eth_call(url, address, amount_sel, client=client))
        if raw_amount is None or raw_amount <= 0:
            continue
        token = _to_address(await _eth_call(url, address, token_sel, client=client))
        if token is None:
            continue
        prices = await _fetch_prices(chain, [token], client=client)
        entry = prices.get(token.lower())
        if entry is None:
            # Priced unknown, but the unit count is still real — fall back to
            # the token's own decimals so a stablecoin vault is not lost.
            decimals = _to_int(await _eth_call(url, token, SEL_DECIMALS, client=client))
            if decimals is None or decimals > 36:
                continue
            log.debug("no price for %s on %s; skipping tier %s", token, chain.value, tier)
            continue
        price, decimals = entry
        if decimals > 36:
            continue
        return (raw_amount / 10**decimals) * price, tier
    return None


async def _measure_balance_sweep(
    url: str,
    address: str,
    chain: Chain,
    *,
    client: httpx.AsyncClient | None,
) -> tuple[float, str] | None:
    """Tier 3: value the ERC-20s and native balance the contract actually holds."""
    try:
        res = await post_json(
            url,
            json_body={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getTokenBalances",
                "params": [address, "erc20"],
            },
            client=client,
        )
    except Exception as exc:
        log.debug("token-balance sweep failed for %s: %s", address, exc)
        return None

    held: dict[str, int] = {}
    if isinstance(res, dict) and isinstance(res.get("result"), dict):
        for entry in res["result"].get("tokenBalances") or []:
            if not isinstance(entry, dict):
                continue
            token = entry.get("contractAddress")
            amount = _to_int(entry.get("tokenBalance"))
            if not isinstance(token, str) or amount is None or amount <= 0:
                continue
            held[token.lower()] = amount
            if len(held) >= MAX_SWEEP_TOKENS:
                break

    native_raw = _to_int(
        (
            await post_json(
                url,
                json_body={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_getBalance",
                    "params": [address, "latest"],
                },
                client=client,
            )
            or {}
        ).get("result")
    )

    price_targets = list(held)
    wrapped = _WRAPPED_NATIVE.get(chain)
    if native_raw and wrapped:
        price_targets.append(wrapped.lower())
    if not price_targets:
        return None

    prices = await _fetch_prices(chain, price_targets, client=client)
    total = 0.0
    priced = 0
    for token, amount in held.items():
        entry = prices.get(token)
        if entry is None:
            continue
        price, decimals = entry
        if decimals > 36:
            continue
        total += (amount / 10**decimals) * price
        priced += 1
    if native_raw and wrapped:
        entry = prices.get(wrapped.lower())
        if entry is not None:
            total += (native_raw / 10**18) * entry[0]
            priced += 1

    if priced == 0 or total <= 0:
        return None
    if total > SWEEP_SANITY_CAP_USD:
        log.warning(
            "on-chain sweep for %s produced an implausible $%.0f — discarding",
            address,
            total,
        )
        return None
    return total, f"balance-sweep:{priced}-tokens"


async def measure_onchain_tvl(
    chain: Chain,
    addresses: list[str],
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[float, str] | None:
    """Best-effort USD value held by `addresses` on `chain`.

    Returns (usd_total, method_note) or None when nothing could be measured.
    Sums across addresses so a protocol whose scope lists several vaults reports
    its aggregate. Solana returns None by design — see the module docstring.
    """
    if chain is Chain.SOLANA or not addresses:
        return None
    url = _alchemy_url(chain)
    if url is None:
        return None

    total = 0.0
    methods: list[str] = []
    seen: set[str] = set()
    for address in addresses:
        addr = address.strip()
        if not addr.startswith("0x") or len(addr) != 42 or addr.lower() in seen:
            continue
        seen.add(addr.lower())
        measured = await _measure_accounting_view(url, addr, chain, client=client)
        if measured is None:
            measured = await _measure_balance_sweep(url, addr, chain, client=client)
        if measured is None:
            continue
        value, tier = measured
        total += value
        methods.append(tier)

    if not methods or total <= 0:
        return None
    unique = sorted(set(methods))
    return total, f"on-chain via {', '.join(unique)} over {len(methods)}/{len(seen)} addr"
