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
from tvl_scanner.enrich import bounty, github_registry
from tvl_scanner.enrich.defillama import DefiLlamaCatalog
from tvl_scanner.enrich.etherscan import fetch_creation_dates_batch
from tvl_scanner.enrich.github import enrich_repo
from tvl_scanner.enrich.homepage_scrape import (
    rank_github_urls_for_protocol,
    scrape_homepage_with_fallback,
)
from tvl_scanner.enrich.prices import PriceCache
from tvl_scanner.enrich.solana_wrapper_check import (
    compute_on_chain_lst_tvl,
)
from tvl_scanner.models import (
    AuditSource,
    AuditSourceKind,
    Chain,
    DiscoverySource,
    EnrichedCandidate,
    Language,
)

log = logging.getLogger(__name__)


def _coerce_audit_count(raw: Any) -> int | None:
    """Normalize DefiLlama `audits` field (int or stringified int) → int."""
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


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

_LANG_NAME_TO_ENUM: dict[str, Language] = {
    "solidity": Language.SOLIDITY,
    "rust": Language.RUST,
    "move": Language.MOVE,
}


def _derive_languages(chain: Chain, repo: Any) -> list[Language]:
    """Resolve languages, treating the repo's own language set as authoritative.

    The chain default is a GUESS ("it's on an EVM chain, so probably Solidity").
    It must not survive contact with evidence. The previous version seeded the
    guess and then *appended* repo languages, so a Rust-only repo on an EVM
    chain came out `[solidity, rust]` — which is how SUBFROST, a Bitcoin
    metaprotocol with zero Solidity in any of its 19 repos, was filed as a
    Solidity target. Verified: `search/code?q=org:subfrost+extension:sol` → 0.

    Now the guess is used only when the repo yields no recognised language.
    """
    resolved: list[Language] = []
    seen: set[Language] = set()
    if repo is not None and getattr(repo, "languages", None):
        for lang_name in repo.languages:
            mapped = _LANG_NAME_TO_ENUM.get(str(lang_name).lower())
            if mapped and mapped not in seen:
                resolved.append(mapped)
                seen.add(mapped)
    if resolved:
        return resolved
    return [CHAIN_DEFAULT_LANG[chain]]


def _pick_primary_chain(
    protocol: dict[str, Any], configured: set[Chain]
) -> Chain | None:
    """Choose the first chain that is both in the protocol's chain list AND configured.

    Order-based fallback used only when `chainTvls` is unusable. Prefer
    `_pick_primary_chain_and_tvl`, which picks by value rather than list order.
    """
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


def _chain_tvls(protocol: dict[str, Any]) -> dict[Chain, float]:
    """Parse DefiLlama's per-chain `chainTvls` into {Chain: usd}.

    The flat `/protocols` catalog already carries this, so reading it costs no
    extra HTTP call. Keys we must ignore: DefiLlama mixes derived buckets into
    the same dict — hyphenated variants (`Ethereum-borrowed`, `Arbitrum-vesting`)
    and bare aggregates (`borrowed`, `pool2`, `staking`). The hyphen check drops
    the former; the latter map to no Chain and fall out naturally.
    """
    raw = protocol.get("chainTvls")
    out: dict[Chain, float] = {}
    if not isinstance(raw, dict):
        return out
    for name, value in raw.items():
        if not isinstance(name, str) or not isinstance(value, (int, float)):
            continue
        if "-" in name:
            continue
        mapped = DL_CHAIN_NAMES.get(name.strip().lower())
        if mapped is None:
            continue
        out[mapped] = max(out.get(mapped, 0.0), float(value))
    return out


def _pick_primary_chain_and_tvl(
    protocol: dict[str, Any], configured: set[Chain]
) -> tuple[Chain | None, float | None]:
    """Pick the configured chain holding the MOST value, and return that chain's TVL.

    Two bugs this exists to fix, both measured on SUBFROST in the 2026-08-10 scan:

    1. **Chain choice by list order.** `_pick_primary_chain` returns the first
       configured entry in `chains`, so a protocol with $1k on Ethereum and $50M
       on Arbitrum was attributed to whichever DefiLlama happened to list first.
    2. **Total TVL attributed to one chain.** Callers used the protocol-wide
       `tvl`, so SUBFROST — `chainTvls: {Ethereum: 6050, Bitcoin: 7302865}` —
       was reported as a $7.3M *Ethereum* protocol. The Bitcoin leg is not on a
       chain this scanner can read, and $6,050 is below MIN_TVL_USD, so the row
       should never have been generated at all. It ranked #1.

    Falls back to (list-order chain, protocol-wide tvl) only when `chainTvls`
    yields nothing usable, preserving behaviour for entries that lack it.
    """
    per_chain = _chain_tvls(protocol)
    in_scope = {c: v for c, v in per_chain.items() if c in configured}
    if in_scope:
        richest = max(in_scope, key=lambda c: in_scope[c])
        return richest, in_scope[richest]

    fallback = _pick_primary_chain(protocol, configured)
    if fallback is None:
        return None, None
    total = protocol.get("tvl")
    return fallback, float(total) if isinstance(total, (int, float)) else None


