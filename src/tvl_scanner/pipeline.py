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
        catalog_enriched = await discover_from_defillama_catalog(
            scan_date=scan_date, client=client
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
    ranked = rank_all(audited, scan_date=scan_date, cutoff=cutoff, cap=cap)
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
