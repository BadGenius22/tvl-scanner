"""GeckoTerminal new-pools discovery.

Public API, no key required. Response is JSON:API format — top-level `data` is
a list of pool resources, each with `attributes` and `relationships`.

Endpoint: https://api.geckoterminal.com/api/v2/networks/{network}/new_pools

Chain slug mapping (GeckoTerminal uses its own network identifiers):
    ethereum → eth
    arbitrum → arbitrum
    base → base
    optimism → optimism
    polygon → polygon_pos
    bsc → bsc
    solana → solana

Only pools with `reserve_in_usd` >= min_tvl are yielded. Pagination is capped
at `max_candidates_per_source` (from settings) to bound API spend.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from tvl_scanner.config import settings
from tvl_scanner.http import get_json
from tvl_scanner.models import Chain, DiscoveredContract, DiscoverySource

log = logging.getLogger(__name__)


CHAIN_TO_GT_NETWORK: dict[Chain, str] = {
    Chain.ETHEREUM: "eth",
    Chain.ARBITRUM: "arbitrum",
    Chain.BASE: "base",
    Chain.OPTIMISM: "optimism",
    Chain.POLYGON: "polygon_pos",
    Chain.BSC: "bsc",
    Chain.SOLANA: "solana",
}


def _parse_pool_attributes(
    attrs: dict[str, Any], chain: Chain, dex_slug: str | None
) -> DiscoveredContract | None:
    """Parse one pool record. Returns None if the record is malformed or below threshold."""
    s = settings()
    try:
        address = attrs.get("address")
        reserve_usd_raw = attrs.get("reserve_in_usd")
        created_at_raw = attrs.get("pool_created_at")
        if not address or reserve_usd_raw is None or created_at_raw is None:
            return None

        tvl_usd = float(reserve_usd_raw)
        if tvl_usd < s.MIN_TVL_USD:
            return None

        first_seen = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00")).date()

        # Unique users estimate from h24 buyers + sellers, scaled up as a rough
        # proxy for 30d activity. NOT exact — GT doesn't expose 30d unique users
        # on this endpoint. Used only for the "dead TVL ghost" filter.
        tx = attrs.get("transactions") or {}
        h24 = tx.get("h24") or {}
        buyers = int(h24.get("buyers") or 0)
        sellers = int(h24.get("sellers") or 0)
        unique_users_30d = (buyers + sellers) * 30

        return DiscoveredContract(
            chain=chain,
            address=address,
            protocol_guess=dex_slug,
            tvl_usd=tvl_usd,
            first_seen=first_seen,
            unique_users_30d=unique_users_30d,
            source=DiscoverySource.GECKOTERMINAL,
        )
    except (ValueError, TypeError, KeyError) as exc:
        log.warning("GeckoTerminal: failed to parse pool: %s", exc)
        return None


def _extract_dex_slug(pool: dict[str, Any], included: list[dict[str, Any]]) -> str | None:
    """Pull the DEX name from JSON:API `included` relationships, if present."""
    rel = (pool.get("relationships") or {}).get("dex") or {}
    dex_data = rel.get("data") or {}
    dex_id = dex_data.get("id")
    if not dex_id:
        return None
    for item in included:
        if item.get("id") == dex_id and item.get("type") == "dex":
            name = (item.get("attributes") or {}).get("name")
            return str(name) if name else str(dex_id)
    return str(dex_id)


async def fetch_new_pools(
    chain: Chain, *, client: httpx.AsyncClient | None = None
) -> list[DiscoveredContract]:
    """Fetch recently-created pools on `chain` above the TVL threshold.

    GeckoTerminal's new_pools endpoint returns ~20 pools per page. We iterate
    pages until either we've hit max_candidates_per_source or the API returns
    an empty page.
    """
    s = settings()
    if chain not in CHAIN_TO_GT_NETWORK:
        log.warning("GeckoTerminal does not support chain %s", chain.value)
        return []

    network = CHAIN_TO_GT_NETWORK[chain]
    url = f"{s.GECKOTERMINAL_BASE}/networks/{network}/new_pools"
    results: list[DiscoveredContract] = []
    page = 1

    while len(results) < s.MAX_CANDIDATES_PER_SOURCE:
        try:
            payload = await get_json(
                url,
                params={"page": page, "include": "dex"},
                client=client,
            )
        except Exception as exc:
            log.error("GeckoTerminal fetch failed (page %d, %s): %s", page, network, exc)
            break

        data = payload.get("data") or []
        included = payload.get("included") or []
        if not data:
            break

        for pool in data:
            attrs = pool.get("attributes") or {}
            dex_slug = _extract_dex_slug(pool, included)
            rec = _parse_pool_attributes(attrs, chain, dex_slug)
            if rec:
                results.append(rec)
                if len(results) >= s.MAX_CANDIDATES_PER_SOURCE:
                    break

        if len(data) < 20:  # last page
            break
        page += 1

    log.info("GeckoTerminal %s: %d pools above $%d threshold", network, len(results), s.MIN_TVL_USD)
    return results
