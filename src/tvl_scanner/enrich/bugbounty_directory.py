"""Broad bug-bounty directory lookup (lissy93/bug-bounties).

The scanner's native bounty detection is Immunefi-centric: `bounty.py` (curated
seeds) + `immunefi.py` (live Immunefi catalogue). A candidate whose only bounty
lives on HackerOne, Bugcrowd, Intigriti, or a self-hosted program therefore reads
as `bounty_program: none` — a false "no payout path", which is exactly the signal
that drives target selection.

This module adds a third, broad fallback: the community-maintained
`lissy93/bug-bounties` directory (~3,000 programs across every major platform +
self-hosted). It is consulted only AFTER the curated seeds and live Immunefi both
miss, so the hand-tuned sources stay authoritative where they hit.

Matching is deliberately CONSERVATIVE to avoid false positives on a web2-heavy
directory:
  - domain match: the candidate's homepage registrable domain is in the program's
    in-scope `domains` (or equals a domain-shaped company name) — strong; or
  - exact normalized-name equality on a distinctive (len >= 5) name.

Only **paying** programs are surfaced (rewards include "Bounty"). A recognition-
only VDP is not a payout path, and tagging one as a bounty would mislead
target selection, so those are dropped.

The directory (~750 KB across two YAML files) is fetched once per process and
cached, mirroring `solana_rpc.load_sumtokens_registry`.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml

from tvl_scanner.config import settings
from tvl_scanner.enrich.bounty import BountyEntry, BountyPlatform, _normalize
from tvl_scanner.http import shared_ssl_context

log = logging.getLogger(__name__)

BASE = "https://raw.githubusercontent.com/lissy93/bug-bounties/main/"
SOURCES = ["independent-programs.yml", "platform-programs.yml"]

# url host → our BountyPlatform bucket. Anything unrecognized → "selfhosted".
_PLATFORM_HOSTS: dict[str, BountyPlatform] = {
    "immunefi.com": "immunefi",
    "hackerone.com": "hackerone",
    "hackenproof.com": "hackenproof",
    "cantina.xyz": "cantina",
    "bugcrowd.com": "bugcrowd",
    "intigriti.com": "intigriti",
}

# Company-name suffixes that are noise for name matching.
_NAME_NOISE = (
    " managed bug bounty engagement",
    " bug bounty program",
    " bug bounty",
    " vdp",
)


@dataclass(frozen=True)
class DirectoryProgram:
    name: str
    norm_names: tuple[str, ...]
    url: str
    platform: BountyPlatform
    domains: tuple[str, ...]
    pays_bounty: bool
    max_payout_usd: int | None


def _registrable_domain(value: str) -> str | None:
    """Best-effort registrable domain from a URL or bare host/domain string.

    'https://docs.0x.org/x' -> '0x.org'; 'atlan.com' -> 'atlan.com';
    '*.foo.com (excluding ...)' -> 'foo.com'. None if nothing domain-shaped.
    """
    if not value:
        return None
    v = value.strip().lower()
    # Strip wildcards, schemes, and trailing parentheticals/whitespace.
    v = v.split("(")[0].strip().lstrip("*.")
    if "://" in v or "/" in v:
        parsed = urlparse(v if "://" in v else f"//{v}", scheme="")
        host = parsed.netloc or parsed.path
        v = host.split("/")[0]
    v = v.strip().strip(".")
    if "." not in v or " " in v:
        return None
    labels = v.split(".")
    if len(labels) < 2 or any(not lbl for lbl in labels):
        return None
    return ".".join(labels[-2:])


def _platform_from_url(url: str) -> BountyPlatform:
    host = (urlparse(url).netloc or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return _PLATFORM_HOSTS.get(host, "selfhosted")


def _clean_name(company: str) -> str:
    norm = _normalize(company)
    for noise in _NAME_NOISE:
        norm = norm.replace(_normalize(noise), "")
    return norm.strip("-")


def _entry_to_program(entry: dict[str, Any]) -> DirectoryProgram | None:
    company = entry.get("company")
    url = entry.get("url")
    if not isinstance(company, str) or not isinstance(url, str):
        return None

    rewards = entry.get("rewards") or []
    pays_bounty = any(isinstance(r, str) and "bounty" in r.lower() for r in rewards)

    # Payout only trusted as USD when currency is USD or unspecified (most are).
    max_payout: int | None = None
    raw_payout = entry.get("max_payout")
    currency = entry.get("currency")
    if (
        isinstance(raw_payout, (int, float))
        and raw_payout > 0
        and (currency is None or str(currency).upper() == "USD")
    ):
        max_payout = int(raw_payout)

    platform = _platform_from_url(url)
    domains: set[str] = set()
    company_dom = _registrable_domain(company)
    if company_dom:
        domains.add(company_dom)
    # For a self-hosted program the URL host IS the protocol's own domain
    # (e.g. docs.0x.org). For a platform-hosted program the host is the platform
    # (immunefi.com / hackerone.com), which must NOT be treated as the target's
    # domain — those rely on the explicit `domains` field instead.
    if platform == "selfhosted":
        url_dom = _registrable_domain(url)
        if url_dom:
            domains.add(url_dom)
    for d in entry.get("domains") or []:
        if isinstance(d, str):
            rd = _registrable_domain(d)
            if rd:
                domains.add(rd)

    norm_names = {_clean_name(company)}
    norm_names.discard("")

    return DirectoryProgram(
        name=company,
        norm_names=tuple(norm_names),
        url=url,
        platform=platform,
        domains=tuple(sorted(domains)),
        pays_bounty=pays_bounty,
        max_payout_usd=max_payout,
    )


def build_index(documents: list[Any]) -> list[DirectoryProgram]:
    """Build the searchable program list from parsed YAML documents (pure)."""
    programs: list[DirectoryProgram] = []
    for doc in documents:
        companies = doc.get("companies") if isinstance(doc, dict) else None
        if not isinstance(companies, list):
            continue
        for entry in companies:
            if not isinstance(entry, dict):
                continue
            prog = _entry_to_program(entry)
            # Only paying programs are a payout path worth surfacing.
            if prog and prog.pays_bounty:
                programs.append(prog)
    return programs


_INDEX: list[DirectoryProgram] | None = None
_LOCK = asyncio.Lock()


def clear_cache() -> None:
    """Reset the module-level directory cache (tests)."""
    global _INDEX
    _INDEX = None


async def _fetch_yaml(url: str, client: httpx.AsyncClient | None) -> Any:
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(
            timeout=settings().HTTP_TIMEOUT_SECONDS,
            verify=shared_ssl_context(),
            follow_redirects=True,
        )
    assert client is not None
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        return yaml.safe_load(resp.text)
    except (httpx.HTTPError, yaml.YAMLError) as exc:
        log.debug("bugbounty_directory: fetch/parse failed for %s: %s", url, exc)
        return None
    finally:
        if owns_client:
            await client.aclose()


async def load_index(client: httpx.AsyncClient | None = None) -> list[DirectoryProgram]:
    """Fetch, parse, and cache the bug-bounty directory (paying programs only)."""
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    async with _LOCK:
        if _INDEX is not None:
            return _INDEX
        docs = [await _fetch_yaml(f"{BASE}{src}", client) for src in SOURCES]
        _INDEX = build_index([d for d in docs if d is not None])
        log.info("bugbounty_directory: indexed %d paying programs", len(_INDEX))
        return _INDEX


def match(
    index: list[DirectoryProgram],
    *,
    display_name: str | None = None,
    homepage_url: str | None = None,
    defillama_slug: str | None = None,
    target_name: str | None = None,
) -> DirectoryProgram | None:
    """Conservative match: homepage-domain equality, else distinctive exact name.

    Domain match is preferred (strongest signal). Name match requires exact
    normalized equality on a name of length >= 5 to avoid false positives on a
    web2-heavy directory (short/generic names like '0x' or 'save' only match by
    domain).
    """
    cand_domain = _registrable_domain(homepage_url) if homepage_url else None
    cand_names = {
        _normalize(x) for x in (display_name, defillama_slug, target_name) if x
    }

    name_hit: DirectoryProgram | None = None
    for prog in index:
        if cand_domain and cand_domain in prog.domains:
            return prog  # strongest signal — return immediately
        if name_hit is None:
            for nm in prog.norm_names:
                if len(nm) >= 5 and nm in cand_names:
                    name_hit = prog
                    break
    return name_hit


async def match_directory(
    *,
    display_name: str | None = None,
    homepage_url: str | None = None,
    defillama_slug: str | None = None,
    target_name: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> BountyEntry | None:
    """Directory lookup returning a `bounty.BountyEntry` (drop-in for callers)."""
    index = await load_index(client)
    prog = match(
        index,
        display_name=display_name,
        homepage_url=homepage_url,
        defillama_slug=defillama_slug,
        target_name=target_name,
    )
    if prog is None:
        return None
    return BountyEntry(
        name=prog.name,
        slugs=(),
        platform=prog.platform,
        url=prog.url,
        max_payout_usd=prog.max_payout_usd,
    )