def _extract_github_url(protocol: dict[str, Any]) -> str | None:
    """Extract a fully-qualified github URL from a DefiLlama protocol entry.

    DefiLlama is inconsistent: some entries have `github=[]` (empty list), some
    have `github=['https://github.com/foo/bar']` (real URL), and some have
    `github=['foo']` (BARE ORG NAME ONLY, unusable — cannot be turned into a
    repo URL without guessing the repo name). We reject the bare-org case so
    that callers fall through to the github_registry fallback, which has
    curated owner/repo pairs that actually point at real repos.
    """
    gh = protocol.get("github")
    candidate: str | None = None
    if isinstance(gh, list) and gh:
        candidate = str(gh[0])
    elif isinstance(gh, str):
        candidate = gh

    # Must contain "github.com" to be a full URL we can parse. Bare org names
    # like "synapsecns" look non-None but can't be enriched, so we force a
    # fallthrough to the registry where curated repo paths live.
    if candidate and "github.com" in candidate:
        return candidate

    url = protocol.get("url")
    if isinstance(url, str) and "github.com" in url:
        return url
    return None


def _audit_links(protocol: dict[str, Any]) -> list[str]:
    raw = protocol.get("audit_links") or []
    if isinstance(raw, str):
        raw = [raw]
    return [u for u in raw if isinstance(u, str) and u.startswith("http")]


def _parse_detail_address(raw: Any) -> tuple[Chain | None, str | None]:
    """Parse the DefiLlama detail `address` field into (chain, evm_address).

    DefiLlama's `/protocol/{slug}` detail exposes the protocol's governance/token
    contract as either a bare `0x...` (implicitly Ethereum) or a chain-qualified
    `bsc:0x...` / `arbitrum:0x...` string. We use it to resolve the protocol's
    TRUE deployment date (see `_resolve_true_deploy_dates`).

    Returns (None, None) for: missing/blank values, unknown chain prefixes,
    and non-EVM addresses (Solana base58 program/mint ids — Etherscan can't
    resolve those).
    """
    if not isinstance(raw, str) or not raw.strip():
        return None, None
    raw = raw.strip()
    if ":" in raw:
        prefix, _, addr = raw.partition(":")
        chain = DL_CHAIN_NAMES.get(prefix.strip().lower())
    else:
        addr, chain = raw, Chain.ETHEREUM  # bare address → assume Ethereum
    addr = addr.strip()
    if chain is None or not addr.lower().startswith("0x") or len(addr) != 42:
        return None, None
    return chain, addr


def _first_seen(protocol: dict[str, Any], scan_date: date) -> date:
    """Derive a 'first seen' date from DefiLlama's `listedAt` Unix timestamp."""
    raw = protocol.get("listedAt")
    if isinstance(raw, (int, float)) and raw > 0:
        try:
            from datetime import UTC
            from datetime import datetime as _dt
            # UTC, not host-local: a listedAt near midnight UTC must not
            # shift a day (and flip MAX_AGE_DAYS filtering) by timezone.
            return _dt.fromtimestamp(float(raw), tz=UTC).date()
        except (ValueError, OSError):
            pass
    # Fallback: mid-range so freshness score is neutral
    return scan_date - timedelta(days=180)


