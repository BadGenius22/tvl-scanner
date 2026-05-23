"""Stage 2 orchestrator: DiscoveredContract → EnrichedCandidate.

For each raw candidate from Stage 1:
  1. Look up protocol identity via DefiLlama (by protocol_guess name)
  2. If matched, extract github URL + audit_links from DefiLlama
  3. Query GitHub for LOC estimate and audits folder presence
  4. Fold all fields into an EnrichedCandidate

Candidates with no DefiLlama match are NOT dropped — they become
EnrichedCandidates with defensive defaults (display_name from protocol_guess
or address, protocol_type = "unknown protocol on {chain}"). A DefiLlama miss
is a positive signal for under-auditedness, not a reason to filter out.

The scanner's Stage 3 audit-check will still try other audit-history sources
(C4/Sherlock/Cantina contest search) for these unmatched records.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from tvl_scanner.config import settings
from tvl_scanner.enrich import bounty, github_registry
from tvl_scanner.enrich.defillama import DefiLlamaCatalog
from tvl_scanner.enrich.etherscan import VerificationResult, check_verification
from tvl_scanner.enrich.evm_bytecode_check import check_bytecode_match
from tvl_scanner.enrich.evm_factory_check import (
    check_factory_attribution,
    fetch_contract_name,
)
from tvl_scanner.enrich.github import RepoMetadata, enrich_repo
from tvl_scanner.enrich.homepage_scrape import (
    rank_github_urls_for_protocol,
    scrape_homepage_with_fallback,
)
from tvl_scanner.enrich.ottersec import check_ottersec_verification
from tvl_scanner.http import make_client
from tvl_scanner.models import (
    AuditSource,
    AuditSourceKind,
    Chain,
    DiscoveredContract,
    EnrichedCandidate,
    Language,
)

log = logging.getLogger(__name__)


# Chain → default language used to classify the protocol. A protocol may use
# multiple languages; this gives the primary one. GitHub's languages endpoint
# overrides this later if the repo reveals something richer.
CHAIN_DEFAULT_LANGUAGE: dict[Chain, Language] = {
    Chain.ETHEREUM: Language.SOLIDITY,
    Chain.ARBITRUM: Language.SOLIDITY,
    Chain.BASE: Language.SOLIDITY,
    Chain.OPTIMISM: Language.SOLIDITY,
    Chain.POLYGON: Language.SOLIDITY,
    Chain.BSC: Language.SOLIDITY,
    Chain.SOLANA: Language.RUST,
}


def _derive_languages(chain: Chain, repo: RepoMetadata | None) -> list[Language]:
    """Combine chain heuristic with GitHub language data."""
    langs: list[Language] = [CHAIN_DEFAULT_LANGUAGE[chain]]
    if not repo or not repo.languages:
        return langs

    seen: set[Language] = set(langs)
    name_to_enum = {
        "solidity": Language.SOLIDITY,
        "rust": Language.RUST,
        "move": Language.MOVE,
    }
    for lang_name in repo.languages:
        mapped = name_to_enum.get(lang_name.lower())
        if mapped and mapped not in seen:
            langs.append(mapped)
            seen.add(mapped)
    return langs


def _display_name(
    contract: DiscoveredContract, dl_match: dict[str, Any] | None
) -> str:
    if dl_match and dl_match.get("name"):
        return str(dl_match["name"])
    if contract.protocol_guess:
        return contract.protocol_guess
    # Shorten the address for readability
    return f"{contract.chain.value}:{contract.address[:10]}…"


def _protocol_type(
    contract: DiscoveredContract, dl_match: dict[str, Any] | None
) -> str:
    if dl_match:
        category = dl_match.get("category") or "protocol"
        return f"{category} on {contract.chain.value}"
    return f"unknown protocol on {contract.chain.value}"


def _target_slug(
    contract: DiscoveredContract, dl_match: dict[str, Any] | None
) -> str:
    if dl_match and dl_match.get("slug"):
        return str(dl_match["slug"])
    # Fall back to `<chain>-<shortaddr>` — unique, safe for filenames
    short = contract.address[:12].lower().lstrip("0x")
    return f"{contract.chain.value}-{short}"


def _audit_links(dl_match: dict[str, Any] | None) -> list[str]:
    """Extract DefiLlama's audit_links field, normalized to a list of URLs."""
    if not dl_match:
        return []
    raw = dl_match.get("audit_links") or []
    if isinstance(raw, str):
        raw = [raw]
    return [u for u in raw if isinstance(u, str) and u.startswith("http")]


def _coerce_audit_count(raw: Any) -> int | None:
    """DefiLlama reports `audits` as either int or stringified int. Normalize to int."""
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


