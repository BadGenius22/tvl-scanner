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
from tvl_scanner.enrich.defillama import DefiLlamaCatalog
from tvl_scanner.enrich.github import RepoMetadata, enrich_repo
from tvl_scanner.http import make_client
from tvl_scanner.models import (
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


async def enrich_one(
    contract: DiscoveredContract,
    catalog: DefiLlamaCatalog,
    *,
    client: Any = None,
) -> EnrichedCandidate:
    """Enrich a single contract. See module docstring for field derivation."""
    dl_match = catalog.lookup(contract.protocol_guess or "") if contract.protocol_guess else None

    github_url = None
    if dl_match:
        github_field = dl_match.get("github")
        if isinstance(github_field, list) and github_field:
            github_url = str(github_field[0])
        elif isinstance(github_field, str):
            github_url = github_field
        # Some DefiLlama entries nest github under `url` — try that if nothing else
        if not github_url:
            url_field = dl_match.get("url")
            if isinstance(url_field, str) and "github.com" in url_field:
                github_url = url_field

    repo_metadata: RepoMetadata | None = None
    if github_url:
        repo_metadata = await enrich_repo(github_url, client=client)

    languages = _derive_languages(contract.chain, repo_metadata)

    return EnrichedCandidate(
        chain=contract.chain,
        address=contract.address,
        tvl_usd=contract.tvl_usd,
        first_seen=contract.first_seen,
        unique_users_30d=contract.unique_users_30d,
        source=contract.source,
        target_name=_target_slug(contract, dl_match),
        display_name=_display_name(contract, dl_match),
        protocol_type=_protocol_type(contract, dl_match),
        languages=languages,
        github_repo=repo_metadata.url if repo_metadata and repo_metadata.exists else None,
        loc_estimate=repo_metadata.loc_estimate if repo_metadata else None,
        docs_url=None,  # v1: docs discovery deferred to v2
        bounty_program="none",  # v1: bounty lookup deferred to v2
        bounty_url=None,
        bounty_max_payout_usd=None,
        defillama_slug=str(dl_match["slug"]) if dl_match and dl_match.get("slug") else None,
        defillama_audit_links=_audit_links(dl_match),
        github_audits_folder_exists=bool(
            repo_metadata and repo_metadata.audits_folder_exists
        ),
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