def _passes_basic_filters(
    protocol: dict[str, Any],
    configured_chains: set[Chain],
    scan_date: date,
) -> tuple[bool, Chain | None, date | None, float | None]:
    """Synchronous cheap pre-filter. Returns (passes, chain, first_seen, chain_tvl).

    Called BEFORE any HTTP work so we only spawn expensive per-protocol tasks
    for entries that actually survive category/tvl/chain/age thresholds.

    The MIN_TVL_USD test runs against the value held on the *selected chain*,
    not the protocol-wide total. A protocol with $7.3M on an unreadable chain
    and $6k on Ethereum does not clear a $100k floor on Ethereum.
    """
    s = settings()
    category = str(protocol.get("category") or "")
    if category not in SCANNABLE_CATEGORIES:
        return False, None, None, None

    # Cheap reject on the protocol-wide total first: it is an upper bound on any
    # single chain's share, so anything failing here fails per-chain too.
    total = protocol.get("tvl")
    if not isinstance(total, (int, float)) or total < s.MIN_TVL_USD:
        return False, None, None, None

    chain, chain_tvl = _pick_primary_chain_and_tvl(protocol, configured_chains)
    if chain is None:
        return False, None, None, None
    if chain_tvl is None or chain_tvl < s.MIN_TVL_USD:
        return False, None, None, None

    first_seen = _first_seen(protocol, scan_date)
    age_days = (scan_date - first_seen).days
    if age_days < 0 or age_days > s.MAX_AGE_DAYS:
        return False, None, None, None

    slug = str(protocol.get("slug") or "").strip()
    if not slug:
        return False, None, None, None

    return True, chain, first_seen, chain_tvl


