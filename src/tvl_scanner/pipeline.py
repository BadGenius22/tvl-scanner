"""Top-level pipeline orchestrator.

Runs all four stages in sequence, writing intermediate JSON artifacts at each
boundary so a failure mid-pipeline does not lose the work already done:

    Stage 1 → artifacts/candidates.json
    Stage 2 → artifacts/enriched.json
    Stage 3 → artifacts/audit_status.json
    Stage 4 → reports/YYYY-MM-DD-scan.md + reports/YYYY-MM-DD-scan/candidates/

Each stage reads its input from memory (not disk) during a single run. The
disk artifacts are a debugging/inspection aid, not a hand-off mechanism.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from tvl_scanner.audit_check.checker import check_all, write_audit_status
from tvl_scanner.discover.merge import discover_all, write_candidates
from tvl_scanner.enrich.defillama_protocols import discover_from_defillama_catalog
from tvl_scanner.enrich.enricher import enrich_all, write_enriched
from tvl_scanner.http import make_client
from tvl_scanner.models import Chain, EnrichedCandidate
from tvl_scanner.rank.priority import rank_all
from tvl_scanner.rank.report import write_report

log = logging.getLogger(__name__)


def _dedupe_enriched(candidates: list[EnrichedCandidate]) -> list[EnrichedCandidate]:
    """Deduplicate the merged enriched list.

    A protocol can appear from TWO sources: as a pool on GeckoTerminal/Birdeye
    (Stage 1 path) and as a direct entry in the DefiLlama catalog (Stage 2 path).
    When both match the same defillama_slug, prefer the DefiLlama catalog
    record because it's protocol-level (higher TVL, proper category) while the
    pool record is just one of the protocol's pools.
    """
    by_slug: dict[str, EnrichedCandidate] = {}
    no_slug: list[EnrichedCandidate] = []
    for c in candidates:
        if c.defillama_slug:
            prev = by_slug.get(c.defillama_slug)
            # Keep the one with larger TVL (catalog TVL is usually higher)
            if prev is None or c.tvl_usd > prev.tvl_usd:
                by_slug[c.defillama_slug] = c
        else:
            no_slug.append(c)
    return list(by_slug.values()) + no_slug


async def run_pipeline(
    chains: list[Chain] | None = None,
    *,
    scan_date: date | None = None,
    cutoff: float = 5.0,
    cap: int = 50,
    exclude_slugs: set[str] | None = None,
) -> Path:
    """Run the full pipeline. Two parallel discovery paths (address-based pools
    and protocol-level catalog) feed into unified enrichment and ranking.
    """
    scan_date = scan_date or date.today()

    log.info("=== Stage 1: Discover (pool-based) ===")
    discovered = await discover_all(chains, scan_date=scan_date)
    write_candidates(discovered)
    log.info("discovered %d pool-based candidates above threshold", len(discovered))

    log.info("=== Stage 1.5: DefiLlama catalog discovery ===")
    async with make_client() as client:
        from tvl_scanner.enrich.prices import PriceCache
        catalog_price_cache = PriceCache()
        catalog_enriched = await discover_from_defillama_catalog(
            chains=chains,
            scan_date=scan_date,
            client=client,
            price_cache=catalog_price_cache,
        )
    log.info("discovered %d catalog-based candidates", len(catalog_enriched))

    if not discovered and not catalog_enriched:
        log.warning("no candidates from any source — nothing to do")
        return Path("/dev/null")

    log.info("=== Stage 2: Enrich pool-based candidates ===")
    pool_enriched = await enrich_all(discovered) if discovered else []
    log.info("enriched %d pool-based candidates", len(pool_enriched))

    # Merge and dedupe
    enriched = _dedupe_enriched(pool_enriched + catalog_enriched)
    write_enriched(enriched)
    log.info(
        "combined enriched candidates: %d (pool=%d + catalog=%d, deduped from %d)",
        len(enriched),
        len(pool_enriched),
        len(catalog_enriched),
        len(pool_enriched) + len(catalog_enriched),
    )

    log.info("=== Stage 3: Audit-check ===")
    audited = await check_all(enriched)
    write_audit_status(audited)
    n_under = sum(1 for a in audited if a.under_audited)
    log.info("audit-check: %d / %d are under-audited", n_under, len(audited))

    log.info("=== Stage 4: Rank + Report ===")
    ranked = rank_all(
        audited,
        scan_date=scan_date,
        cutoff=cutoff,
        cap=cap,
        exclude_slugs=exclude_slugs,
    )
    summary_path, candidate_paths = write_report(ranked, scan_date)
    log.info(
        "ranked %d candidates (cutoff=%.1f, cap=%d); wrote %d per-candidate files",
        len(ranked),
        cutoff,
        cap,
        len(candidate_paths),
    )
    log.info("summary report: %s", summary_path)
    return summary_path


async def run_immunefi_scan(
    chains: list[Chain] | None = None,
    *,
    scan_date: date | None = None,
    cutoff: float = 5.0,
    cap: int = 60,
    kyc: bool | None = None,
    min_bounty: int | None = None,
    exclude_slugs: set[str] | None = None,
    exclude_invite_only: bool = False,
) -> Path:
    """Rank the FULL live Immunefi bounty universe on the 12 target-selection criteria.

    Unlike `run_pipeline` (which discovers by TVL pool / DefiLlama catalog and then
    tags whichever protocols happen to have a bounty), this seeds a candidate from
    every active Immunefi program, so a live bounty is never missed just because
    the TVL-pool discovery didn't independently surface its protocol. TVL and
    deploy-age are resolved best-effort; the bounty, in-scope addresses, and prior-
    audit record come straight from Immunefi.

    Ranking uses `rank/bounty_priority.py`, not the 6-factor discovery formula:
    every candidate here already has a bounty, so that formula's `bounty_score`
    term is a constant and its `activity_score` term is always neutral. The
    12-criteria formula scores what actually separates bounty targets — payout
    size and how it is computed, program age and staleness, known-issue density,
    scope churn, competition and resolution quality. Writes
    reports/YYYY-MM-DD-immunefi-scan.md.
    """
    from tvl_scanner.enrich.immunefi_catalog import discover_from_immunefi_catalog
    from tvl_scanner.rank.bounty_priority import rank_all_bounty

    scan_date = scan_date or date.today()

    log.info("=== Immunefi bounty-universe scan ===")
    async with make_client() as client:
        candidates = await discover_from_immunefi_catalog(
            chains=chains,
            scan_date=scan_date,
            client=client,
            kyc=kyc,
            min_bounty=min_bounty,
        )
    log.info("seeded %d candidates from the Immunefi catalogue", len(candidates))

    if not candidates:
        log.warning("no Immunefi candidates — nothing to do")
        return Path("/dev/null")

    log.info("=== Stage 3: Audit-check ===")
    audited = await check_all(candidates)
    write_audit_status(audited)
    n_under = sum(1 for a in audited if a.under_audited)
    log.info("audit-check: %d / %d are under-audited", n_under, len(audited))

    log.info("=== Stage 4: Rank + Report (12-criteria bounty formula) ===")
    ranked = rank_all_bounty(
        audited,
        scan_date=scan_date,
        cutoff=cutoff,
        cap=cap,
        exclude_slugs=exclude_slugs,
        exclude_invite_only=exclude_invite_only,
    )
    summary_path, candidate_paths = write_report(ranked, scan_date, label="immunefi-scan")
    log.info(
        "ranked %d bounty candidates (cutoff=%.1f, cap=%d); wrote %d per-candidate files",
        len(ranked),
        cutoff,
        cap,
        len(candidate_paths),
    )
    log.info("summary report: %s", summary_path)
    return summary_path
