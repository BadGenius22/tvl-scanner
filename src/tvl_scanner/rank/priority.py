"""Composite priority score computation.

Every candidate (under-audited or not) gets a priority score on a 0-10 scale.
The weighted sum of six sub-scores. Filter threshold: priority >= 5.0.

Per the plan:
    priority = tvl_score * 0.25
             + freshness_score * 0.20
             + audit_gap_score * 0.30
             + activity_score * 0.15
             + edge_match_score * 0.10
             + bounty_score * 0.10

Each sub-score is normalized to [0, 10] so the weighted sum is also [0, 10].
"""

from __future__ import annotations

import math
from datetime import date

from tvl_scanner.config import settings
from tvl_scanner.models import AuditedCandidate, CandidateRecord

# Weight distribution — sums to 1.0
W_TVL = 0.25
W_FRESH = 0.20
W_AUDIT_GAP = 0.30
W_ACTIVITY = 0.15
W_EDGE_MATCH = 0.10
W_BOUNTY = 0.10

# Priority cutoff for inclusion in the final report
PRIORITY_CUTOFF = 5.0

# Protocol-type tokens whose value depends on a price feed. Price-oracle
# manipulation is the single most-exploited bug class in the DeFiHackLabs
# corpus, so any candidate in one of these classes gets an oracle-focused
# audit hint. Matched as substrings against the lowercased protocol_type
# ("Lending on arbitrum", "Leveraged Farming on base", ...).
_PRICE_SENSITIVE_TYPE_TOKENS: tuple[str, ...] = (
    "lend",
    "borrow",
    "cdp",
    "collateral",
    "derivativ",
    "perp",
    "option",
    "synthetic",
    "yield",
    "vault",
    "leverage",
    "money market",
    "stablecoin",
)


def tvl_score(tvl_usd: float) -> float:
    """Log-scaled TVL score: $100K → 0, $1M → 5, $10M → 10, capped.

    Below $100K returns 0 (shouldn't happen — those are filtered in Stage 1).
    Above $10M stays at 10 since a bigger TVL doesn't make a bug more valuable.
    """
    if tvl_usd <= 0:
        return 0.0
    log_tvl = math.log10(tvl_usd)
    # log10($100K) = 5, log10($10M) = 7 → map [5, 7] → [0, 10]
    raw = (log_tvl - 5.0) * 5.0
    return max(0.0, min(10.0, raw))


def freshness_score(age_days: int, max_age_days: int) -> float:
    """Linear decay from 10 (brand new) to 0 (at max_age_days)."""
    if age_days < 0:
        return 0.0
    if age_days >= max_age_days:
        return 0.0
    return 10.0 * (1.0 - age_days / max_age_days)


def audit_gap_score(audit_density_score: int, resolved: bool = True) -> float:
    """Inverse of audit density. 0 audits → 10, 5+ audits → 0.

    `resolved=False` means no audit source was consultable, so a score of 0
    is "unknown", not "zero audits". Unknown returns a neutral 5.0 — the same
    convention `activity_score` already uses for a None user count. Awarding
    the full 10.0 there is what surfaced Pareto Credit (14 audits, published
    only on its own docs site) at rank 2 of a live scan.
    """
    if not resolved:
        return 5.0
    return max(0.0, 10.0 - 2.0 * audit_density_score)


def activity_score(unique_users_30d: int | None) -> float:
    """Log-scaled user activity. None (unknown) gets a neutral 5.

    10 users → ~2.5, 100 → 5, 1000 → 7.5, 10000+ → 10
    """
    if unique_users_30d is None:
        return 5.0
    if unique_users_30d <= 0:
        return 0.0
    raw = math.log10(unique_users_30d + 1) * 2.5
    return max(0.0, min(10.0, raw))


def edge_match_score(candidate: AuditedCandidate) -> tuple[float, list[str]]:
    """Score +10 if 2+ edge keywords match, +5 if 1, 0 if none. Returns (score, keywords_hit)."""
    s = settings()
    haystack = " ".join(
        filter(
            None,
            [
                candidate.display_name.lower(),
                candidate.protocol_type.lower(),
                candidate.target_name.lower(),
                (candidate.defillama_slug or "").lower(),
            ],
        )
    )
    hits = [kw for kw in s.EDGE_MATCH_KEYWORDS if kw in haystack]
    if len(hits) >= 2:
        return 10.0, hits
    if len(hits) == 1:
        return 5.0, hits
    return 0.0, hits