async def _process_protocol(
    protocol: dict[str, Any],
    chain: Chain,
    first_seen: date,
    catalog: DefiLlamaCatalog,
    client: httpx.AsyncClient | None,
    price_cache: PriceCache | None = None,
    chain_tvl: float | None = None,
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
        # Value on THIS chain, not the protocol-wide total. The caller resolves
        # it from `chainTvls`; the total is only a fallback for entries that
        # publish no per-chain breakdown.
        tvl = (
            float(chain_tvl)
            if chain_tvl is not None
            else float(protocol["tvl"])
        )

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

        # Capture the protocol's on-chain contract address (governance/token)
        # from the detail endpoint so the batch pass can resolve its TRUE
        # deployment date. Catalog records otherwise have no real address and an
        # unreliable listedAt-based age. Stored chain-qualified ("{chain}:0x..").
        onchain_address: str | None = None
        if detail:
            addr_chain, addr_value = _parse_detail_address(detail.get("address"))
            if addr_chain is not None and addr_value is not None:
                onchain_address = f"{addr_chain.value}:{addr_value}"

        # Solana on-chain program resolution. Catalog Solana candidates have no
        # real address — Stage 1's on-chain leg is EVM-only — so without this the
        # `address` stays `defillama:{slug}` and the auditor gets no code pointer.
        # Walk the DefiLlama TVL adapter (detail `module` field) → token account →
        # SPL authority → owning program, and read its upgrade authority. The true
        # on-chain deploy date also beats the listedAt-based placeholder.
        solana_program_id: str | None = None
        solana_upgrade_authority: str | None = None
        solana_upgrade_authority_type: str | None = None
        if chain == Chain.SOLANA and detail:
            module = str(detail.get("module") or "").strip()
            if module:
                from tvl_scanner.enrich.solana_rpc import resolve_solana_program

                profile = await resolve_solana_program(module, client=client)
                if profile:
                    solana_program_id = profile.program_id
                    solana_upgrade_authority = profile.upgrade_authority
                    solana_upgrade_authority_type = profile.authority_type
                    onchain_address = f"{Chain.SOLANA.value}:{profile.program_id}"
                    if profile.deploy_date is not None:
                        first_seen = profile.deploy_date

        # github_url resolution: flat catalog → detail → curated registry →
        # org-name auto-guess (G2+G3) → None.
        # BATCH I fix #1: curated seed file as a fallback, covering
        # ~50 well-known protocols whose DefiLlama entries lack a github URL.
        # BATCH P (G2+G3): when no curated entry exists, try GitHub org-name
        # variants (slug, slug-protocol, slug-dao, ...) and accept only orgs
        # with at least one non-fork repo in a smart-contract language. This
        # catches protocols like Templar where DefiLlama lacks a github field
        # but a public github.com/<slug>-protocol org exists, AND correctly
        # rejects orgs like bima-protocol that exist but have 0 public repos.
        github_url = _extract_github_url(protocol)
        if not github_url and detail:
            github_url = _extract_github_url(detail)
        if not github_url:
            github_url = github_registry.lookup(slug)
        if not github_url:
            from tvl_scanner.enrich.github import find_org_with_repos
            github_url = await find_org_with_repos(slug, name, client=client)

        repo_metadata = None
        if github_url:
            repo_metadata = await enrich_repo(github_url, client=client)

        # Org-level `Audits` REPO check — independent of `github_url`, because
        # the two resolve differently: a team can publish reports in
        # <org>/Audits while its code repo is private (or is a fork the repo
        # picker skips). Runs whenever the folder check came up empty, which is
        # exactly the case that produced the false `under_audited: true`.
        org_audit_sources: list[AuditSource] = []
        if not (repo_metadata and repo_metadata.audits_folder_exists):
            from tvl_scanner.enrich.github import find_org_audit_repo
            found = await find_org_audit_repo(slug, name, client=client)
            if found:
                audit_repo_url, report_count = found
                org_audit_sources.append(
                    AuditSource(
                        source=AuditSourceKind.GITHUB_ORG_AUDIT_REPO,
                        url=audit_repo_url,
                        title=f"Org-level audit repo with {report_count} report(s)/component(s)",
                        weight=min(3, max(1, report_count)),
                    )
                )

        # Merge audit_links from detail with the flat catalog's set
        merged_audit_links = _audit_links(protocol)
        if detail:
            for link in _audit_links(detail):
                if link not in merged_audit_links:
                    merged_audit_links.append(link)

        languages = _derive_languages(chain, repo_metadata)

        bounty_entry = bounty.match(display_name=name, defillama_slug=slug, target_name=slug)
        bounty_program = bounty_entry.platform if bounty_entry else "none"
        bounty_url = bounty_entry.url if bounty_entry else None
        bounty_payout = bounty_entry.max_payout_usd if bounty_entry else None

        # Broad bug-bounty directory (lissy93/bug-bounties) — third fallback after
        # the curated seeds, catching HackerOne/Bugcrowd/Intigriti/self-hosted
        # programs Immunefi-centric detection misses. Only upgrades from "none".
        # The DefiLlama homepage URL gives the directory a domain to match on.
        if bounty_program == "none":
            from tvl_scanner.enrich.bugbounty_directory import match_directory

            homepage = protocol.get("url") or (detail.get("url") if detail else None)
            dir_entry = await match_directory(
                display_name=name,
                homepage_url=homepage if isinstance(homepage, str) else None,
                defillama_slug=slug,
                target_name=slug,
                client=client,
            )
            if dir_entry is not None:
                bounty_program = dir_entry.platform
                bounty_url = dir_entry.url
                bounty_payout = dir_entry.max_payout_usd
                log.info(
                    "bugbounty-directory match: %s -> %s (%s)",
                    slug, dir_entry.name, dir_entry.platform,
                )

        # BATCH J1: Solana wrapper-program detection. For Solana candidates
        # that match a known LST in our mint registry, query the stake pool
        # account's owner. If owned by SPL Stake Pool (or similar wrapper),
        # generate a synthetic AuditSource crediting the upstream program's
        # audit history.
        # Seeded with any org-level audit-repo source found above. This also
        # correctly suppresses the expensive 20-attempt homepage crawl below
        # (`needs_k2_fallback`), since the reports themselves are already found.
        precomputed_sources: list[AuditSource] = list(org_audit_sources)
        if chain == Chain.SOLANA:
            from tvl_scanner.enrich.solana_wrapper_check import check_lst_wrapper
            wrapper_match = await check_lst_wrapper(slug, client=client)
            if wrapper_match:
                precomputed_sources.append(
                    AuditSource(
                        source=AuditSourceKind.WRAPPER_PROGRAM,
                        url=wrapper_match.entry.audit_url,
                        title=(
                            f"Wraps {wrapper_match.entry.name} "
                            f"(owner: {wrapper_match.account_owner[:12]}…) — "
                            f"{wrapper_match.entry.audit_count} prior audits"
                        ),
                        weight=max(4, wrapper_match.entry.audit_count),
                    )
                )

        # BATCH J2: on-chain TVL sanity check for LSTs. If the LST is in our
        # mint registry, fetch its actual mint supply and compare to
        # DefiLlama's claim. >10x discrepancy → trust on-chain.
        actual_tvl_usd: float | None = None
        if chain == Chain.SOLANA and price_cache is not None:
            sol_price = await price_cache.get(Chain.SOLANA, client=client)
            if sol_price > 0:
                actual_tvl_usd = await compute_on_chain_lst_tvl(
                    slug, sol_price, client=client
                )
                if actual_tvl_usd is not None and actual_tvl_usd * 10 < float(tvl):
                    log.warning(
                        "%s: DefiLlama TVL $%.0f contradicts on-chain $%.2f, overriding",
                        slug,
                        float(tvl),
                        actual_tvl_usd,
                    )
                    tvl = actual_tvl_usd

        # BATCH K + K2: homepage scrape with multi-URL fallback. Phase 1 tries
        # DefiLlama's `url` field; Phase 2 derives candidate URLs from the
        # display_name when Phase 1 returns empty; Phase 3 (Batch L) mines
        # Phase 1 HTML for audit-related <a href> links.
        #
        # K2 cost gate: only fire the Phase 2 fallback when the candidate has
        # NO other audit signal available. If DefiLlama already reports audits,
        # or we already detected a wrapper / bounty match, the candidate is
        # well-classified and additional homepage scraping is wasted work.
        #
        # BATCH L tuning: raised max_attempts 4 → 20 because Batch L expanded
        # _AUDIT_PATHS from 5 to 18 entries — at 4 attempts the deeper paths
        # (e.g. /documentation/custody-and-security/audits used by SoDEX) were
        # unreachable. Phase 3 link-crawl now also has its own implicit budget
        # of 3 visits independent of max_attempts, so the catalog path catches
        # protocols whose audit page is at an unguessable custom URL but
        # linked from the brand homepage's nav.
        needs_k2_fallback = (
            (dl_audit_count is None or dl_audit_count == 0)
            and bounty_program == "none"
            and not precomputed_sources  # no wrapper detected yet
        )
        homepage_url = protocol.get("url") or (detail.get("url") if detail else None)
        if isinstance(homepage_url, str) or name:
            if needs_k2_fallback:
                scrape = await scrape_homepage_with_fallback(
                    homepage_url if isinstance(homepage_url, str) else None,
                    name,
                    client=client,
                    max_attempts=20,
                )
            else:
                # Phase 1 only — single URL, no derived URL fallback
                from tvl_scanner.enrich.homepage_scrape import scrape_homepage
                scrape = await scrape_homepage(
                    homepage_url if isinstance(homepage_url, str) else None,
                    client=client,
                )
            scrape_url_str = scrape.url or homepage_url  # use the URL that actually worked
            url_for_source = scrape_url_str if isinstance(scrape_url_str, str) and scrape_url_str.startswith("http") else None
            for firm in scrape.audit_firm_matches:
                precomputed_sources.append(
                    AuditSource(
                        source=AuditSourceKind.HOMEPAGE_SCRAPE,
                        url=url_for_source,
                        title=f"{firm} audit cited on protocol homepage",
                        weight=4,
                    )
                )
            for wrapper_tag in scrape.wrapper_matches:
                precomputed_sources.append(
                    AuditSource(
                        source=AuditSourceKind.HOMEPAGE_SCRAPE,
                        url=url_for_source,
                        title=f"Wrapper of {wrapper_tag} (cited on homepage)",
                        weight=4,
                    )
                )

            # Fallback step in github_repo resolution chain: if DefiLlama
            # and the curated registry both failed, try GitHub URLs found
            # in the homepage HTML. Ranked by name overlap with the slug
            # so we try the protocol's own repo before unrelated footer
            # links. Cap at 3 candidate URLs to bound API calls.
            if (repo_metadata is None or not repo_metadata.exists) and scrape.github_urls:
                ranked = rank_github_urls_for_protocol(
                    scrape.github_urls, slug=slug, display_name=name
                )
                for candidate_gh in ranked[:3]:
                    repo_metadata = await enrich_repo(candidate_gh, client=client)
                    if repo_metadata and repo_metadata.exists:
                        log.info(
                            "github resolved via homepage scrape: %s for %s",
                            candidate_gh, slug,
                        )
                        break

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
            github_repo=(repo_metadata.url if repo_metadata and repo_metadata.exists else None),
            loc_estimate=(repo_metadata.loc_estimate if repo_metadata else None),
            docs_url=None,
            bounty_program=bounty_program,
            bounty_url=bounty_url,
            bounty_max_payout_usd=bounty_payout,
            defillama_slug=slug,
            defillama_audit_links=merged_audit_links,
            defillama_audit_count=dl_audit_count,
            defillama_audit_note=dl_audit_note,
            github_audits_folder_exists=bool(
                repo_metadata and repo_metadata.audits_folder_exists
            ),
            github_audit_report_count=(
                repo_metadata.audit_report_count if repo_metadata else 0
            ),
            precomputed_audit_sources=precomputed_sources,
            onchain_address=onchain_address,
            solana_program_id=solana_program_id,
            solana_upgrade_authority=solana_upgrade_authority,
            solana_upgrade_authority_type=solana_upgrade_authority_type,
        )
    except Exception as exc:
        log.warning("defillama protocol discovery: skipped entry: %s", exc)
        return None


