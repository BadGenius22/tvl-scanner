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

log = logging.getLogger(__name__)


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

    def lookup(self, query: str) -> dict[str, Any] | None:
        """Return the best-matching protocol entry for `query`, or None.

        Match priority:
          1. Exact slug match (`slug == slugify(query)`)
          2. Exact name match (`name == query`, case-insensitive)
          3. Slug prefix match (`slug.startswith(slugify(query))`)
          4. Substring name match (`query in name`, case-insensitive)
        """
        if not self._loaded or not self._protocols or not query:
            return None

        q_slug = _slugify(query)
        q_lower = query.lower().strip()

        exact_slug: dict[str, Any] | None = None
        exact_name: dict[str, Any] | None = None
        prefix_slug: dict[str, Any] | None = None
        substring_name: dict[str, Any] | None = None

        for p in self._protocols:
            slug = str(p.get("slug") or "").lower()
            name = str(p.get("name") or "").lower()
            if slug == q_slug and exact_slug is None:
                exact_slug = p
            if name == q_lower and exact_name is None:
                exact_name = p
            if slug.startswith(q_slug) and q_slug and prefix_slug is None:
                prefix_slug = p
            if q_lower in name and q_lower and substring_name is None:
                substring_name = p

        return exact_slug or exact_name or prefix_slug or substring_name

    def is_loaded(self) -> bool:
        return self._loaded
