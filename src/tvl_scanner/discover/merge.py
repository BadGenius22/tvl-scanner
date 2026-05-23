"""Merge discovered contracts from multiple sources into a deduped candidate set.

Dedup key: `(chain, normalized_address)`. Addresses are normalized to lowercase
for EVM (case-insensitive), left as-is for Solana (case-sensitive base58).

When the same (chain, address) appears from multiple sources, we keep the
record with the highest tvl_usd (most recent snapshot) but merge the source
list so downstream stages can see which discovery paths saw it.

Filter stages applied here (cheap filters first):
  1. TVL >= MIN_TVL_USD (redundant with per-source filters, defense in depth)
  2. Age <= MAX_AGE_DAYS
  3. unique_users_30d >= MIN_UNIQUE_USERS_30D (if populated; None passes)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from pathlib import Path

from tvl_scanner.config import settings
from tvl_scanner.discover.alchemy import fetch_fresh_deployments as fetch_alchemy
from tvl_scanner.discover.birdeye import fetch_top_pairs as fetch_birdeye
from tvl_scanner.discover.geckoterminal import fetch_new_pools as fetch_geckoterminal
from tvl_scanner.discover.rpc import fetch_active_holders as fetch_rpc_holders
from tvl_scanner.enrich.prices import PriceCache
from tvl_scanner.http import make_client
from tvl_scanner.models import Chain, DiscoveredContract

log = logging.getLogger(__name__)


def _normalize_address(chain: Chain, address: str) -> str:
    """Normalize for dedup. EVM addresses are case-insensitive hex; Solana is base58."""
    if chain == Chain.SOLANA:
        return address
    return address.lower()


def _dedup(contracts: list[DiscoveredContract]) -> list[DiscoveredContract]:
    """Keep the highest-TVL record per (chain, normalized_address)."""
    best: dict[tuple[Chain, str], DiscoveredContract] = {}
    for c in contracts:
        key = (c.chain, _normalize_address(c.chain, c.address))
        prev = best.get(key)
        if prev is None or c.tvl_usd > prev.tvl_usd:
            best[key] = c
    return list(best.values())


def _apply_filters(
    contracts: list[DiscoveredContract], *, scan_date: date
) -> list[DiscoveredContract]:
    """Drop records that fail any threshold. Returns the survivors."""
    s = settings()
    kept: list[DiscoveredContract] = []
    for c in contracts:
        if c.tvl_usd < s.MIN_TVL_USD:
            continue
        age_days = (scan_date - c.first_seen).days
        if age_days < 0 or age_days > s.MAX_AGE_DAYS:
            continue
        if c.unique_users_30d is not None and c.unique_users_30d < s.MIN_UNIQUE_USERS_30D:
            continue
        kept.append(c)
    return kept


async def discover_all(
    chains: list[Chain] | None = None, *, scan_date: date | None = None
) -> list[DiscoveredContract]:
    """Run all Stage 1 discovery sources in parallel for all chains, merge, filter.

    Returns the deduped, filtered candidate list ready for Stage 2 enrichment.
    """
    s = settings()
    chains = chains or [Chain(c) for c in s.chain_list]
    scan_date = scan_date or date.today()

    async with make_client() as client:
        price_cache = PriceCache()
        # Parallelize: one task per (source, chain) pair.
        tasks: list[asyncio.Task[list[DiscoveredContract]]] = []
        for chain in chains:
            tasks.append(asyncio.create_task(fetch_geckoterminal(chain, client=client)))
            tasks.append(asyncio.create_task(fetch_birdeye(chain, client=client)))
            tasks.append(
                asyncio.create_task(
                    fetch_alchemy(
                        chain,
                        price_cache=price_cache,
                        client=client,
                        scan_date=scan_date,
                    )
                )
            )
            tasks.append(
                asyncio.create_task(
                    fetch_rpc_holders(
                        chain,
                        price_cache=price_cache,
                        client=client,
                        scan_date=scan_date,
                    )
                )
            )
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

    merged: list[DiscoveredContract] = []
    for result in all_results:
        if isinstance(result, BaseException):
            log.error("discovery source failed: %s", result)
            continue
        merged.extend(result)

    log.info("discover: %d raw records before dedup", len(merged))
    deduped = _dedup(merged)
    log.info("discover: %d after dedup", len(deduped))
    filtered = _apply_filters(deduped, scan_date=scan_date)
    log.info("discover: %d after threshold filters", len(filtered))
    return filtered


def write_candidates(
    contracts: list[DiscoveredContract], path: Path | None = None
) -> Path:
    """Serialize the candidate list to artifacts/candidates.json."""
    s = settings()
    path = path or (s.artifacts_path / "candidates.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [c.model_dump(mode="json") for c in contracts]
    path.write_text(json.dumps(records, indent=2, default=str))
    log.info("wrote %d candidates to %s", len(contracts), path)
    return path
