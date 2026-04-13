"""Protocol-level discovery via DefiLlama catalog.

GeckoTerminal and Birdeye surface pool-style TVL (AMM liquidity), but they
miss protocols that don't have public AMM pools — lending markets, staking
contracts, leverage vaults, bridges. DefiLlama's /protocols catalog indexes
those directly by protocol identity.

This module produces EnrichedCandidate records straight from the DefiLlama
catalog, bypassing Stage 1 (which is address-based). A DefiLlama-sourced
candidate has a synthetic address `defillama:{slug}` so the rest of the
pipeline can treat it uniformly.

Filters applied at ingest:
    - tvl >= MIN_TVL_USD
    - listedAt within MAX_AGE_DAYS (if present). If missing, the protocol is
      treated as 180 days old (mid-range) — we don't know, but discarding
      would be too strict.
    - category ∈ SCANNABLE_CATEGORIES (excludes categories that are rarely
      audit-relevant: CEX, Chain, Indexer, RWA-Offchain, etc.)
    - at least one chain ∈ configured CHAINS
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import httpx

from tvl_scanner.config import settings
from tvl_scanner.enrich import bounty
from tvl_scanner.enrich.defillama import DefiLlamaCatalog
from tvl_scanner.enrich.github import enrich_repo


def _coerce_audit_count(raw: Any) -> int | None:
    """Normalize DefiLlama `audits` field (int or stringified int) → int."""
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None
from tvl_scanner.models import (
    Chain,
    DiscoverySource,
    EnrichedCandidate,
    Language,
)

log = logging.getLogger(__name__)


# DefiLlama categories worth scanning. Lending/Yield/Derivatives/CDP/Bridge/LSD
# are the obvious audit-rich classes. Everything else is skipped.
SCANNABLE_CATEGORIES: set[str] = {
    "Lending",
    "Yield",
    "Yield Aggregator",
    "Derivatives",
    "Options",
    "Options Vault",
    "Leveraged Farming",
    "Liquid Staking",
    "Liquid Restaking",
    "Staking Pool",
    "CDP",
    "Synthetics",
    "Bridge",
    "Cross Chain Bridge",
    "Cross Chain",
    "RWA Lending",
    "Privacy",
    "Insurance",
    "NFT Lending",
    "NFT Marketplace",
    "Algo-Stables",
    "Reserve Currency",
    "Restaking",
}


# DefiLlama chain name → our Chain enum
DL_CHAIN_NAMES: dict[str, Chain] = {
    "ethereum": Chain.ETHEREUM,
    "arbitrum": Chain.ARBITRUM,
    "base": Chain.BASE,
    "optimism": Chain.OPTIMISM,
    "polygon": Chain.POLYGON,
    "bsc": Chain.BSC,
    "binance": Chain.BSC,
    "solana": Chain.SOLANA,
}


CHAIN_DEFAULT_LANG: dict[Chain, Language] = {
    Chain.ETHEREUM: Language.SOLIDITY,
    Chain.ARBITRUM: Language.SOLIDITY,
    Chain.BASE: Language.SOLIDITY,
    Chain.OPTIMISM: Language.SOLIDITY,
    Chain.POLYGON: Language.SOLIDITY,
    Chain.BSC: Language.SOLIDITY,
    Chain.SOLANA: Language.RUST,
}


def _pick_primary_chain(
    protocol: dict[str, Any], configured: set[Chain]
) -> Chain | None:
    """Choose the first chain that is both in the protocol's chain list AND configured."""
    raw_chains = protocol.get("chains") or []
    if not isinstance(raw_chains, list):
        return None
    for raw in raw_chains:
        if not isinstance(raw, str):
            continue
        key = raw.strip().lower()
        mapped = DL_CHAIN_NAMES.get(key)
        if mapped is not None and mapped in configured:
            return mapped
    return None


def _extract_github_url(protocol: dict[str, Any]) -> str | None:
    gh = protocol.get("github")
    if isinstance(gh, list) and gh:
        return str(gh[0])
    if isinstance(gh, str):
        return gh
    url = protocol.get("url")
    if isinstance(url, str) and "github.com" in url:
        return url
    return None