def _propagate_sibling_audits(
    enriched: list[EnrichedCandidate],
    catalog_protocols: list[dict[str, Any]],
) -> None:
    """BATCH Q: propagate audit signals across siblings in a parentProtocol group.

    Multi-product teams (Rho Labs, Pendle V1/V2/V3, etc.) publish audits once
    on the brand domain, but DefiLlama lists each sub-product as a separate
    protocol entry. The per-protocol homepage scrape misses the audit signal
    on siblings that live at sub-product subdomains (e.g. x.rho.trading).

    For each parentProtocol group with at least one audited sibling, append
    a PARENT_PROTOCOL AuditSource to every member that lacks its own audit
    signal. Mutates `enriched` in place.

    A sibling counts as "audited" if it has ANY of:
      - DefiLlama audit_count >= 1
      - precomputed_audit_sources of kind HOMEPAGE_SCRAPE / WRAPPER_PROGRAM /
        FACTORY_ATTRIBUTION (single-source override kinds in compute_score)
    """
    if not enriched or not catalog_protocols:
        return

    # Map enriched candidates → their raw catalog dict (for the parentProtocol
    # field, which isn't carried on the EnrichedCandidate model). Keyed by slug.
    by_slug_raw: dict[str, dict[str, Any]] = {
        str(p["slug"]): p for p in catalog_protocols if p.get("slug")
    }

    # Group enriched candidates by parentProtocol value
    groups: dict[str, list[EnrichedCandidate]] = {}
    for c in enriched:
        if not c.defillama_slug:
            continue
        raw = by_slug_raw.get(c.defillama_slug)
        if not raw:
            continue
        parent_id = raw.get("parentProtocol")
        if not parent_id:
            continue
        groups.setdefault(str(parent_id), []).append(c)

    STRONG_SOURCE_KINDS = {
        AuditSourceKind.HOMEPAGE_SCRAPE,
        AuditSourceKind.WRAPPER_PROGRAM,
        AuditSourceKind.FACTORY_ATTRIBUTION,
    }

    propagated_count = 0
    for parent_id, members in groups.items():
        if len(members) < 2:
            continue

        # Collect audited siblings and their evidence
        audited_siblings: list[tuple[EnrichedCandidate, str]] = []
        for m in members:
            evidence_summary: str | None = None
            if m.defillama_audit_count and m.defillama_audit_count >= 1:
                evidence_summary = (
                    f"DefiLlama reports {m.defillama_audit_count} audit(s)"
                )
            else:
                strong_firms = [
                    s.title or s.source
                    for s in m.precomputed_audit_sources
                    if AuditSourceKind(s.source) in STRONG_SOURCE_KINDS
                ]
                if strong_firms:
                    evidence_summary = "; ".join(strong_firms[:3])
            if evidence_summary:
                audited_siblings.append((m, evidence_summary))

        if not audited_siblings:
            continue

        # Find the strongest sibling — prefer HOMEPAGE_SCRAPE evidence (most
        # specific) over DefiLlama count (least specific). The first audited
        # sibling provides the credit string for the synthetic source.
        donor, donor_evidence = audited_siblings[0]
        for m, e in audited_siblings:
            if any(
                AuditSourceKind(s.source) == AuditSourceKind.HOMEPAGE_SCRAPE
                for s in m.precomputed_audit_sources
            ):
                donor, donor_evidence = m, e
                break

        # Members that lack BOTH a DefiLlama audit count AND any precomputed
        # source inherit a PARENT_PROTOCOL source. We do not overwrite — if
        # a sibling already has its own evidence, propagation adds no value.
        for m in members:
            has_own_signal = (
                (m.defillama_audit_count and m.defillama_audit_count >= 1)
                or bool(m.precomputed_audit_sources)
            )
            if has_own_signal:
                continue
            m.precomputed_audit_sources.append(
                AuditSource(
                    source=AuditSourceKind.PARENT_PROTOCOL,
                    title=(
                        f"Sibling protocol '{donor.defillama_slug}' is audited "
                        f"({donor_evidence}); parent group: {parent_id}"
                    ),
                    weight=4,
                )
            )
            propagated_count += 1

    if propagated_count:
        log.info(
            "sibling audit propagation: added PARENT_PROTOCOL source to %d "
            "candidates across %d parent groups",
            propagated_count,
            len(groups),
        )