def bounty_score(candidate: AuditedCandidate) -> float:
    """10 if the protocol has any public bounty program, else 0."""
    return 10.0 if candidate.bounty_program != "none" else 0.0


def _infer_platform(candidate: AuditedCandidate) -> str:
    if candidate.bounty_program == "immunefi":
        return "immunefi"
    if candidate.bounty_program != "none":
        return "immunefi"  # HackerOne/HackenProof also map to public bounty platforms
    return "private"


def _infer_mode(candidate: AuditedCandidate) -> str:
    if candidate.bounty_program != "none":
        return "bug-bounty"
    return "private"


def _why_interesting(
    candidate: AuditedCandidate,
    age_days: int,
    edge_keywords: list[str],
) -> str:
    """Auto-generate the one-sentence summary shown in the report table."""
    parts: list[str] = []
    parts.append(f"{candidate.protocol_type}")
    parts.append(f"${int(candidate.tvl_usd):,} TVL")
    parts.append(f"{age_days}d old")
    if candidate.loc_estimate:
        parts.append(f"~{candidate.loc_estimate} LOC")
    if candidate.audit_density_score == 0:
        parts.append("no prior audits found")
    else:
        parts.append(f"audit_density={candidate.audit_density_score}")
    if edge_keywords:
        parts.append(f"edge-match: {', '.join(edge_keywords)}")
    if candidate.bounty_program != "none":
        parts.append(f"bounty: {candidate.bounty_program}")
    return " • ".join(parts)


def _focus_areas(
    candidate: AuditedCandidate, edge_keywords: list[str], *, scan_date: date
) -> list[str]:
    """Generate suggested focus areas for the VAULT_CONTEXT.md lift.

    Hints are emitted in priority order: verification red flags first (they
    gate whether the candidate is even worth auditing), then edge-match
    specializations, then generic hints. Capped at 5 total.
    """
    suggestions: list[str] = []

    # On-chain verification hints — highest priority, directly actionable.
    # Semantics differ by chain: EVM unverified is a red flag (verification is
    # nearly universal), Solana unverified just means "not in OtterSec DB"
    # which is the default for most programs.
    is_solana = candidate.chain.value == "solana"
    if not is_solana and candidate.is_verified is False:
        suggestions.append(
            "⚠ UNVERIFIED on Etherscan — source code is not public. Confirm the team has a plan to verify "
            "before committing audit time; auditing unverified bytecode is rarely productive."
        )
    elif is_solana and candidate.is_verified:
        suggestions.append(
            "✓ OtterSec reproducible build registered — the github_repo matches deployed bytecode. "
            "Audit against the verified commit, not the latest `main`."
        )
    elif is_solana and candidate.is_verified is False:
        suggestions.append(
            "Not registered in OtterSec verified-builds DB (default for most Solana programs). "
            "If this candidate progresses to audit, run `solana-verify` yourself to confirm the "
            "github_repo commit matches the deployed bytecode before starting."
        )
    elif candidate.is_proxy:
        impl = candidate.proxy_impl_address or "impl slot"
        suggestions.append(
            f"EIP-1967 proxy detected → implementation at `{impl}`. Audit BOTH slots: the proxy itself "
            f"(upgrade authority, initializer guard) and the current implementation. Check for upgrade "
            f"race conditions and uninitialized slot exploits."
        )

    # Edge-match hints
    if "leverage" in edge_keywords:
        suggestions.append(
            "Prioritize leverage-loop and flash-loan entry points — brand match signals leverage logic"
        )
    if "vault" in edge_keywords:
        suggestions.append(
            "Audit share/asset conversion math (convertToAssets/convertToShares rounding) — "
            "ERC4626 first-depositor and donation-based share inflation are recurrent "
            "(e.g. Edel xStock, 2026)"
        )
    if any(k in edge_keywords for k in ("aave", "compound", "silo", "pendle")):
        suggestions.append(
            "Check integration seams with external lending/yield primitive — cross-protocol trust boundary"
        )
    if any(k in edge_keywords for k in ("zk", "noir", "anchor")):
        suggestions.append(
            "Solana-specific: verify account validation, PDA derivation, and Anchor constraint coverage"
        )

    # Oracle-manipulation hint — grounded in the DeFiHackLabs corpus, where
    # price-oracle manipulation is the most-exploited bug class (270+ incidents)
    # and dominates 2026 losses. Fire it for protocols whose solvency depends on
    # a price feed. Placed after the more-specific edge hints so those keep their
    # slots (the list is capped at 5), but ahead of the generic freshness/TVL
    # hints since it points at the highest-probability failure surface.
    is_price_sensitive = any(
        tok in candidate.protocol_type.lower() for tok in _PRICE_SENSITIVE_TYPE_TOKENS
    ) or any(k in edge_keywords for k in ("aave", "compound", "silo", "pendle", "leverage"))
    if is_price_sensitive:
        suggestions.append(
            "Price-oracle manipulation is the most-exploited DeFi bug class (DeFiHackLabs) — "
            "check spot-price vs TWAP reliance, reserve/balanceOf-derived valuation, "
            "single-source feeds, and flashloan-amplified price moves"
        )

    # Freshness hint — measured against the scan date, not the wall clock,
    # so backdated/reproduced scans stay consistent with age_days.
    scan_age = (scan_date - candidate.first_seen).days
    if scan_age < 60:
        suggestions.append(
            f"Brand-new contract ({scan_age}d old) — check initialization racing, first-caller bootstrap invariants"
        )

    # Audit gap hint
    if candidate.audit_density_score == 0:
        suggestions.append(
            "No prior audits found in any source — start with standard sanity pass before specialized depth"
        )

    # TVL hint
    if candidate.tvl_usd > 1_000_000:
        suggestions.append(
            f"Real money at stake (${int(candidate.tvl_usd):,} TVL) — favor impact-driven finding scoping"
        )

    # Fallback if nothing else
    if not suggestions:
        suggestions.append(
            f"Standard breadth sweep on {candidate.languages[0].value} code; no edge-match tailwinds"
        )

    return suggestions[:5]


