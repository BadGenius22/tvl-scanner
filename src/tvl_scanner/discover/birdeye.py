"""Birdeye new-listing token discovery.

Birdeye's public API requires an API key in the `X-API-KEY` header and the
chain in the `x-chain` header. Free tier is ~30 req/min, so each run should
stay well under that bound — we make a single call per chain.

Endpoint: `/defi/v2/tokens/new_listing` — returns recently-listed tokens
(within the requested time window) with liquidity, creation time, and source.
Chain header values are lowercase canonical: `solana`, `ethereum`, `arbitrum`,
`base`, `bsc`, `optimism`, `polygon`.

BATCH G FIX #1: v1 used `/defi/v3/pair/list` which returned HTTP 404 on every
call — that endpoint path does not exist in Birdeye's public API. Switched
to `new_listing` which is documented and stable.

Birdeye's strength vs GeckoTerminal is Solana depth, especially for fresh
tokens. On EVM chains we still call it but expect fewer useful results since
most EVM fresh-pool discovery flows through GeckoTerminal.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from tvl_scanner.config import get_secret, settings
from tvl_scanner.http import get_json
from tvl_scanner.models import Chain, DiscoveredContract, DiscoverySource

log = logging.getLogger(__name__)


CHAIN_TO_BIRDEYE: dict[Chain, str] = {
    Chain.SOLANA: "solana",
    Chain.ETHEREUM: "ethereum",
    Chain.ARBITRUM: "arbitrum",
    Chain.BASE: "base",
    Chain.BSC: "bsc",
    Chain.OPTIMISM: "optimism",
    Chain.POLYGON: "polygon",
}


def _parse_token(item: dict, chain: Chain) -> DiscoveredContract | None:
    """Parse one new_listing token record. Returns None if below threshold or malformed.

    Field names are defensive — Birdeye has historically changed field names
    across API versions without migration paths. Try multiple keys for each
    logical field.
    """
    s = settings()
    try:
        address = (
            item.get("address")
            or item.get("tokenAddress")
            or item.get("mint")
        )
        liquidity = (
            item.get("liquidity")
            or item.get("liquidityUSD")
            or item.get("liquidity_usd")
            or item.get("tvl")
        )
        created_at_raw = (
            item.get("liquidityAddedAt")
            or item.get("createdAt")
            or item.get("created_at")
            or item.get("createdTime")
            or item.get("created_time")
        )
        if not address or liquidity is None:
            return None

        tvl_usd = float(liquidity)
        if tvl_usd < s.MIN_TVL_USD:
            return None

        if isinstance(created_at_raw, (int, float)):
            first_seen = datetime.fromtimestamp(float(created_at_raw)).date()
        elif isinstance(created_at_raw, str):
            first_seen = datetime.fromisoformat(
                created_at_raw.replace("Z", "+00:00")
            ).date()
        else:
            return None

        symbol = item.get("symbol") or item.get("name")
        source_name = item.get("source") or item.get("dex") or item.get("exchange")
        # Prefer the DEX source as protocol_guess if available; fall back to
        # the token symbol so downstream name-matching has something to use.
        protocol_guess = str(source_name) if source_name else (str(symbol) if symbol else None)

        return DiscoveredContract(
            chain=chain,
            address=str(address),
            protocol_guess=protocol_guess,
            tvl_usd=tvl_usd,
            first_seen=first_seen,
            unique_users_30d=None,
            source=DiscoverySource.BIRDEYE,
        )
    except (ValueError, TypeError, KeyError) as exc:
        log.warning("Birdeye: failed to parse item: %s", exc)
        return None


async def fetch_top_pairs(
    chain: Chain, *, client: httpx.AsyncClient | None = None, limit: int = 20
) -> list[DiscoveredContract]:
    """Fetch recently-listed tokens above the TVL threshold from Birdeye.

    Silently returns [] if the Birdeye API key is not configured — this makes
    Birdeye an optional enhancement, not a hard dependency. GeckoTerminal still
    provides full coverage if Birdeye is skipped.

    Note: function name is historical (`fetch_top_pairs`). It now actually
    queries the `/defi/v2/tokens/new_listing` endpoint which returns TOKENS
    not pairs. The naming is preserved to avoid touching every import site.
    """
    s = settings()
    if chain not in CHAIN_TO_BIRDEYE:
        log.info("Birdeye does not support chain %s", chain.value)
        return []

    api_key = get_secret("birdeye", required=False)
    if not api_key:
        log.info("Birdeye skipped: no API key in pass store")
        return []

    headers = {
        "X-API-KEY": api_key,
        "x-chain": CHAIN_TO_BIRDEYE[chain],
        "accept": "application/json",
    }
    url = f"{s.BIRDEYE_BASE}/defi/v2/tokens/new_listing"

    try:
        payload = await get_json(
            url,
            params={"limit": limit},
            headers=headers,
            client=client,
        )
    except Exception as exc:
        log.error("Birdeye fetch failed for %s: %s", chain.value, exc)
        return []

    # Response shape varies by Birdeye API version. Be defensive.
    raw_items: list[dict] = []
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            raw_items = data.get("items") or data.get("tokens") or data.get("pairs") or []
        elif isinstance(data, list):
            raw_items = data
    elif isinstance(payload, list):
        raw_items = payload

    results: list[DiscoveredContract] = []
    for item in raw_items:
        if len(results) >= s.MAX_CANDIDATES_PER_SOURCE:
            break
        rec = _parse_token(item, chain)
        if rec:
            results.append(rec)

    log.info(
        "Birdeye %s: %d new listings above $%d threshold",
        chain.value,
        len(results),
        s.MIN_TVL_USD,
    )
    return results