async def enrich_one(
    contract: DiscoveredContract,
    catalog: DefiLlamaCatalog,
    *,
    client: Any = None,
) -> EnrichedCandidate:
    """Enrich a single contract. See module docstring for field derivation."""
    dl_match = catalog.lookup(contract.protocol_guess or "") if contract.protocol_guess else None

    github_url = None
    dl_audit_count: int | None = None
    dl_audit_note: str | None = None
    dl_slug: str | None = None
    if dl_match:
        # BATCH I fix #1.1: DefiLlama sometimes returns `github=['bareorgname']`
        # which looks like a URL but isn't parseable. Require "github.com" in
        # the candidate to accept it, else fall through to the URL field and
        # then the github_registry seed file.
        github_field = dl_match.get("github")
        candidate = None
        if isinstance(github_field, list) and github_field:
            candidate = str(github_field[0])
        elif isinstance(github_field, str):
            candidate = github_field
        if candidate and "github.com" in candidate:
            github_url = candidate

        # Some DefiLlama entries nest github under `url` — try that if nothing else
        if not github_url:
            url_field = dl_match.get("url")
            if isinstance(url_field, str) and "github.com" in url_field:
                github_url = url_field

        # Pull deeper audit metadata from the /protocol/{slug} detail endpoint.
        # This is the Batch D improvement: the flat catalog has `audits` as a
        # count and `audit_links` but NO `audit_note`. Detail has all three.
        slug = dl_match.get("slug")
        if slug:
            dl_slug = str(slug)
            detail = await catalog.fetch_detail(dl_slug, client=client)
            if detail:
                dl_audit_count = _coerce_audit_count(detail.get("audits"))
                note_raw = detail.get("audit_note")
                if isinstance(note_raw, str) and note_raw.strip():
                    dl_audit_note = note_raw.strip()
                # Also try to extract github URL from detail if flat was empty.
                # Same bare-org-name guard as above.
                if not github_url:
                    detail_gh = detail.get("github")
                    detail_candidate = None
                    if isinstance(detail_gh, list) and detail_gh:
                        detail_candidate = str(detail_gh[0])
                    elif isinstance(detail_gh, str):
                        detail_candidate = detail_gh
                    if detail_candidate and "github.com" in detail_candidate:
                        github_url = detail_candidate
            # Fallback to the flat catalog's `audits` field if detail didn't help
            if dl_audit_count is None:
                dl_audit_count = _coerce_audit_count(dl_match.get("audits"))

    # BATCH I fix #1: curated seed-file fallback when both DefiLlama paths fail
    if not github_url and dl_slug:
        github_url = github_registry.lookup(dl_slug)

    repo_metadata: RepoMetadata | None = None
    if github_url:
        repo_metadata = await enrich_repo(github_url, client=client)

    # Verification check — dispatches by chain. Etherscan V2 for EVM, OtterSec
    # reproducible-build registry for Solana. Synthetic `defillama:<slug>`
    # addresses fall through to empty VerificationResult in both paths.
    if contract.chain == Chain.SOLANA:
        verification: VerificationResult = await check_ottersec_verification(
            contract.address, client=client
        )
    else:
        verification = await check_verification(
            contract.chain, contract.address, client=client
        )

    # BATCH J3: EVM bytecode pattern check. For pool-based candidates with a
    # real EVM address (not synthetic defillama:slug), query eth_getCode and
    # check the keccak256 against our registry of known DEX pool patterns
    # (Uniswap V2/V3 pair, Curve, Balancer, etc.). If matched, the candidate
    # is a deployment of an audited factory and gets a synthetic AuditSource.
    precomputed_sources: list[AuditSource] = []
    if contract.chain != Chain.SOLANA and contract.address.startswith("0x"):
        bytecode_match = await check_bytecode_match(
            contract.chain, contract.address, client=client
        )
        if bytecode_match:
            precomputed_sources.append(
                AuditSource(
                    source=AuditSourceKind.WRAPPER_PROGRAM,
                    url=bytecode_match.entry.audit_url,  # type: ignore[arg-type]
                    title=(
                        f"Bytecode matches {bytecode_match.entry.name} "
                        f"(upstream: {bytecode_match.entry.upstream_protocol}, "
                        f"{bytecode_match.entry.audit_count} prior audits)"
                    ),
                    weight=max(4, bytecode_match.entry.audit_count),
                )
            )

        # BATCH N.5: source-code identifier attribution. When Etherscan
        # source verification is available and the source declares
        # `@author <protocol>` or has a meaningful contract_name, match the
        # author/name against the slug whitelist. Catches verified contracts
        # whose `name()` returns nothing (e.g. ether.fi TopUpDest is an
        # ERC1967Proxy named "TopUpDest" with @author ether.fi).
        verif_identifiers: list[str] = []
        if verification.source_author:
            verif_identifiers.append(verification.source_author)
        if verification.contract_name:
            verif_identifiers.append(verification.contract_name)
        if verification.source_title:
            verif_identifiers.append(verification.source_title)
        if verification.source_project_dir:
            verif_identifiers.append(verification.source_project_dir)

        # If the candidate is a proxy with a verified implementation, ALSO
        # fetch the impl's verification — the proxy's source is just
        # ERC1967Proxy boilerplate, the protocol identity lives on the impl.
        if verification.is_proxy and verification.proxy_impl_address:
            impl_verif = await check_verification(
                contract.chain, verification.proxy_impl_address, client=client
            )
            if impl_verif.source_author:
                verif_identifiers.append(impl_verif.source_author)
            if impl_verif.contract_name and impl_verif.contract_name != "ERC1967Proxy":
                verif_identifiers.append(impl_verif.contract_name)
            if impl_verif.source_title:
                verif_identifiers.append(impl_verif.source_title)
            if impl_verif.source_project_dir:
                verif_identifiers.append(impl_verif.source_project_dir)

        # Match against the slug whitelist (same prefixes used in score.py).
        # We import lazily to avoid circular import.
        from tvl_scanner.audit_check.score import KNOWN_AUDITED_SLUG_PREFIXES
        for ident in verif_identifiers:
            ident_clean = ident.lower().replace(".", "-").replace(" ", "-")
            if any(ident_clean.startswith(p) for p in KNOWN_AUDITED_SLUG_PREFIXES):
                precomputed_sources.append(
                    AuditSource(
                        source=AuditSourceKind.FACTORY_ATTRIBUTION,
                        url=None,
                        title=(
                            f"Verified source identifier '{ident}' matches "
                            f"known audited protocol family — audit attribution by source"
                        ),
                        weight=4,
                    )
                )
                break

        # BATCH N: factory-attribution check. Catches the case where the
        # bytecode registry is empty/incomplete — calls factory() and matches
        # against a curated table of well-known DEX factory addresses. The
        # v0.6.0 scan ranked the canonical Uniswap V3 WBTC/WETH pool at #1
        # because none of the prior signals fired; this one would have.
        factory_match = await check_factory_attribution(
            contract.chain, contract.address, client=client
        )
        if factory_match:
            precomputed_sources.append(
                AuditSource(
                    source=AuditSourceKind.FACTORY_ATTRIBUTION,
                    url=factory_match.entry.audit_url,  # type: ignore[arg-type]
                    title=(
                        f"factory() returns {factory_match.entry.name} factory "
                        f"({factory_match.factory_address}) — pool of audited "
                        f"upstream protocol {factory_match.entry.upstream_protocol}"
                    ),
                    weight=4,
                )
            )

    # BATCH K + K2: homepage scrape with multi-URL fallback for pool-based
    # candidates. Phase 1 tries the DefiLlama url; Phase 2 derives candidate
    # URLs from the protocol display_name when Phase 1 returns empty.
    if dl_match:
        homepage_url = dl_match.get("url") if isinstance(dl_match.get("url"), str) else None
        display_name_for_scrape = _display_name(contract, dl_match)
        if homepage_url or display_name_for_scrape:
            scrape = await scrape_homepage_with_fallback(
                homepage_url, display_name_for_scrape, client=client
            )
            scrape_url_str = scrape.url or homepage_url
            url_for_source = scrape_url_str if isinstance(scrape_url_str, str) and scrape_url_str.startswith("http") else None
            for firm in scrape.audit_firm_matches:
                precomputed_sources.append(
                    AuditSource(
                        source=AuditSourceKind.HOMEPAGE_SCRAPE,
                        url=url_for_source,  # type: ignore[arg-type]
                        title=f"{firm} audit cited on protocol homepage",
                        weight=4,
                    )
                )
            for wrapper_tag in scrape.wrapper_matches:
                precomputed_sources.append(
                    AuditSource(
                        source=AuditSourceKind.HOMEPAGE_SCRAPE,
                        url=url_for_source,  # type: ignore[arg-type]
                        title=f"Wrapper of {wrapper_tag} (cited on homepage)",
                        weight=4,
                    )
                )

            # Fallback step in github_repo resolution: if DefiLlama and
            # the curated registry both failed, try GitHub URLs found
            # in the homepage HTML, ranked by name overlap with the slug.
            if (repo_metadata is None or not repo_metadata.exists) and scrape.github_urls:
                slug_for_rank = (
                    str(dl_match.get("slug")) if dl_match and dl_match.get("slug") else None
                )
                ranked = rank_github_urls_for_protocol(
                    scrape.github_urls,
                    slug=slug_for_rank,
                    display_name=display_name_for_scrape,
                )
                for candidate_gh in ranked[:3]:
                    repo_metadata = await enrich_repo(candidate_gh, client=client)
                    if repo_metadata and repo_metadata.exists:
                        log.info(
                            "github resolved via homepage scrape: %s for %s",
                            candidate_gh,
                            display_name_for_scrape or contract.address,
                        )
                        break

    languages = _derive_languages(contract.chain, repo_metadata)

    # Batch N.4: if DefiLlama didn't supply a display_name (i.e. an RPC-
    # discovered contract that's not in the catalog), fetch the contract's
    # on-chain `name()` and use it. Without this, Ostium LP ($29M Arbitrum)
    # shows up in the report as "arbitrum:0x20d419a8…" instead of "ostiumLP" —
    # the protocol is identifiable on-chain but invisible to a reader.
    on_chain_name: str | None = None
    if (
        not dl_match
        and contract.chain != Chain.SOLANA
        and contract.address.startswith("0x")
    ):
        on_chain_name = await fetch_contract_name(
            contract.chain, contract.address, client=client
        )

    # Bounty registry lookup (seeds file) — upgrades bounty_program from "none"
    # if the candidate matches a known public bounty.
    bounty_entry = bounty.match(
        display_name=on_chain_name or _display_name(contract, dl_match),
        defillama_slug=str(dl_match["slug"]) if dl_match and dl_match.get("slug") else None,
        target_name=_target_slug(contract, dl_match),
    )
    bounty_program = bounty_entry.platform if bounty_entry else "none"
    bounty_url_raw = bounty_entry.url if bounty_entry else None
    bounty_payout = bounty_entry.max_payout_usd if bounty_entry else None

    return EnrichedCandidate(
        chain=contract.chain,
        address=contract.address,
        tvl_usd=contract.tvl_usd,
        first_seen=contract.first_seen,
        unique_users_30d=contract.unique_users_30d,
        source=contract.source,
        target_name=_target_slug(contract, dl_match),
        display_name=on_chain_name or _display_name(contract, dl_match),
        protocol_type=_protocol_type(contract, dl_match),
        languages=languages,
        github_repo=repo_metadata.url if repo_metadata and repo_metadata.exists else None,
        loc_estimate=repo_metadata.loc_estimate if repo_metadata else None,
        docs_url=None,  # v1: docs discovery deferred to a later batch
        bounty_program=bounty_program,  # type: ignore[arg-type]
        bounty_url=bounty_url_raw,  # type: ignore[arg-type]
        bounty_max_payout_usd=bounty_payout,
        defillama_slug=str(dl_match["slug"]) if dl_match and dl_match.get("slug") else None,
        defillama_audit_links=_audit_links(dl_match),
        defillama_audit_count=dl_audit_count,
        defillama_audit_note=dl_audit_note,
        github_audits_folder_exists=bool(
            repo_metadata and repo_metadata.audits_folder_exists
        ),
        is_verified=verification.is_verified,
        contract_name=verification.contract_name,
        is_proxy=verification.is_proxy,
        proxy_impl_address=verification.proxy_impl_address,
        compiler_version=verification.compiler_version,
        precomputed_audit_sources=precomputed_sources,
    )


async def enrich_all(
    contracts: list[DiscoveredContract],
) -> list[EnrichedCandidate]:
    """Enrich the Stage 1 candidate list. Loads DefiLlama catalog once up front."""
    async with make_client() as client:
        catalog = DefiLlamaCatalog()
        await catalog.load(client=client)

        # Run GitHub lookups with bounded concurrency to stay under rate limits
        sem = asyncio.Semaphore(10)

        async def _bounded(c: DiscoveredContract) -> EnrichedCandidate:
            async with sem:
                return await enrich_one(c, catalog, client=client)

        results = await asyncio.gather(*(_bounded(c) for c in contracts))
    log.info("enrich: %d candidates enriched", len(results))
    return list(results)


def write_enriched(
    candidates: list[EnrichedCandidate], path: Path | None = None
) -> Path:
    s = settings()
    path = path or (s.artifacts_path / "enriched.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [c.model_dump(mode="json") for c in candidates]
    path.write_text(json.dumps(records, indent=2, default=str))
    log.info("wrote %d enriched candidates to %s", len(candidates), path)
    return path
