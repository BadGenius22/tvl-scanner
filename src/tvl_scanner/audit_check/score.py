"""Audit density scoring and under-audited classification.

Stage 3 combines signals from multiple audit-history sources into a single
`audit_density_score` (integer, 0 = none found, higher = more audits). The
under_audited threshold is 2 — anything at or below is a candidate.

Weights (per the plan):
    DefiLlama audit_links:       1 point each, cap 3
    GitHub audits/ folder:       1 point (presence only — we don't count files)
    Solodit prior findings:      2 points (v2 — deferred)
    C4/Sherlock/Cantina hit:     3 points per unique contest match
    Protocol docs mention:       1 point each (v2 — deferred)
"""

from __future__ import annotations

import logging

from tvl_scanner.models import (
    AuditedCandidate,
    AuditSource,
    AuditSourceKind,
    EnrichedCandidate,
)

log = logging.getLogger(__name__)


# Cap per source kind to prevent one noisy source from dominating
CAPS: dict[AuditSourceKind, int] = {
    AuditSourceKind.DEFILLAMA: 3,
    AuditSourceKind.GITHUB_AUDITS_FOLDER: 1,
}

# Any candidate at or below this score is flagged as under-audited
UNDER_AUDITED_THRESHOLD = 2


def _defillama_sources(candidate: EnrichedCandidate) -> list[AuditSource]:
    """Build AuditSource entries from DefiLlama audit_links."""
    sources: list[AuditSource] = []
    for link in candidate.defillama_audit_links[: CAPS[AuditSourceKind.DEFILLAMA]]:
        sources.append(
            AuditSource(
                source=AuditSourceKind.DEFILLAMA,
                url=link,
                weight=1,
            )
        )
    return sources


def _github_folder_source(candidate: EnrichedCandidate) -> list[AuditSource]:
    """A single AuditSource if the github audits folder exists, else empty."""
    if not candidate.github_audits_folder_exists or not candidate.github_repo:
        return []
    audits_url = str(candidate.github_repo).rstrip("/") + "/tree/HEAD/audits"
    return [
        AuditSource(
            source=AuditSourceKind.GITHUB_AUDITS_FOLDER,
            url=audits_url,
            weight=1,
        )
    ]


def compute_score(
    candidate: EnrichedCandidate,
    *,
    contest_sources: list[AuditSource] | None = None,
) -> AuditedCandidate:
    """Combine all audit-history signals into an AuditedCandidate.

    Caller is responsible for fetching `contest_sources` (via the contests
    module) — this function is pure and synchronous so it's testable in
    isolation.
    """
    contest_sources = contest_sources or []

    all_sources: list[AuditSource] = []
    all_sources.extend(_defillama_sources(candidate))
    all_sources.extend(_github_folder_source(candidate))
    all_sources.extend(contest_sources)

    total_score = sum(src.weight for src in all_sources)
    under_audited = total_score <= UNDER_AUDITED_THRESHOLD

    return AuditedCandidate(
        **candidate.model_dump(),
        audit_density_score=total_score,
        audit_sources_found=all_sources,
        under_audited=under_audited,
    )