def _audit_links(protocol: dict[str, Any]) -> list[str]:
    raw = protocol.get("audit_links") or []
    if isinstance(raw, str):
        raw = [raw]
    return [u for u in raw if isinstance(u, str) and u.startswith("http")]


def _first_seen(protocol: dict[str, Any], scan_date: date) -> date:
    """Derive a 'first seen' date from DefiLlama's `listedAt` Unix timestamp."""
    raw = protocol.get("listedAt")
    if isinstance(raw, (int, float)) and raw > 0:
        try:
            from datetime import datetime as _dt
            return _dt.fromtimestamp(float(raw)).date()
        except (ValueError, OSError):
            pass
    # Fallback: mid-range so freshness score is neutral
    return scan_date - timedelta(days=180)


def _passes_basic_filters(
    protocol: dict[str, Any],
    configured_chains: set[Chain],
    scan_date: date,
) -> tuple[bool, Chain | None, date | None]:
    """Synchronous cheap pre-filter. Returns (passes, chain, first_seen).

    Called BEFORE any HTTP work so we only spawn expensive per-protocol tasks
    for entries that actually survive category/tvl/chain/age thresholds.
    """
    s = settings()
    category = str(protocol.get("category") or "")
    if category not in SCANNABLE_CATEGORIES:
        return False, None, None

    tvl = protocol.get("tvl")
    if not isinstance(tvl, (int, float)) or tvl < s.MIN_TVL_USD:
        return False, None, None

    chain = _pick_primary_chain(protocol, configured_chains)
    if chain is None:
        return False, None, None

    first_seen = _first_seen(protocol, scan_date)
    age_days = (scan_date - first_seen).days
    if age_days < 0 or age_days > s.MAX_AGE_DAYS:
        return False, None, None

    slug = str(protocol.get("slug") or "").strip()
    if not slug:
        return False, None, None

    return True, chain, first_seen


async def _process_protocol(
    protocol: dict[str, Any],
    chain: Chain,
    first_seen: date,
    catalog: DefiLlamaCatalog,
    client: httpx.AsyncClient | None,
) -> EnrichedCandidate | None:
    """Per-protocol HTTP work: detail fetch + github enrichment + bounty match.

    Runs the expensive calls for a single protocol. Concurrently-safe; safe to
    call inside asyncio.gather with a semaphore. Returns None if any exception
    is raised during processing so the gather can keep going.
    """
    try:
        slug = str(protocol["slug"]).strip()
        name = str(protocol.get("name") or slug)
        category = str(protocol.get("category") or "")
        tvl = float(protocol["tvl"])

        # BATCH G fix #4: detail fetch for audit_count, audit_note, and
        # fallback github URL. BATCH H fix #1: this call now runs concurrently
        # with 10+ others via the outer semaphore instead of serially.
        detail = await catalog.fetch_detail(slug, client=client)

        dl_audit_count: int | None = None
        dl_audit_note: str | None = None
        if detail:
            dl_audit_count = _coerce_audit_count(detail.get("audits"))
            note_raw = detail.get("audit_note")
            if isinstance(note_raw, str) and note_raw.strip():
                dl_audit_note = note_raw.strip()
        if dl_audit_count is None:
            dl_audit_count = _coerce_audit_count(protocol.get("audits"))

        # github_url resolution: flat catalog → detail → None
        github_url = _extract_github_url(protocol)
        if not github_url and detail:
            github_url = _extract_github_url(detail)

        repo_metadata = None
        if github_url:
            repo_metadata = await enrich_repo(github_url, client=client)

        # Merge audit_links from detail with the flat catalog's set
        merged_audit_links = _audit_links(protocol)
        if detail:
            for link in _audit_links(detail):
                if link not in merged_audit_links:
                    merged_audit_links.append(link)

        languages: list[Language] = [CHAIN_DEFAULT_LANG[chain]]
        if repo_metadata and repo_metadata.languages:
            name_to_enum = {
                "solidity": Language.SOLIDITY,
                "rust": Language.RUST,
                "move": Language.MOVE,
            }
            seen: set[Language] = set(languages)
            for lang_name in repo_metadata.languages:
                mapped = name_to_enum.get(lang_name.lower())
                if mapped and mapped not in seen:
                    languages.append(mapped)
                    seen.add(mapped)

        bounty_entry = bounty.match(display_name=name, defillama_slug=slug, target_name=slug)
        bounty_program = bounty_entry.platform if bounty_entry else "none"
        bounty_url = bounty_entry.url if bounty_entry else None
        bounty_payout = bounty_entry.max_payout_usd if bounty_entry else None

        return EnrichedCandidate(
            chain=chain,
            address=f"defillama:{slug}",
            tvl_usd=tvl,
            first_seen=first_seen,
            unique_users_30d=None,
            source=DiscoverySource.DEFILLAMA_CATALOG,
            target_name=slug,
            display_name=name,
            protocol_type=f"{category} on {chain.value}",
            languages=languages,
            github_repo=(repo_metadata.url if repo_metadata and repo_metadata.exists else None),  # type: ignore[arg-type]
            loc_estimate=(repo_metadata.loc_estimate if repo_metadata else None),
            docs_url=None,  # type: ignore[arg-type]
            bounty_program=bounty_program,  # type: ignore[arg-type]
            bounty_url=bounty_url,  # type: ignore[arg-type]
            bounty_max_payout_usd=bounty_payout,
            defillama_slug=slug,
            defillama_audit_links=merged_audit_links,  # type: ignore[arg-type]
            defillama_audit_count=dl_audit_count,
            defillama_audit_note=dl_audit_note,
            github_audits_folder_exists=bool(
                repo_metadata and repo_metadata.audits_folder_exists
            ),
        )
    except Exception as exc:
        log.warning("defillama protocol discovery: skipped entry: %s", exc)
        return None


