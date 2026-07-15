"""Live Immunefi bounty lookup.

Complements the curated ``bounty_registry.yaml`` (``enrich/bounty.py``): fetches
the LIVE Immunefi public bounty catalogue and matches a candidate against it by

  1. in-scope contract ADDRESS — definitive; the candidate's deployed contract
     is literally listed in an Immunefi program's scope, or
  2. protocol name / slug.

This catches bounties that are NOT in the curated seeds file — the case that
matters for the hunt: surfacing an under-audited candidate that *also* has a
live payout. The catalogue is fetched once per scan and indexed for O(1) lookup.
Best-effort: any fetch/parse failure returns empty so a scan never aborts on it.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from tvl_scanner.http import get_json

log = logging.getLogger(__name__)

IMMUNEFI_BOUNTIES_URL = "https://immunefi.com/public-api/bounties.json"
_ADDR_RE = re.compile(r"0x[a-fA-F0-9]{40}")


def _norm(s: str) -> str:
    return s.strip().lower().replace(" ", "-")


@dataclass(frozen=True)
class ImmunefiProgram:
    slug: str
    project: str
    max_payout_usd: int | None
    kyc: bool
    url: str
    name_keys: frozenset[str]
    addresses: frozenset[str]


@dataclass(frozen=True)
class ImmunefiMatch:
    slug: str
    url: str
    max_payout_usd: int | None
    kyc: bool
    reason: str  # "address" (definitive) | "name"


@dataclass
class ImmunefiIndex:
    """O(1) lookup built once from the live catalogue."""

    by_address: dict[str, ImmunefiProgram]
    by_name: dict[str, ImmunefiProgram]


def parse_program(raw: dict[str, Any]) -> ImmunefiProgram | None:
    """Parse one bounties.json entry into an ImmunefiProgram. None if unusable."""
    slug = raw.get("slug")
    if not slug:
        return None
    addresses: set[str] = set()
    for asset in raw.get("assets") or []:
        if not isinstance(asset, dict) or asset.get("type") != "smart_contract":
            continue
        addresses.update(m.lower() for m in _ADDR_RE.findall(str(asset.get("url") or "")))
    name_keys = {_norm(str(slug))}
    if raw.get("project"):
        name_keys.add(_norm(str(raw["project"])))
    max_bounty = raw.get("maxBounty")
    return ImmunefiProgram(
        slug=str(slug),
        project=str(raw.get("project") or slug),
        max_payout_usd=int(max_bounty) if isinstance(max_bounty, (int, float)) else None,
        kyc=bool(raw.get("kyc")),
        url=f"https://immunefi.com/bug-bounty/{slug}",
        name_keys=frozenset(name_keys),
        addresses=frozenset(addresses),
    )


async def fetch_programs(client: httpx.AsyncClient | None = None) -> list[ImmunefiProgram]:
    """Fetch + parse the live Immunefi catalogue. Returns [] on any failure —
    bounty enrichment is best-effort and must never abort a scan.
    """
    try:
        data = await get_json(IMMUNEFI_BOUNTIES_URL, client=client)
    except Exception as exc:  # best-effort; log and degrade to [] so a scan never aborts
        log.warning("immunefi catalogue fetch failed: %s", exc)
        return []
    rows: Any = data if isinstance(data, list) else (data.get("bounties") if isinstance(data, dict) else None)
    if not isinstance(rows, list):
        log.warning("immunefi catalogue: unexpected shape %s", type(data).__name__)
        return []
    programs = [p for r in rows if isinstance(r, dict) and (p := parse_program(r)) is not None]
    log.info("loaded %d immunefi programs (live catalogue)", len(programs))
    return programs


def build_index(programs: list[ImmunefiProgram]) -> ImmunefiIndex:
    by_address: dict[str, ImmunefiProgram] = {}
    by_name: dict[str, ImmunefiProgram] = {}
    for p in programs:
        for addr in p.addresses:
            by_address.setdefault(addr, p)
        for key in p.name_keys:
            by_name.setdefault(key, p)
    return ImmunefiIndex(by_address=by_address, by_name=by_name)


def _to_match(p: ImmunefiProgram, reason: str) -> ImmunefiMatch:
    return ImmunefiMatch(
        slug=p.slug, url=p.url, max_payout_usd=p.max_payout_usd, kyc=p.kyc, reason=reason
    )


def match(
    index: ImmunefiIndex,
    *,
    address: str | None = None,
    display_name: str | None = None,
    defillama_slug: str | None = None,
    target_name: str | None = None,
) -> ImmunefiMatch | None:
    """Match a candidate to a live Immunefi program. Address match (definitive)
    is tried first, then name/slug. None if no match.
    """
    if address:
        p = index.by_address.get(address.lower())
        if p is not None:
            return _to_match(p, "address")
    for raw in (display_name, defillama_slug, target_name):
        if raw:
            p = index.by_name.get(_norm(raw))
            if p is not None:
                return _to_match(p, "name")
    return None