def rank_candidate(candidate: AuditedCandidate, *, scan_date: date) -> CandidateRecord:
    """Compute priority score and derived fields, returning a full CandidateRecord."""
    s = settings()
    age_days = max(0, (scan_date - candidate.first_seen).days)

    tvl_s = tvl_score(candidate.tvl_usd)
    fresh_s = freshness_score(age_days, s.MAX_AGE_DAYS)
    audit_gap_s = audit_gap_score(candidate.audit_density_score)
    activity_s = activity_score(candidate.unique_users_30d)
    edge_s, edge_keywords = edge_match_score(candidate)
    bounty_s = bounty_score(candidate)

    priority = (
        tvl_s * W_TVL
        + fresh_s * W_FRESH
        + audit_gap_s * W_AUDIT_GAP
        + activity_s * W_ACTIVITY
        + edge_s * W_EDGE_MATCH
        + bounty_s * W_BOUNTY
    )

    return CandidateRecord(
        **candidate.model_dump(),
        priority_score=round(priority, 2),
        tvl_score=round(tvl_s, 2),
        freshness_score=round(fresh_s, 2),
        audit_gap_score=round(audit_gap_s, 2),
        activity_score=round(activity_s, 2),
        edge_match_score=round(edge_s, 2),
        bounty_score=round(bounty_s, 2),
        edge_match_keywords=edge_keywords,
        focus_areas_suggested=_focus_areas(candidate, edge_keywords, scan_date=scan_date),
        inferred_platform=_infer_platform(candidate),  # type: ignore[arg-type]
        inferred_mode=_infer_mode(candidate),  # type: ignore[arg-type]
        why_interesting=_why_interesting(candidate, age_days, edge_keywords),
        scan_date=scan_date,
        age_days=age_days,
    )


def rank_all(
    candidates: list[AuditedCandidate],
    *,
    scan_date: date,
    cutoff: float = PRIORITY_CUTOFF,
    cap: int = 50,
    exclude_slugs: set[str] | None = None,
) -> list[CandidateRecord]:
    """Rank, filter by cutoff, sort descending, cap at `cap` candidates.

    `exclude_slugs` (case-insensitive) removes already-processed protocols so
    a follow-up scan can surface only fresh candidates.
    """
    ranked = [rank_candidate(c, scan_date=scan_date) for c in candidates]
    kept = [r for r in ranked if r.priority_score >= cutoff]
    if exclude_slugs:
        skip = {s.strip().lower() for s in exclude_slugs if s.strip()}
        kept = [r for r in kept if (r.target_name or "").lower() not in skip]
    kept.sort(key=lambda r: r.priority_score, reverse=True)
    return kept[:cap]
