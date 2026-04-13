"""Stage 3 orchestrator: EnrichedCandidate → AuditedCandidate.

For each enriched candidate:
  1. Gather DefiLlama audit links (already in the enriched record, no fetch)
  2. Gather GitHub audits/ folder signal (already in the enriched record)
  3. Query GitHub search for C4/Sherlock/Cantina audit-org repos matching
     the protocol name (async, concurrency-capped)
  4. Call compute_score to fold everything into an AuditedCandidate

Output: `artifacts/audit_status.json` — full AuditedCandidate records, not
just the under-audited ones. Stage 4 ranking needs the full set to compute
the audit_gap_score for every candidate.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from tvl_scanner.audit_check.contests import check_all_contests
from tvl_scanner.audit_check.score import compute_score
from tvl_scanner.config import settings
from tvl_scanner.http import make_client
from tvl_scanner.models import AuditedCandidate, EnrichedCandidate

log = logging.getLogger(__name__)


async def check_one(
    candidate: EnrichedCandidate, *, client: object = None
) -> AuditedCandidate:
    """Run audit-history checks on a single candidate."""
    contest_sources = await check_all_contests(
        candidate.display_name,
        defillama_slug=candidate.defillama_slug,
        client=client,  # type: ignore[arg-type]
    )
    return compute_score(candidate, contest_sources=contest_sources)


async def check_all(
    candidates: list[EnrichedCandidate],
) -> list[AuditedCandidate]:
    """Run Stage 3 on the full enriched list with bounded concurrency."""
    async with make_client() as client:
        # GitHub search is rate-limited to 30/min for the search endpoint.
        # Keep concurrency low so we don't burst over the bucket.
        sem = asyncio.Semaphore(5)

        async def _bounded(c: EnrichedCandidate) -> AuditedCandidate:
            async with sem:
                return await check_one(c, client=client)

        results = await asyncio.gather(*(_bounded(c) for c in candidates))

    n_under = sum(1 for r in results if r.under_audited)
    log.info("audit-check: %d/%d candidates under-audited", n_under, len(results))
    return list(results)


def write_audit_status(
    candidates: list[AuditedCandidate], path: Path | None = None
) -> Path:
    s = settings()
    path = path or (s.artifacts_path / "audit_status.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [c.model_dump(mode="json") for c in candidates]
    path.write_text(json.dumps(records, indent=2, default=str))
    log.info("wrote %d audit_status records to %s", len(candidates), path)
    return path
