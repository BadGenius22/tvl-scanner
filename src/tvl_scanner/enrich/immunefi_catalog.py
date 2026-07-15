"""Bounty-first discovery via the live Immunefi catalogue.

The pool-based (Stage 1) and DefiLlama-catalog paths discover protocols by TVL
and then *tag* whichever ones happen to have a bug bounty (see enrich/immunefi.py).
That answers "of the protocols I found, which have a bounty?" — but it is blind to
any active bounty whose protocol the TVL/pool discovery never surfaces.

This module inverts that: it seeds a candidate from EVERY active Immunefi program,
so the whole live bounty universe gets ranked by the same priority formula. It is
the discovery source behind the `immunefi-scan` command.

Immunefi's own catalogue already carries most of what enrichment normally has to
go fetch: the bounty (payout, KYC, url), the in-scope contract addresses (chain
inferred from the explorer domain), the github repo, the languages, and the prior-
audit record. We resolve only two things ourselves, both best-effort and reusing
existing helpers:
  - TVL + category, by matching the program name/slug against the DefiLlama catalog
  - the TRUE deploy date, via Etherscan (enrich/etherscan.py) for EVM addresses

A program with no in-scope contract on a supported chain (Primacy-of-Impact-only,
or an ecosystem entirely outside our Chain enum) is skipped and counted, never
silently dropped.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import httpx

from tvl_scanner.enrich import immunefi
from tvl_scanner.enrich.defillama import DefiLlamaCatalog
from tvl_scanner.enrich.defillama_protocols import CHAIN_DEFAULT_LANG
from tvl_scanner.enrich.etherscan import fetch_creation_dates_batch
from tvl_scanner.models import (
    Chain,
    DiscoverySource,
    EnrichedCandidate,
    Language,
)

log = logging.getLogger(__name__)

ALL_CHAINS: set[Chain] = set(Chain)

# Explorer domain → Chain. Checked in order: an L2 explorer whose domain embeds a
# more generic one (optimistic.etherscan.io) must be matched before the generic
# suffix (etherscan.io), which therefore stays LAST.
_EXPLORER_CHAINS: list[tuple[str, Chain]] = [
    ("optimistic.etherscan.io", Chain.OPTIMISM),
    ("arbiscan.io", Chain.ARBITRUM),
    ("basescan.org", Chain.BASE),
    ("polygonscan.com", Chain.POLYGON),
    ("bscscan.com", Chain.BSC),
    ("solscan.io", Chain.SOLANA),
    ("explorer.solana.com", Chain.SOLANA),
    ("solana.fm", Chain.SOLANA),
    ("etherscan.io", Chain.ETHEREUM),
]

# Non-mainnet explorer subdomains — never treat these as a mainnet target.
_TESTNET_MARKERS: tuple[str, ...] = (
    "sepolia.",
    "goerli.",
    "hoodi.",
    "holesky.",
    "testnet.",
    "-testnet",
    "mumbai.",
)

# Immunefi `ecosystem` label → Chain (fallback when no in-scope address resolves).
_ECOSYSTEM_CHAINS: dict[str, Chain] = {
    "eth": Chain.ETHEREUM,
    "ethereum": Chain.ETHEREUM,
    "arbitrum": Chain.ARBITRUM,
    "base": Chain.BASE,
    "optimism": Chain.OPTIMISM,
    "op mainnet": Chain.OPTIMISM,
    "polygon": Chain.POLYGON,
    "polygon pos": Chain.POLYGON,
    "matic": Chain.POLYGON,
    "bnb chain": Chain.BSC,
    "bnb smart chain": Chain.BSC,
    "bsc": Chain.BSC,
    "binance": Chain.BSC,
    "solana": Chain.SOLANA,
}

_LANG_NAMES: dict[str, Language] = {
    "solidity": Language.SOLIDITY,
    "rust": Language.RUST,
    "move": Language.MOVE,
    "vyper": Language.SOLIDITY,
}


def _is_testnet(url: str) -> bool:
    u = url.lower()
    return any(m in u for m in _TESTNET_MARKERS)


def _chain_from_explorer(url: str) -> Chain | None:
    u = url.lower()
    for marker, chain in _EXPLORER_CHAINS:
        if marker in u:
            return chain
    return None


def _pick_scope(
    program: dict[str, Any], configured: set[Chain]
) -> tuple[Chain | None, str | None, int]:
    """Choose a representative in-scope contract for a program.

    Returns (chain, evm_address_or_None, in_scope_contract_count). Prefers the
    first smart-contract asset with a real EVM address on a configured chain
    (so its deploy date can be resolved); falls back to the first configured
    chain seen among the scope assets even without an extractable address.
    """
    evm_hit: tuple[Chain, str] | None = None
    chain_seen: Chain | None = None
    count = 0
    for asset in program.get("assets") or []:
        if not isinstance(asset, dict) or asset.get("type") != "smart_contract":
            continue
        url = str(asset.get("url") or "")
        # Primacy-of-Impact placeholder assets point at immunefi.com, not a contract.
        if not url or "immunefi.com" in url:
            continue
        count += 1
        if _is_testnet(url):
            continue
        chain = _chain_from_explorer(url)
        if chain is None or chain not in configured:
            continue
        if chain_seen is None:
            chain_seen = chain
        if evm_hit is None and chain != Chain.SOLANA:
            m = immunefi._ADDR_RE.search(url)
            if m:
                evm_hit = (chain, m.group(0))
    if evm_hit is not None:
        return evm_hit[0], evm_hit[1], count
    return chain_seen, None, count


def _ecosystem_chain(program: dict[str, Any], configured: set[Chain]) -> Chain | None:
    for raw in program.get("ecosystem") or []:
        chain = _ECOSYSTEM_CHAINS.get(str(raw).strip().lower())
        if chain is not None and chain in configured:
            return chain
    return None


def _launch_date(program: dict[str, Any], scan_date: date) -> date:
    raw = program.get("launchDate")
    if isinstance(raw, str) and len(raw) >= 10:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            pass
    # Neutral mid-range fallback (matches the DefiLlama catalog's listedAt default).
    return scan_date - timedelta(days=180)


def _project_type(program: dict[str, Any]) -> str | None:
    for key in ("projectType", "productType"):
        raw = program.get(key)
        if isinstance(raw, list) and raw:
            return "/".join(str(x) for x in raw if x)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _audit_signal(program: dict[str, Any]) -> tuple[int, list[str], str | None]:
    """Extract Immunefi's own prior-audit record: (count, report_urls, note)."""
    audits = [a for a in (program.get("audits") or []) if isinstance(a, dict)]
    if not audits:
        return 0, [], None
    urls = [
        str(a["url"])
        for a in audits
        if isinstance(a.get("url"), str) and a["url"].startswith("http")
    ]
    dates = sorted(str(a["date"]) for a in audits if isinstance(a.get("date"), str))
    latest = f", latest {dates[-1]}" if dates else ""
    note = f"Immunefi lists {len(audits)} prior audit(s){latest}"
    return len(audits), urls, note