async def discover_from_defillama_catalog(
    *,
    scan_date: date | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[EnrichedCandidate]:
    """Walk the DefiLlama catalog, apply filters, produce EnrichedCandidates.

    BATCH H fix #1: detail fetch + github enrichment now run concurrently with
    semaphore-bounded parallelism (default 10). For a typical catalog pass
    with ~150 qualifying entries this drops the stage from ~5 minutes
    (serial) to ~15-20 seconds, which was by far the biggest contributor to
    the ~6-minute total scan time.
    """
    s = settings()
    scan_date = scan_date or date.today()
    configured_chains = {Chain(c) for c in s.chain_list}

    catalog = DefiLlamaCatalog()
    await catalog.load(client=client)

    if not catalog.is_loaded() or not catalog._protocols:
        return []

    # Phase 1: cheap synchronous pre-filter to find which protocols are
    # worth the expensive HTTP work. Walks all 7000+ protocols but only
    # does dict lookups and arithmetic.
    to_process: list[tuple[dict[str, Any], Chain, date]] = []
    for protocol in catalog._protocols:
        passes, chain, first_seen = _passes_basic_filters(
            protocol, configured_chains, scan_date
        )
        if passes and chain and first_seen:
            to_process.append((protocol, chain, first_seen))

    log.info(
        "defillama catalog pre-filter: %d of %d protocols qualify for enrichment",
        len(to_process),
        len(catalog._protocols),
    )

    # Phase 2: concurrent per-protocol enrichment with bounded parallelism.
    # DefiLlama doesn't document a hard rate limit but 10 concurrent is well
    # below what they throttle on in practice (we have never seen a 429 from
    # /protocols or /protocol/{slug} in real scans).
    sem = asyncio.Semaphore(10)

    async def _bounded(
        protocol: dict[str, Any], chain: Chain, first_seen: date
    ) -> EnrichedCandidate | None:
        async with sem:
            return await _process_protocol(
                protocol, chain, first_seen, catalog, client
            )

    task_results = await asyncio.gather(
        *(_bounded(p, c, fs) for (p, c, fs) in to_process)
    )

    results = [r for r in task_results if r is not None]
    log.info(
        "defillama catalog discovery: %d protocols matched filters (from %d total)",
        len(results),
        len(catalog._protocols),
    )
    return results
