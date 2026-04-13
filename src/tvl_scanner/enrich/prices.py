"""Native-token USD price fetcher.

Used only by the Alchemy fresh-deployment discoverer (Stage 1 batch C) to
convert `eth_getBalance` native wei into USD so we can threshold new contracts
by real-money value.

Source: Coingecko `/simple/price`, free tier (no key, 30 req/min).
Fallback: hardcoded conservative prices. Better to miss a few real candidates
than to hammer Coingecko or fail the whole scan when they rate-limit us.

All prices are cached per-process in an instance-level dict. The scanner is a
short-lived CLI so per-scan caching is sufficient.
"""

from __future__ import annotations

import logging

import httpx

from tvl_scanner.http import HttpError, get_json
from tvl_scanner.models import Chain

log = logging.getLogger(__name__)


# Chain → Coingecko coin ID for the native token. ETH is the native for all
# OP-stack and Arbitrum Nitro L2s.
CHAIN_TO_COINGECKO_ID: dict[Chain, str] = {
    Chain.ETHEREUM: "ethereum",
    Chain.ARBITRUM: "ethereum",
    Chain.BASE: "ethereum",
    Chain.OPTIMISM: "ethereum",
    Chain.POLYGON: "matic-network",
    Chain.BSC: "binancecoin",
    # Solana uses SOL but this price fetcher is for EVM fresh-deployment scoring.
    Chain.SOLANA: "solana",
}


# Conservative fallback prices. Updated manually when they drift more than ~50%
# off real values. Use these when Coingecko is unreachable or rate-limited.
# The fallback is always preferred over a hard failure because the scanner's
# threshold ($100K default) is a coarse filter — being 30% off on ETH doesn't
# move a contract in/out of the candidate set in most cases.
FALLBACK_USD: dict[Chain, float] = {
    Chain.ETHEREUM: 3000.0,
    Chain.ARBITRUM: 3000.0,
    Chain.BASE: 3000.0,
    Chain.OPTIMISM: 3000.0,
    Chain.POLYGON: 0.50,
    Chain.BSC: 500.0,
    Chain.SOLANA: 150.0,
}


class PriceCache:
    """Per-scan in-memory price cache. Instantiate once per pipeline run."""

    def __init__(self) -> None:
        self._prices: dict[Chain, float] = {}

    async def get(
        self, chain: Chain, *, client: httpx.AsyncClient | None = None
    ) -> float:
        """Return USD price for `chain`'s native token. Fetches lazily, caches."""
        if chain in self._prices:
            return self._prices[chain]

        coingecko_id = CHAIN_TO_COINGECKO_ID.get(chain)
        if not coingecko_id:
            price = FALLBACK_USD.get(chain, 0.0)
            self._prices[chain] = price
            return price

        url = "https://api.coingecko.com/api/v3/simple/price"
        try:
            payload = await get_json(
                url,
                params={"ids": coingecko_id, "vs_currencies": "usd"},
                client=client,
            )
        except HttpError as exc:
            log.info("coingecko price fetch failed for %s: %s — using fallback", coingecko_id, exc)
            price = FALLBACK_USD.get(chain, 0.0)
            self._prices[chain] = price
            return price

        if not isinstance(payload, dict):
            price = FALLBACK_USD.get(chain, 0.0)
            self._prices[chain] = price
            return price

        entry = payload.get(coingecko_id) or {}
        raw = entry.get("usd")
        if isinstance(raw, (int, float)) and raw > 0:
            price = float(raw)
        else:
            price = FALLBACK_USD.get(chain, 0.0)

        # Cache under ALL chains that use the same coingecko ID so the next
        # lookup for a different L2 with the same native asset is free.
        for ch, cid in CHAIN_TO_COINGECKO_ID.items():
            if cid == coingecko_id:
                self._prices[ch] = price

        return price
