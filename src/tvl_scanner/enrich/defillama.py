"""DefiLlama protocol identification and metadata enrichment.

DefiLlama's `/protocols` endpoint returns the full protocol catalog (~2000 entries).
We fetch it once per scan, cache in-memory, and match discovered contracts by
the discovery-time `protocol_guess` string (usually a DEX/dex-like name from
GeckoTerminal). Matching is name-similarity based with a simple slug heuristic.

DefiLlama fields we care about for enrichment:
    slug, name, category, description, url, github, audit_links, audits, logo

DefiLlama is SUPPLEMENTARY for the scanner: the scanner's goal is to find
protocols that DefiLlama may have missed or never indexed. A match gives us
metadata; a miss is a signal that the target is potentially under-audited.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from tvl_scanner.config import settings
from tvl_scanner.http import get_json
from tvl_scanner.models import Chain

log = logging.getLogger(__name__)

# DefiLlama `chains` / `chainTvls` keys that mean one of our Chain values.
# Keep this local so lookup can stay chain-aware without importing the
# catalog-path helpers (those import this module).
_CHAIN_ALIASES: dict[Chain, frozenset[str]] = {
    Chain.ETHEREUM: frozenset({"ethereum"}),
    Chain.ARBITRUM: frozenset({"arbitrum"}),
    Chain.BASE: frozenset({"base"}),
    Chain.OPTIMISM: frozenset({"optimism"}),
    Chain.POLYGON: frozenset({"polygon", "matic"}),
    Chain.BSC: frozenset({"bsc", "binance"}),
    Chain.SOLANA: frozenset({"solana"}),
}


def _protocol_chain_names(protocol: dict[str, Any]) -> set[str]:
    """Lowercased chain names DefiLlama published for this row."""
    names: set[str] = set()
    raw_chains = protocol.get("chains") or []
    if isinstance(raw_chains, list):
        names.update(
            c.strip().lower() for c in raw_chains if isinstance(c, str) and c.strip()
        )
    raw_ct = protocol.get("chainTvls")
    if isinstance(raw_ct, dict):
        for key in raw_ct:
            if isinstance(key, str) and key.strip() and "-" not in key:
                names.add(key.strip().lower())
    names -= {"borrowed", "pool2", "staking"}
    return names


def _touches_chain(protocol: dict[str, Any], chain: Chain) -> bool:
    return bool(_protocol_chain_names(protocol) & _CHAIN_ALIASES[chain])


_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    """Normalize a protocol name for comparison. Matches DefiLlama slug style loosely."""
    return _SLUG_CLEAN.sub("-", name.lower()).strip("-")


class DefiLlamaCatalog:
    """In-memory cache of the DefiLlama protocol catalog.

    Instantiate once per scan, call `load()`, then `lookup()` repeatedly.
    `lookup()` is O(catalog_size) per call, which is fine for v1 (~2000 entries
    × ~50 candidates = 100k comparisons, still sub-second).
    """

    def __init__(self) -> None:
        self._protocols: list[dict[str, Any]] = []
        self._loaded = False
        self._detail_cache: dict[str, dict[str, Any] | None] = {}

    async def load(self, *, client: httpx.AsyncClient | None = None) -> None:
        s = settings()
        url = f"{s.DEFILLAMA_BASE}/protocols"
        try:
            payload = await get_json(url, client=client)
        except Exception as exc:
            log.error("DefiLlama catalog fetch failed: %s", exc)
            self._protocols = []
            self._loaded = True
            return

        if isinstance(payload, list):
            self._protocols = payload
        else:
            self._protocols = []
        self._loaded = True
        log.info("DefiLlama catalog loaded: %d protocols", len(self._protocols))

    async def fetch_detail(
        self, slug: str, *, client: httpx.AsyncClient | None = None
    ) -> dict[str, Any] | None:
        """Fetch `/protocol/{slug}` detail endpoint. Cached per slug per catalog.

        Returns the raw JSON response as a dict. The detail endpoint has
        `audits` as a count (may be string "2" or int 2), `audit_note` as
        free-form text, and expanded `audit_links`.

        Returns None on HTTP failure — caller should treat missing detail as
        "no additional audit signal" rather than an error.
        """
        if slug in self._detail_cache:
            return self._detail_cache[slug]

        s = settings()
        url = f"{s.DEFILLAMA_BASE}/protocol/{slug}"
        try:
            payload = await get_json(url, client=client)
        except Exception as exc:
            log.debug("DefiLlama detail fetch failed for %s: %s", slug, exc)
            self._detail_cache[slug] = None
            return None

        if isinstance(payload, dict):
            self._detail_cache[slug] = payload
            return payload
        self._detail_cache[slug] = None
        return None

    def lookup(
        self, query: str, *, prefer_chain: Chain | None = None
    ) -> dict[str, Any] | None:
        """Return the best-matching protocol entry for `query`, or None.

        Match priority:
          1. Exact slug match (`slug == slugify(query)`)
          2. Exact name match (`name == query`, case-insensitive)
          3. Slug prefix match (`slug.startswith(slugify(query))`)
          4. Substring name match (`query in name`, case-insensitive)

        When `prefer_chain` is set, each tier prefers a row that actually
        lists that chain. Prefix/substring hits on the *wrong* chain are
        dropped rather than returned: that is how `lookup("katana")` bound
        an Ethereum Immunefi program to Solana Katana, and `lookup("trufin")`
        bound TruYields to `trufin-legacy-vaults` ($7 on Ethereum). Exact
        slug/name still return a wrong-chain row when it is the only exact
        match — the caller then leaves TVL unresolved instead of inventing a
        weaker name hit.
        """
        if not self._loaded or not self._protocols or not query:
            return None

        q_slug = _slugify(query)
        q_lower = query.lower().strip()

        exact_slugs: list[dict[str, Any]] = []
        exact_names: list[dict[str, Any]] = []
        prefix_slugs: list[dict[str, Any]] = []
        substring_names: list[dict[str, Any]] = []

        for p in self._protocols:
            slug = str(p.get("slug") or "").lower()
            name = str(p.get("name") or "").lower()
            if slug == q_slug:
                exact_slugs.append(p)
            elif name == q_lower:
                exact_names.append(p)
            elif q_slug and slug.startswith(q_slug):
                prefix_slugs.append(p)
            elif q_lower and q_lower in name:
                substring_names.append(p)

        def _pick(
            matches: list[dict[str, Any]], *, weak: bool
        ) -> dict[str, Any] | None:
            if not matches:
                return None
            if prefer_chain is None:
                return matches[0]
            on_chain = [p for p in matches if _touches_chain(p, prefer_chain)]
            if on_chain:
                return on_chain[0]
            return None if weak else matches[0]

        return (
            _pick(exact_slugs, weak=False)
            or _pick(exact_names, weak=False)
            or _pick(prefix_slugs, weak=True)
            or _pick(substring_names, weak=True)
        )

    def is_loaded(self) -> bool:
        return self._loaded