async def _resolve_true_deploy_dates(
    results: list[EnrichedCandidate],
    client: httpx.AsyncClient | None,
) -> None:
    """Override `first_seen` with the TRUE on-chain deployment date for catalog
    candidates that exposed a contract address via the detail endpoint.

    Catalog records carry no real contract address (`address="defillama:{slug}"`)
    and fall back to a listedAt-based age that is frequently a 180-day placeholder
    (DefiLlama `listedAt` is null for most established protocols). This batch-
    resolves each protocol's governance/token contract creation date via Etherscan
    V2 (batched 5/call, throttled) and uses it as `first_seen`, so the freshness
    score and reported age reflect TRUE protocol age — the difference between
    surfacing a 5-year-old protocol as "180 days old" and as "5 years old".

    Mutates candidates in place. No-op when no candidate carries an
    `onchain_address` (tests, Solana-only runs) or when the etherscan key is
    absent (the underlying fetch returns {} and nothing is overridden).
    """
    from collections import defaultdict

    by_chain: dict[Chain, list[str]] = defaultdict(list)
    addr_index: dict[tuple[Chain, str], list[EnrichedCandidate]] = defaultdict(list)
    for cand in results:
        oc = cand.onchain_address
        if not oc or ":" not in oc:
            continue
        chain_str, _, addr = oc.partition(":")
        try:
            chain = Chain(chain_str)
        except ValueError:
            continue
        # Solana deploy dates are resolved inline via solana_rpc (getBlockTime);
        # fetch_creation_dates_batch is Etherscan V2 and can't resolve base58
        # program ids. Skip so we don't feed a Solana program id to Etherscan.
        if chain == Chain.SOLANA:
            continue
        by_chain[chain].append(addr)
        addr_index[(chain, addr.lower())].append(cand)

    if not by_chain:
        return

    total_with_addr = sum(len(v) for v in by_chain.values())
    resolved = 0
    for chain, addrs in by_chain.items():
        dates = await fetch_creation_dates_batch(chain, addrs, client=client)
        for addr_lower, deploy_date in dates.items():
            for cand in addr_index.get((chain, addr_lower), []):
                cand.first_seen = deploy_date
                resolved += 1

    log.info(
        "defillama catalog: resolved TRUE deploy date for %d/%d candidates with "
        "on-chain addresses (rest keep listedAt-based first_seen)",
        resolved,
        total_with_addr,
    )


