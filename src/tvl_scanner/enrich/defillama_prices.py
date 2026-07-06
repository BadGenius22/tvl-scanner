"""DefiLlama token price lookup (batched).

Used by the Alchemy fresh-deployment discoverer to convert ERC20 balances
into USD values so we can threshold new contracts by actual TVL rather than
just native-token holdings.

Endpoint: `https://coins.llama.fi/prices/current/<coins>`
  Public, no API key.

Request format: `coins` is a comma-separated list of `<chain>:<address>`
pairs, e.g.:
    `ethereum:0xA0b8...48eB,arbitrum:0xFF97...CE06,base:0x833...63Bb`

Response shape:
    {
      "coins": {
        "ethereum:0xA0b8...48eB": {
          "decimals": 6,
          "symbol": "USDC",
          "price": 0.9998,
          "timestamp": 1700000000,
          "confidence": 0.99
        },
        ...
      }
    }

The response is structured exactly as we want — price + decimals in one
call, no separate metadata lookup needed. We batch up to 100 tokens per
request to stay polite on the free endpoint.

Tokens that DefiLlama doesn't recognize are silently absent from the
response; callers should treat missing entries as `None` (unknown price,
don't count toward TVL).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from tvl_scanner.http import HttpError, get_json
from tvl_scanner.models import Chain

log = logging.getLogger(__name__)


# Map our Chain enum → DefiLlama's chain slug convention. DefiLlama uses
# lowercase chain names that mostly match but differ in a few cases.
CHAIN_TO_DEFILLAMA_SLUG: dict[Chain, str] = {
    Chain.ETHEREUM: "ethereum",
    Chain.ARBITRUM: "arbitrum",
    Chain.BASE: "base",
    Chain.OPTIMISM: "optimism",
    Chain.POLYGON: "polygon",
    Chain.BSC: "bsc",
    Chain.SOLANA: "solana",
}


# DefiLlama's /prices/current endpoint accepts up to ~100 coins per request
# before the URL gets uncomfortably long. Stay well below.
BATCH_SIZE = 80


@dataclass(frozen=True)
class TokenPrice:
    """Structured price entry returned by DefiLlama."""

    symbol: str | None
    price: float
    decimals: int
    confidence: float = 1.0


def _build_coin_key(chain: Chain, token_address: str) -> str | None:
    """Build the `<chain>:<address>` key DefiLlama expects. None if not mappable."""
    slug = CHAIN_TO_DEFILLAMA_SLUG.get(chain)
    if not slug:
        return None
    return f"{slug}:{token_address.lower()}"


def _parse_coin_entry(entry: dict[str, Any]) -> TokenPrice | None:
    """Parse one DefiLlama coin response into our TokenPrice dataclass."""
    try:
        price_raw = entry.get("price")
        decimals_raw = entry.get("decimals")
        if price_raw is None or decimals_raw is None:
            return None
        return TokenPrice(
            symbol=entry.get("symbol"),
            price=float(price_raw),
            decimals=int(decimals_raw),
            confidence=float(entry.get("confidence") or 1.0),
        )
    except (TypeError, ValueError):
        return None


async def fetch_prices(
    coin_keys: list[str], *, client: httpx.AsyncClient | None = None
) -> dict[str, TokenPrice]:
    """Fetch prices for a list of `<chain>:<address>` keys. Batches automatically.

    Returns a dict mapping coin key → TokenPrice. Keys missing from the
    response (unknown tokens) are absent from the return dict — callers
    should treat absence as "unknown price, skip this token for TVL".
    """
    if not coin_keys:
        return {}

    # Dedup and sort for determinism in logs/tests
    unique = sorted(set(coin_keys))
    result: dict[str, TokenPrice] = {}

    for batch_start in range(0, len(unique), BATCH_SIZE):
        batch = unique[batch_start : batch_start + BATCH_SIZE]
        url = f"https://coins.llama.fi/prices/current/{','.join(batch)}"
        try:
            payload = await get_json(url, client=client)
        except HttpError as exc:
            log.info("defillama prices batch failed: %s", exc)
            continue

        if not isinstance(payload, dict):
            continue
        coins = payload.get("coins")
        if not isinstance(coins, dict):
            continue

        for key, entry in coins.items():
            if not isinstance(entry, dict):
                continue
            parsed = _parse_coin_entry(entry)
            if parsed:
                result[key] = parsed

    log.info(
        "defillama prices: fetched %d of %d requested tokens",
        len(result),
        len(unique),
    )
    return result