def _dl_audit_count(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _languages(program: dict[str, Any], chain: Chain) -> list[Language]:
    langs = [CHAIN_DEFAULT_LANG[chain]]
    for raw in program.get("language") or []:
        mapped = _LANG_NAMES.get(str(raw).strip().lower())
        if mapped is not None and mapped not in langs:
            langs.append(mapped)
    return langs


def _build_candidate(
    program: dict[str, Any],
    catalog: DefiLlamaCatalog,
    configured: set[Chain],
    scan_date: date,
    *,
    kyc: bool | None,
    min_bounty: int | None,
) -> EnrichedCandidate | None:
    """Map one Immunefi program to an EnrichedCandidate. None → skipped."""
    slug = str(program.get("slug") or "").strip()
    if not slug:
        return None
    project = str(program.get("project") or slug).strip()

    if kyc is not None and bool(program.get("kyc")) != kyc:
        return None

    max_bounty_raw = program.get("maxBounty")
    max_bounty = int(max_bounty_raw) if isinstance(max_bounty_raw, (int, float)) else None
    if min_bounty is not None and (max_bounty or 0) < min_bounty:
        return None

    chain, evm_addr, in_scope_count = _pick_scope(program, configured)
    if chain is None:
        chain = _ecosystem_chain(program, configured)
    if chain is None:
        return None  # no in-scope contract on any supported chain — caller counts it

    address = evm_addr or f"immunefi:{slug}"
    onchain_address = f"{chain.value}:{evm_addr}" if evm_addr else None

    # DefiLlama match → TVL, category, DefiLlama audit count/links.
    dl = catalog.lookup(project) or (catalog.lookup(slug) if slug != project else None)
    tvl = 0.0
    category: str | None = None
    dl_slug: str | None = None
    dl_count: int | None = None
    dl_links: list[str] = []
    if dl:
        raw_tvl = dl.get("tvl")
        tvl = float(raw_tvl) if isinstance(raw_tvl, (int, float)) and raw_tvl > 0 else 0.0
        category = str(dl["category"]) if dl.get("category") else None
        dl_slug = str(dl["slug"]) if dl.get("slug") else None
        dl_count = _dl_audit_count(dl.get("audits"))
        dl_links = [u for u in (dl.get("audit_links") or []) if isinstance(u, str) and u.startswith("http")]

    im_count, im_urls, im_note = _audit_signal(program)

    # Fold the two audit records into one count. compute_score reads
    # defillama_audit_count for audit density, and Stage 3 skips the rate-limited
    # GitHub contest search when it is > 0 — Immunefi's own audit list already
    # answers "is this audited?", so we don't need to re-derive it from GitHub.
    combined = max(dl_count or 0, im_count)
    audit_count = combined if (dl_count is not None or im_count) else None
    note = "; ".join(n for n in (im_note, str(dl.get("audit_note")) if dl and dl.get("audit_note") else None) if n) or None

    audit_links = dl_links + [u for u in im_urls if u not in dl_links]

    github_url_raw = program.get("githubUrl")
    github_repo = (
        str(github_url_raw)
        if isinstance(github_url_raw, str) and "github.com" in github_url_raw
        else None
    )

    ptype = category or _project_type(program) or "Bug bounty"

    return EnrichedCandidate(
        chain=chain,
        address=address,
        tvl_usd=tvl,
        first_seen=_launch_date(program, scan_date),
        unique_users_30d=None,
        source=DiscoverySource.IMMUNEFI_CATALOG,
        target_name=slug,
        display_name=project,
        protocol_type=f"{ptype} on {chain.value} ({in_scope_count} in-scope contracts)",
        languages=_languages(program, chain),
        github_repo=github_repo,
        loc_estimate=None,
        docs_url=None,
        bounty_program="immunefi",
        bounty_url=f"https://immunefi.com/bug-bounty/{slug}",
        bounty_max_payout_usd=max_bounty,
        defillama_slug=dl_slug,
        defillama_audit_links=audit_links[:10],
        defillama_audit_count=audit_count,
        defillama_audit_note=note,
        onchain_address=onchain_address,
    )


async def _resolve_deploy_dates(
    results: list[EnrichedCandidate], client: httpx.AsyncClient | None
) -> None:
    """Override first_seen with the TRUE on-chain deploy date for candidates whose
    in-scope contract exposed an EVM address. Batched by chain (5/call via Etherscan).
    Mutates in place; no-op without addresses or an etherscan key.
    """
    by_chain: dict[Chain, list[str]] = defaultdict(list)
    index: dict[tuple[Chain, str], list[EnrichedCandidate]] = defaultdict(list)
    for cand in results:
        oc = cand.onchain_address
        if not oc or ":" not in oc:
            continue
        chain_str, _, addr = oc.partition(":")
        try:
            chain = Chain(chain_str)
        except ValueError:
            continue
        by_chain[chain].append(addr)
        index[(chain, addr.lower())].append(cand)

    if not by_chain:
        return

    total = sum(len(v) for v in by_chain.values())
    resolved = 0
    for chain, addrs in by_chain.items():
        dates = await fetch_creation_dates_batch(chain, addrs, client=client)
        for addr_lower, deploy_date in dates.items():
            for cand in index.get((chain, addr_lower), []):
                cand.first_seen = deploy_date
                resolved += 1
    log.info(
        "immunefi catalog: resolved TRUE deploy date for %d/%d candidates with EVM addresses",
        resolved,
        total,
    )


async def discover_from_immunefi_catalog(
    *,
    chains: list[Chain] | None = None,
    scan_date: date | None = None,
    client: httpx.AsyncClient | None = None,
    catalog: DefiLlamaCatalog | None = None,
    kyc: bool | None = None,
    min_bounty: int | None = None,
) -> list[EnrichedCandidate]:
    """Seed one EnrichedCandidate per active Immunefi program.

    `chains` restricts to those chains (default: every chain in the Chain enum —
    the whole point is to rank the FULL bounty universe, not the .env subset).
    `kyc` filters to programs matching that KYC flag (None = both). `min_bounty`
    drops programs whose max payout is below the floor.
    """
    scan_date = scan_date or date.today()
    configured = set(chains) if chains is not None else ALL_CHAINS

    programs = await immunefi.fetch_raw(client=client)
    if not programs:
        log.warning("immunefi catalog: no programs fetched")
        return []

    if catalog is None:
        catalog = DefiLlamaCatalog()
        await catalog.load(client=client)

    results: list[EnrichedCandidate] = []
    skipped_chain = 0
    for program in programs:
        try:
            cand = _build_candidate(
                program, catalog, configured, scan_date, kyc=kyc, min_bounty=min_bounty
            )
        except Exception as exc:  # one malformed program must not abort the scan
            log.warning("immunefi catalog: skipped %s: %s", program.get("slug"), exc)
            continue
        if cand is None:
            # Distinguish an unsupported-chain skip from a filter skip for the log.
            if program.get("slug") and (kyc is None and min_bounty is None):
                skipped_chain += 1
            continue
        results.append(cand)

    await _resolve_deploy_dates(results, client)

    log.info(
        "immunefi catalog discovery: %d candidates from %d programs "
        "(%d skipped: no in-scope contract on a supported chain)",
        len(results),
        len(programs),
        skipped_chain,
    )
    return results