async def discover_from_defillama_catalog(
    *,
    chains: list[Chain] | None = None,
    scan_date: date | None = None,
    client: httpx.AsyncClient | None = None,
    price_cache: PriceCache | None = None,
) -> list[EnrichedCandidate]:
    """Walk the DefiLlama catalog, apply filters, produce EnrichedCandidates.

    BATCH H fix #1: detail fetch + github enrichment now run concurrently with
    semaphore-bounded parallelism (default 10). For a typical catalog pass
    with ~150 qualifying entries this drops the stage from ~5 minutes
    (serial) to ~15-20 seconds, which was by far the biggest contributor to
    the ~6-minute total scan time.

    `chains` overrides the .env `CHAINS` setting (matches Stage 1 behavior).
    When None, falls back to `Settings.chain_list`. Without this parameter,
    a `--chains ethereum` CLI override was silently dropped here — leaving
    catalog discovery on the default `solana,arbitrum,base` set and filtering
    out Ethereum-only protocols (e.g. rho-x-lp-vault) regardless of what
    the user asked for.
    """
    s = settings()
    scan_date = scan_date or date.today()
    configured_chains = set(chains) if chains is not None else {Chain(c) for c in s.chain_list}

    catalog = DefiLlamaCatalog()
    await catalog.load(client=client)

    if not catalog.is_loaded() or not catalog._protocols:
        return []

    # Phase 1: cheap synchronous pre-filter to find which protocols are
    # worth the expensive HTTP work. Walks all 7000+ protocols but only
    # does dict lookups and arithmetic.
    to_process: list[tuple[dict[str, Any], Chain, date, float | None]] = []
    # Protocols whose money is real but sits on a chain this scanner cannot read
    # (Bitcoin, Hyperliquid L1, Monad, ICP, Ripple, ...). Before per-chain TVL
    # attribution these were scored as if the whole amount were on an EVM chain
    # we scan, which is how SUBFROST ($7.3M on Bitcoin, $6k on Ethereum) ranked
    # #1. They are now correctly excluded — but silently dropping 60+ funded
    # protocols would trade one blind spot for another, so count and report them.
    off_scope: list[tuple[str, float, str]] = []
    s_cfg = settings()

    for protocol in catalog._protocols:
        passes, chain, first_seen, chain_tvl = _passes_basic_filters(
            protocol, configured_chains, scan_date
        )
        if passes and chain and first_seen:
            to_process.append((protocol, chain, first_seen, chain_tvl))
            continue

        # Was this dropped only because the value lives off our chain set?
        total = protocol.get("tvl")
        if (
            str(protocol.get("category") or "") in SCANNABLE_CATEGORIES
            and isinstance(total, (int, float))
            and total >= s_cfg.MIN_TVL_USD
        ):
            per_chain = _chain_tvls(protocol)
            in_scope_max = max(
                (v for c, v in per_chain.items() if c in configured_chains),
                default=0.0,
            )
            if per_chain and in_scope_max < s_cfg.MIN_TVL_USD:
                richest = max(per_chain, key=lambda c: per_chain[c], default=None)
                where = richest.value if richest else "unsupported chain"
                # Name the biggest chain even when it is one we cannot map
                raw_ct = protocol.get("chainTvls")
                if isinstance(raw_ct, dict):
                    named = [
                        (k, v)
                        for k, v in raw_ct.items()
                        if isinstance(k, str)
                        and isinstance(v, (int, float))
                        and "-" not in k
                        and k.strip().lower() not in {"borrowed", "pool2", "staking"}
                    ]
                    if named:
                        where = max(named, key=lambda kv: kv[1])[0]
                off_scope.append((str(protocol.get("slug") or "?"), float(total), where))

    log.info(
        "defillama catalog pre-filter: %d of %d protocols qualify for enrichment",
        len(to_process),
        len(catalog._protocols),
    )

    if off_scope:
        off_scope.sort(key=lambda r: -r[1])
        log.info(
            "defillama catalog: %d funded protocols EXCLUDED because their TVL sits "
            "on chains outside the configured set — not a clean sweep of DeFi, only "
            "of %s. Largest: %s",
            len(off_scope),
            ",".join(sorted(c.value for c in configured_chains)),
            "; ".join(f"{slug} (${tvl:,.0f} on {where})" for slug, tvl, where in off_scope[:8]),
        )

    # Phase 2: concurrent per-protocol enrichment with bounded parallelism.
    # DefiLlama doesn't document a hard rate limit but 10 concurrent is well
    # below what they throttle on in practice (we have never seen a 429 from
    # /protocols or /protocol/{slug} in real scans).
    sem = asyncio.Semaphore(10)

    async def _bounded(
        protocol: dict[str, Any],
        chain: Chain,
        first_seen: date,
        chain_tvl: float | None,
    ) -> EnrichedCandidate | None:
        async with sem:
            return await _process_protocol(
                protocol,
                chain,
                first_seen,
                catalog,
                client,
                price_cache=price_cache,
                chain_tvl=chain_tvl,
            )

    task_results = await asyncio.gather(
        *(_bounded(p, c, fs, ct) for (p, c, fs, ct) in to_process)
    )

    results = [r for r in task_results if r is not None]

    # BATCH Q: sibling-protocol audit propagation. DefiLlama's `parentProtocol`
    # field groups multi-product teams under a single parent (e.g. rho-x +
    # rho-x-lp-vault + rho-vaults-v1 + rho-protocol all share `parent#rho`).
    # Audits published by the team — typically on a single brand domain —
    # apply to ALL siblings, but the per-protocol homepage scrape only fires
    # on each sibling's own `url` field. When a sibling lives at a sub-product
    # subdomain (e.g. x.rho.trading) that doesn't list audits, while another
    # sibling (rho.trading) does, the first is wrongly classified as under-
    # audited. Propagate sibling signals to fix this.
    _propagate_sibling_audits(results, catalog._protocols)

    # Resolve TRUE deploy dates for catalog candidates so freshness/age reflect
    # real protocol age, not DefiLlama's listedAt placeholder. Runs after all
    # per-protocol enrichment so addresses can be batched by chain (5/call).
    await _resolve_true_deploy_dates(results, client)

    log.info(
        "defillama catalog discovery: %d protocols matched filters (from %d total)",
        len(results),
        len(catalog._protocols),
    )
    return results
