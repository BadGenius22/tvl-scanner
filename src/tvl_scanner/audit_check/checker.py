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

from tvl_scanner.audit_check.contests import ContestHit, check_all_contests
from tvl_scanner.audit_check.score import compute_score
from tvl_scanner.config import settings
from tvl_scanner.http import make_client
from tvl_scanner.models import AuditedCandidate, AuditSourceKind, EnrichedCandidate

log = logging.getLogger(__name__)


async def check_one(
    candidate: EnrichedCandidate,
    *,
    client: object = None,
    token_cache: dict[tuple[str, AuditSourceKind], list[ContestHit]] | None = None,
) -> AuditedCandidate:
    """Run audit-history checks on a single candidate.

    BATCH H fix #2: skip GitHub contest search entirely for candidates where
    DefiLlama already reports a non-zero audit count. Stage 3's real purpose
    is to find audit history that DefiLlama missed; when DefiLlama already
    has the data, spending three API calls per org to re-confirm is wasted
    work AND it saturates GitHub search's 30-req-per-minute rate limit which
    caused 403s on late candidates in v0.3.0. Net effect: Stage 3 now does
    ~80% fewer GitHub calls and no longer hits rate limits.
    """
    has_defillama_audits = (
        candidate.defillama_audit_count is not None
        and candidate.defillama_audit_count > 0
    )
    if has_defillama_audits:
        contest_sources: list = []
    else:
        contest_sources = await check_all_contests(
            candidate.display_name,
            defillama_slug=candidate.defillama_slug,
            client=client,  # type: ignore[arg-type]
            token_cache=token_cache,
        )
    return compute_score(candidate, contest_sources=contest_sources)


async def check_all(
    candidates: list[EnrichedCandidate],
) -> list[AuditedCandidate]:
    """Run Stage 3 on the full enriched list with bounded concurrency.

    BATCH G FIX #3: uses a per-scan token cache shared across all candidates.
    Protocols sharing a brand token (Aave / Aave V2 / Aave V3 all normalize
    to 'aave') cost only one HTTP round-trip. Concurrency also lowered from
    5 to 2 because GitHub search API has a 30/min rate limit separate from
    the 5000/hr core API.
    """
    token_cache: dict[tuple[str, AuditSourceKind], list[ContestHit]] = {}
    async with make_client() as client:
        sem = asyncio.Semaphore(2)

        async def _bounded(c: EnrichedCandidate) -> AuditedCandidate:
            async with sem:
                return await check_one(c, client=client, token_cache=token_cache)

        results = await asyncio.gather(*(_bounded(c) for c in candidates))

    log.info(
        "audit-check: token_cache held %d unique (token,org) pairs — "
        "saved ~%d api calls",
        len(token_cache),
        max(0, len(candidates) * 3 * 2 - len(token_cache)),
    )

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
