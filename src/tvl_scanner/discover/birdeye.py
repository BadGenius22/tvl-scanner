"""Birdeye token/pair discovery.

Birdeye's public API requires an API key in the `X-API-KEY` header and the
chain in the `x-chain` header. Free tier is ~30 req/min, so each run should
stay well under that bound — we make a single paginated call per chain.

Endpoint: `/defi/v3/pair/list` (preferred when available) or `/defi/tokenlist`
(fallback). Chain header values are lowercase canonical: `solana`, `ethereum`,
`arbitrum`, `base`, `bsc`, `optimism`, `polygon`.

Birdeye's strength vs GeckoTerminal is Solana depth. On EVM chains we keep
calls lean (one page) since GeckoTerminal already covers them well.
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


def _parse_pair(pair: dict, chain: Chain) -> DiscoveredContract | None:
    """Parse one pair/pool record. Returns None if below threshold or malformed."""
    s = settings()
    try:
        address = pair.get("address") or pair.get("pool_address") or pair.get("id")
        liquidity = pair.get("liquidity") or pair.get("liquidity_usd") or pair.get("tvl")
        created_at_raw = (
            pair.get("created_at")
            or pair.get("createdAt")
            or pair.get("created_time")
            or pair.get("first_traded_at")
        )
        if not address or liquidity is None:
            return None

        tvl_usd = float(liquidity)
        if tvl_usd < s.MIN_TVL_USD:
            return None

        if isinstance(created_at_raw, (int, float)):
            # Unix timestamp
            first_seen = datetime.fromtimestamp(float(created_at_raw)).date()
        elif isinstance(created_at_raw, str):
            first_seen = datetime.fromisoformat(
                created_at_raw.replace("Z", "+00:00")
            ).date()
        else:
            # No reliable creation date — skip so the freshness filter has real data
            return None

        dex_name = pair.get("source") or pair.get("dex") or pair.get("exchange")
        protocol_guess = str(dex_name) if dex_name else None

        return DiscoveredContract(
            chain=chain,
            address=str(address),
            protocol_guess=protocol_guess,
            tvl_usd=tvl_usd,
            first_seen=first_seen,
            unique_users_30d=None,  # Birdeye pair list does not expose user counts
            source=DiscoverySource.BIRDEYE,
        )
    except (ValueError, TypeError, KeyError) as exc:
        log.warning("Birdeye: failed to parse pair: %s", exc)
        return None


async def fetch_top_pairs(
    chain: Chain, *, client: httpx.AsyncClient | None = None, limit: int = 100
) -> list[DiscoveredContract]:
    """Fetch top pairs by liquidity on `chain` from Birdeye.

    Silently returns [] if the Birdeye API key is not configured — this makes
    Birdeye an optional enhancement, not a hard dependency. GeckoTerminal still
    provides full coverage if Birdeye is skipped.
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
    url = f"{s.BIRDEYE_BASE}/defi/v3/pair/list"

    try:
        payload = await get_json(
            url,
            params={"sort_by": "liquidity", "sort_type": "desc", "limit": limit, "offset": 0},
            headers=headers,
            client=client,
        )
    except Exception as exc:
        log.error("Birdeye fetch failed for %s: %s", chain.value, exc)
        return []

    # Response shape varies by Birdeye API version. Be defensive.
    raw_pairs: list[dict] = []
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            raw_pairs = data.get("items") or data.get("pairs") or []
        elif isinstance(data, list):
            raw_pairs = data
    elif isinstance(payload, list):
        raw_pairs = payload

    results: list[DiscoveredContract] = []
    for pair in raw_pairs:
        if len(results) >= s.MAX_CANDIDATES_PER_SOURCE:
            break
        rec = _parse_pair(pair, chain)
        if rec:
            results.append(rec)

    log.info("Birdeye %s: %d pairs above $%d threshold", chain.value, len(results), s.MIN_TVL_USD)
    return results
