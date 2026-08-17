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

import asyncio
import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import httpx

from tvl_scanner.enrich import immunefi
from tvl_scanner.enrich.defillama import DefiLlamaCatalog
from tvl_scanner.enrich.defillama_protocols import (
    CHAIN_DEFAULT_LANG,
    _chain_tvls,
    _raw_named_chain_tvls,
)
from tvl_scanner.enrich.etherscan import fetch_creation_dates_batch
from tvl_scanner.enrich.github import enrich_repo
from tvl_scanner.enrich.homepage_scrape import (
    github_url_matches_protocol,
    scrape_homepage_with_fallback,
)
from tvl_scanner.enrich.immunefi_filter import (
    REASON_NO_CHAIN,
    FilterFunnel,
    ProgramFilter,
)
from tvl_scanner.enrich.immunefi_profile import (
    TESTNET_MARKERS,
    attach_payout_ratio,
    build_profile,
)
from tvl_scanner.enrich.onchain_tvl import measure_onchain_tvl
from tvl_scanner.enrich.scope_audits import extract_scope_audit_sources
from tvl_scanner.models import (
    AuditSource,
    AuditSourceKind,
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
# Single-sourced in immunefi_profile so the scope table and the chain resolver
# cannot disagree about what a testnet URL is.
_TESTNET_MARKERS: tuple[str, ...] = TESTNET_MARKERS

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
        if _is_testnet(url):
            continue
        count += 1
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


def _explorer_partition(
    program: dict[str, Any], configured: set[Chain]
) -> tuple[int, int, Chain | None]:
    """Split in-scope explorers into mapped / unmapped, plus a testnet chain hint.

    Returns (mapped_mainnet, unmapped_mainnet, testnet_hint). Testnet rows are
    not a chain we can hunt, but they *do* tell us which ecosystem the program
    is actually about — TruYields lists Solana devnet + a Solana github repo
    and `ecosystem: [ETH, Polygon, Solana]`; without the hint the fallback
    picked ETH and bound DefiLlama's $7 Ethereum leftover.

    Unmapped mainnet explorers (katanascan, snowtrace, …) are a chain this
    scanner cannot read. A program whose *majority* of explorer rows are
    unmapped is not an Ethereum target just because two OFT adapters also
    have an etherscan link.
    """
    mapped = 0
    unmapped = 0
    testnet_hint: Chain | None = None
    for asset in program.get("assets") or []:
        if not isinstance(asset, dict) or asset.get("type") != "smart_contract":
            continue
        url = str(asset.get("url") or "")
        if not url or "immunefi.com" in url or "github.com" in url.lower():
            continue
        chain = _chain_from_explorer(url)
        if _is_testnet(url):
            if (
                testnet_hint is None
                and chain is not None
                and chain in configured
            ):
                testnet_hint = chain
            continue
        if chain is None or chain not in configured:
            unmapped += 1
        else:
            mapped += 1
    return mapped, unmapped, testnet_hint


def _has_unmapped_mainnet_explorer(
    program: dict[str, Any], configured: set[Chain]
) -> bool:
    """True when unmapped explorers outnumber ones we can read.

    Kept as a named predicate so tests can assert the Katana shape without
    going through the full builder.
    """
    mapped, unmapped, _hint = _explorer_partition(program, configured)
    return unmapped > mapped



def _scope_addresses(program: dict[str, Any], chain: Chain) -> list[str]:
    """Every in-scope EVM address on `chain`, deduped, order preserved.

    `_pick_scope` returns ONE representative address (it only needs a deploy
    date). TVL needs the whole set: Pareto Credit spreads $224M across five
    separate credit vaults, so measuring only the first would undercount it by
    ~95%.
    """
    out: list[str] = []
    seen: set[str] = set()
    for asset in program.get("assets") or []:
        if not isinstance(asset, dict) or asset.get("type") != "smart_contract":
            continue
        url = str(asset.get("url") or "")
        if not url or "immunefi.com" in url or _is_testnet(url):
            continue
        if _chain_from_explorer(url) is not chain:
            continue
        m = immunefi._ADDR_RE.search(url)
        if not m:
            continue
        addr = m.group(0)
        if addr.lower() in seen:
            continue
        seen.add(addr.lower())
        out.append(addr)
    return out


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
    """Prefer the program's own language list; the chain default is a guess.

    Seeding Solidity because the in-scope explorer is etherscan, then appending
    Immunefi's list, is how a Rust/Bitcoin metaprotocol with an Ethereum
    explorer row was filed as Solidity. The guess applies only when the
    program publishes no recognised language.
    """
    resolved: list[Language] = []
    seen: set[Language] = set()
    for raw in program.get("language") or []:
        mapped = _LANG_NAMES.get(str(raw).strip().lower())
        if mapped is not None and mapped not in seen:
            resolved.append(mapped)
            seen.add(mapped)
    if resolved:
        return resolved
    return [CHAIN_DEFAULT_LANG[chain]]


def _tvl_on_scope_chain(
    dl: dict[str, Any] | None, chain: Chain
) -> tuple[float, bool]:
    """TVL sitting on the Immunefi in-scope chain, not the protocol-wide total.

    Same defect the catalog path fixed for SUBFROST: DefiLlama's `tvl` is the
    sum across every chain the protocol exists on. A bounty whose in-scope
    contracts are on Ethereum must not inherit $7.3M of Bitcoin TVL (or any
    other unreadable chain). When `chainTvls` says the money is elsewhere,
    leave TVL unresolved so the on-chain fallback can try, rather than
    scoring a confident wrong number.
    """
    if not dl:
        return 0.0, False
    per_chain = _chain_tvls(dl)
    if chain in per_chain:
        value = per_chain[chain]
        return (value, True) if value > 0 else (0.0, False)
    named = _raw_named_chain_tvls(dl)
    if named:
        richest_name = max(named, key=lambda n: named[n])
        log.info(
            "immunefi catalog: %s DefiLlama TVL sits on %s, not in-scope %s — "
            "leaving unresolved rather than attributing $%s",
            dl.get("slug") or dl.get("name") or "?",
            richest_name,
            chain.value,
            f"{sum(named.values()):,.0f}",
        )
        return 0.0, False
    raw = dl.get("tvl")
    if isinstance(raw, (int, float)) and raw > 0:
        return float(raw), True
    return 0.0, False


def _build_candidate(
    program: dict[str, Any],
    catalog: DefiLlamaCatalog,
    configured: set[Chain],
    scan_date: date,
) -> EnrichedCandidate | None:
    """Map one Immunefi program to an EnrichedCandidate.

    Returns None only when the program has no in-scope contract on a supported
    chain — the one rejection that is a property of the *scanner's* coverage
    rather than of the user's filters. Everything the user asked to filter on is
    decided by `ProgramFilter` against the built candidate, so each drop can be
    attributed to a named reason in the funnel instead of vanishing here.
    """
    slug = str(program.get("slug") or "").strip()
    if not slug:
        return None
    project = str(program.get("project") or slug).strip()

    max_bounty_raw = program.get("maxBounty")
    max_bounty = int(max_bounty_raw) if isinstance(max_bounty_raw, (int, float)) else None

    chain, evm_addr, in_scope_count = _pick_scope(program, configured)
    mapped, unmapped, testnet_hint = _explorer_partition(program, configured)
    # Majority-unmapped (Katana: ~18 katanascan vs 4 L1 OFT/bridge rows) is
    # not an Ethereum program. Skip rather than scoring the L1 leftovers.
    if unmapped > mapped:
        return None
    if chain is None:
        # Testnet explorers we *can* map beat ecosystem-list order. TruYields
        # would otherwise become Ethereum because ETH is first in `ecosystem`.
        chain = testnet_hint or _ecosystem_chain(program, configured)
    if chain is None:
        return None  # no in-scope contract on any supported chain — caller counts it

    address = evm_addr or f"immunefi:{slug}"
    onchain_address = f"{chain.value}:{evm_addr}" if evm_addr else None

    # DefiLlama match → TVL, category, DefiLlama audit count/links.
    dl = catalog.lookup(project, prefer_chain=chain) or (
        catalog.lookup(slug, prefer_chain=chain) if slug != project else None
    )
    tvl = 0.0
    category: str | None = None
    dl_slug: str | None = None
    dl_count: int | None = None
    dl_links: list[str] = []
    dl_url: str | None = None
    # Unresolved until DefiLlama actually yields a number. Both failure modes —
    # no name-match at all, and a match whose `tvl` is null — used to land on a
    # bare 0.0 that the report then printed as a confident "$0".
    tvl_resolved = False
    if dl:
        tvl, tvl_resolved = _tvl_on_scope_chain(dl, chain)
        category = str(dl["category"]) if dl.get("category") else None
        dl_slug = str(dl["slug"]) if dl.get("slug") else None
        dl_count = _dl_audit_count(dl.get("audits"))
        dl_links = [u for u in (dl.get("audit_links") or []) if isinstance(u, str) and u.startswith("http")]
        raw_url = dl.get("url")
        dl_url = raw_url if isinstance(raw_url, str) and raw_url.startswith("http") else None

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

    # Criteria 2-6 and 8-12 of the target-selection rubric, straight out of the
    # program record. The payout-vs-TVL ratio needs the TVL we just resolved,
    # and is recomputed after the on-chain TVL fallback runs.
    profile = build_profile(program, scan_date=scan_date)
    attach_payout_ratio(profile, tvl, tvl_resolved)

    return EnrichedCandidate(
        chain=chain,
        address=address,
        tvl_usd=tvl,
        tvl_resolved=tvl_resolved,
        first_seen=_launch_date(program, scan_date),
        unique_users_30d=None,
        source=DiscoverySource.IMMUNEFI_CATALOG,
        target_name=slug,
        display_name=project,
        protocol_type=f"{ptype} on {chain.value} ({in_scope_count} in-scope contracts)",
        languages=_languages(program, chain),
        github_repo=github_repo,
        loc_estimate=None,
        # DefiLlama's protocol homepage. Doubles as the phase-1 seed for the
        # homepage audit scrape below — Immunefi's own `websiteUrl` is null for
        # most programs, so this is the only URL we get for free.
        docs_url=dl_url,
        bounty_program="immunefi",
        bounty_url=f"https://immunefi.com/bug-bounty/{slug}",
        bounty_max_payout_usd=max_bounty,
        defillama_slug=dl_slug,
        defillama_audit_links=audit_links[:10],
        defillama_audit_count=audit_count,
        defillama_audit_note=note,
        onchain_address=onchain_address,
        # Audit reports the program itself cites as out-of-scope prior work.
        # The structured `audits` array covers only ~30% of programs; this
        # prose signal covers ~64% and is the only one that sees PDF-publishing
        # firms (Sigma Prime, ChainSecurity, PeckShield) which no contest
        # search can reach.
        precomputed_audit_sources=extract_scope_audit_sources(program),
        bounty_profile=profile,
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


# A DefiLlama count at or below this is treated as too weak to suppress the
# docs/homepage scrape. DefiLlama's `audits` field systematically understates:
# Pareto Credit reads 2 there while publishing 14 reports on its own docs site,
# GMTrade read 2 against 9, NUVA 3 against 7. Since the under_audited threshold
# is 2 and audit_gap carries 0.30 of the priority score, accuracy matters most
# exactly in this band — so we spend a fetch to check rather than trust it.
WEAK_DL_AUDIT_COUNT = 3


def _has_audit_evidence(cand: EnrichedCandidate) -> bool:
    """True when we already know this candidate is audited.

    Used to bound the cost of the network-backed GitHub `audits/` pass: it only
    runs for candidates that would otherwise score zero, which is exactly the
    population whose `under_audited` flag is at risk of being a false positive.
    """
    return bool(cand.precomputed_audit_sources) or bool(cand.defillama_audit_count)


def _has_strong_audit_evidence(cand: EnrichedCandidate) -> bool:
    """True only when a source that NAMES actual reports vouches for this.

    A precomputed source is a real citation — a report URL in the bounty prose,
    a GitHub `audits/` folder, a contest hit. A bare DefiLlama integer is not:
    it is an aggregator's summary that is frequently far below the truth, so on
    its own it must NOT suppress the docs scrape. Treating it as sufficient is
    what hid Pareto Credit's 14 audits and floated it to rank 2 of a live scan.
    """
    if cand.precomputed_audit_sources:
        return True
    count = cand.defillama_audit_count
    return count is not None and count > WEAK_DL_AUDIT_COUNT


async def _resolve_github_audit_folders(
    results: list[EnrichedCandidate], client: httpx.AsyncClient | None
) -> None:
    """Populate the `audits/` folder signal for candidates that name a repo.

    ~30% of Immunefi programs publish a `githubUrl`, and teams that keep audit
    PDFs in-repo (Metronome, Ampleforth) are invisible to every other source.
    Mutates in place.
    """
    targets: list[EnrichedCandidate] = []
    disowned = 0
    for cand in results:
        if not cand.github_repo or _has_audit_evidence(cand):
            continue
        if not github_url_matches_protocol(
            str(cand.github_repo),
            slug=cand.defillama_slug or cand.target_name,
            display_name=cand.display_name,
        ):
            # Upstream/vendor repo, not the team's own — its audits say nothing
            # about this protocol's in-scope code.
            disowned += 1
            continue
        targets.append(cand)

    if disowned:
        log.info(
            "immunefi catalog: %d candidate(s) declare a repo that is not theirs — "
            "audits/ folder not credited",
            disowned,
        )
    if not targets:
        return

    sem = asyncio.Semaphore(4)

    async def _one(cand: EnrichedCandidate) -> bool:
        async with sem:
            try:
                meta = await enrich_repo(cand.github_repo, client=client)
            except Exception as exc:
                log.debug("audits-folder check failed for %s: %s", cand.target_name, exc)
                return False
        if not meta or not meta.audits_folder_exists:
            return False
        cand.github_audits_folder_exists = True
        cand.github_audit_report_count = meta.audit_report_count
        return True

    found = sum(await asyncio.gather(*(_one(c) for c in targets)))
    log.info(
        "immunefi catalog: audits/ folder found for %d/%d candidates with a repo",
        found,
        len(targets),
    )


async def _resolve_homepage_audits(
    results: list[EnrichedCandidate], client: httpx.AsyncClient | None
) -> None:
    """Last-resort audit signal: scrape the protocol's own site for firm names.

    Runs only for candidates with no audit evidence from any cheaper source.
    `max_attempts` is kept low because this is the most fragile source (SPAs,
    bot blocking) and it runs against the long tail. Mutates in place.
    """
    # Gated on STRONG evidence, not any evidence: a low DefiLlama count is the
    # case this pass exists to correct, so it must not be the reason to skip.
    targets = [c for c in results if not _has_strong_audit_evidence(c)]
    if not targets:
        return

    sem = asyncio.Semaphore(4)

    async def _one(cand: EnrichedCandidate) -> bool:
        async with sem:
            try:
                result = await scrape_homepage_with_fallback(
                    cand.docs_url, cand.display_name, client=client, max_attempts=4
                )
            except Exception as exc:
                log.debug("homepage scrape failed for %s: %s", cand.target_name, exc)
                return False
        if not result.audit_firm_matches:
            return False
        page = result.url if result.url.startswith("http") else cand.docs_url
        cand.precomputed_audit_sources.extend(
            AuditSource(
                source=AuditSourceKind.HOMEPAGE_SCRAPE,
                url=page,
                title=f"{firm} audit cited on protocol homepage",
                weight=4,
            )
            for firm in result.audit_firm_matches
        )
        return True

    found = sum(await asyncio.gather(*(_one(c) for c in targets)))
    log.info(
        "immunefi catalog: homepage audit citations found for %d/%d zero-evidence candidates",
        found,
        len(targets),
    )



async def _resolve_onchain_tvl(
    results: list[EnrichedCandidate],
    scope_map: dict[str, list[str]],
    client: httpx.AsyncClient | None,
) -> None:
    """Measure TVL on-chain for candidates DefiLlama could not resolve.

    Runs only where `tvl_resolved` is False, so a working DefiLlama figure is
    never overridden — this is a fallback, not a replacement. Mutates in place.
    """
    targets = [c for c in results if not c.tvl_resolved and c.chain is not Chain.SOLANA]
    if not targets:
        return

    sem = asyncio.Semaphore(4)

    async def _one(cand: EnrichedCandidate) -> bool:
        addresses = scope_map.get(cand.target_name) or []
        if not addresses:
            return False
        async with sem:
            try:
                measured = await measure_onchain_tvl(cand.chain, addresses, client=client)
            except Exception as exc:
                log.debug("on-chain TVL failed for %s: %s", cand.target_name, exc)
                return False
        if measured is None:
            return False
        cand.tvl_usd, cand.tvl_resolved = measured[0], True
        # The payout-vs-funds-at-risk ratio was left None when DefiLlama had no
        # figure; now that TVL is measured, criterion 3 can be scored properly.
        if cand.bounty_profile is not None:
            attach_payout_ratio(cand.bounty_profile, cand.tvl_usd, True)
        note = f"TVL measured {measured[1]}"
        cand.defillama_audit_note = (
            f"{cand.defillama_audit_note} | {note}" if cand.defillama_audit_note else note
        )
        return True

    found = sum(await asyncio.gather(*(_one(c) for c in targets)))
    log.info(
        "immunefi catalog: on-chain TVL resolved for %d/%d candidates DefiLlama missed",
        found,
        len(targets),
    )


async def discover_from_immunefi_catalog(
    *,
    chains: list[Chain] | None = None,
    scan_date: date | None = None,
    client: httpx.AsyncClient | None = None,
    catalog: DefiLlamaCatalog | None = None,
    filters: ProgramFilter | None = None,
) -> tuple[list[EnrichedCandidate], FilterFunnel]:
    """Seed one EnrichedCandidate per Immunefi program, filtered before enrichment.

    `chains` restricts to those chains (default: every chain in the Chain enum —
    the whole point is to rank the FULL bounty universe, not the .env subset).
    `filters` is the user's target-selection constraints; the default
    `ProgramFilter()` keeps everything except already-closed competitions.

    The flow is deliberately build → filter → enrich. Building is pure and cheap,
    so every program gets a candidate and a profile; filtering then runs against
    those, which means each rejection has a named reason for the funnel AND the
    expensive passes below (deploy dates, audits-folder probes, homepage scrapes,
    on-chain TVL) only ever touch survivors.

    Returns (candidates, funnel) — the funnel accounts for every program that did
    not make it, so a three-candidate shortlist is always explainable.
    """
    scan_date = scan_date or date.today()
    configured = set(chains) if chains is not None else ALL_CHAINS
    filters = filters or ProgramFilter()

    programs = await immunefi.fetch_raw(client=client)
    funnel = FilterFunnel(fetched=len(programs))
    if not programs:
        log.warning("immunefi catalog: no programs fetched")
        return [], funnel

    if catalog is None:
        catalog = DefiLlamaCatalog()
        await catalog.load(client=client)

    results: list[EnrichedCandidate] = []
    scope_map: dict[str, list[str]] = {}
    for program in programs:
        try:
            cand = _build_candidate(program, catalog, configured, scan_date)
        except Exception as exc:  # one malformed program must not abort the scan
            log.warning("immunefi catalog: skipped %s: %s", program.get("slug"), exc)
            funnel.drop(REASON_NO_CHAIN)
            continue
        if cand is None:
            funnel.drop(REASON_NO_CHAIN)
            continue
        reason = filters.reject_reason(cand, scan_date=scan_date)
        if reason is not None:
            funnel.drop(reason)
            continue
        results.append(cand)
        scope_map[cand.target_name] = _scope_addresses(program, cand.chain)

    log.info(
        "immunefi catalog: %d/%d programs passed pre-enrichment filters",
        len(results),
        len(programs),
    )

    await _resolve_deploy_dates(results, client)
    scope_hits = sum(1 for c in results if c.precomputed_audit_sources)
    log.info(
        "immunefi catalog: %d/%d candidates cite an audit report in their bounty scope",
        scope_hits,
        len(results),
    )
    await _resolve_github_audit_folders(results, client)
    await _resolve_homepage_audits(results, client)
    await _resolve_onchain_tvl(results, scope_map, client)

    # TVL-dependent constraints run last: --min-tvl and --min-payout-ratio can
    # only be judged once the DefiLlama match and the on-chain fallback have both
    # had their turn, otherwise they would drop protocols for being unmeasured
    # when the fallback was about to measure them.
    kept: list[EnrichedCandidate] = []
    for cand in results:
        reason = filters.tvl_reject_reason(cand)
        if reason is not None:
            funnel.drop(reason)
            continue
        kept.append(cand)

    log.info("immunefi catalog discovery funnel:\n%s", funnel.render())
    return kept, funnel
