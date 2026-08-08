"""12-criteria bounty target-selection formula (immunefi-scan ranking).

`rank/priority.py` ranks *discovery*: of all the protocols on chain, which are
big, fresh and under-audited enough to be worth a look. That is the right
question for `run`, whose input is the TVL universe.

`immunefi-scan`'s input is different — every candidate already has a live bounty,
so "has a bounty" (the 0.10 `bounty_score` term) is a constant and carries no
information, and `activity_score` is always the neutral 5.0 because Immunefi
publishes no user counts. Two of six terms are noise. This module replaces the
formula with the twelve criteria that actually separate one bounty target from
another:

     1. Current TVL / funds at risk        0.12   tvl_score
     2. Maximum + minimum bounty           0.12   bounty_size_score
     3. Bounty calculation                 0.08   bounty_calc_score
     4. Last update                        0.05   program_update_score
     5. Program age                        0.06   program_age_score
     6. Known issues                       0.07   known_issues_score
     7. Audit history                      0.15   audit_gap_score
     8. Protocol architecture              0.07   architecture_score
     9. Recent upgrades / features         0.10   upgrade_activity_score
    10. Technical edge                     0.08   edge_match_score
    11. Likely researcher competition      0.06   competition_score
    12. Historical payout / resolution     0.04   resolution_quality_score
                                           ----
                                           1.00

Audit history keeps the largest single weight, as in the discovery formula:
unreviewed code is still where the bugs are. It is followed by funds at risk and
bounty size (together 0.24) — the two terms that set what a finding is worth —
and then by scope churn (0.10), which is the delta-watch thesis applied to the
bounty: an asset that entered scope after the last audit priced it is the
highest-yield surface a program exposes.

Every sub-score is [0, 10] and every one degrades to a neutral 5.0 when its
input is unknown, so a program with a thin catalogue record is neither rewarded
nor punished for the gaps — the same convention `rank/priority.py` uses for an
unresolved TVL or audit record.
"""

from __future__ import annotations

import math
from datetime import date

from tvl_scanner.config import settings
from tvl_scanner.models import AuditedCandidate, BountyProfile, CandidateRecord
from tvl_scanner.rank.priority import (
    PRIORITY_CUTOFF,
    _focus_areas,
    _infer_mode,
    _infer_platform,
    activity_score,
    audit_gap_score,
    edge_match_score,
    freshness_score,
    tvl_score,
)

# Weight distribution — sums to 1.0. Keyed by the rubric criterion number so a
# reweighting can be checked against the docstring above at a glance.
W_TVL = 0.12  # 1
W_BOUNTY_SIZE = 0.12  # 2
W_BOUNTY_CALC = 0.08  # 3
W_PROGRAM_UPDATE = 0.05  # 4
W_PROGRAM_AGE = 0.06  # 5
W_KNOWN_ISSUES = 0.07  # 6
W_AUDIT_GAP = 0.15  # 7
W_ARCHITECTURE = 0.07  # 8
W_UPGRADE_ACTIVITY = 0.10  # 9
W_EDGE_MATCH = 0.08  # 10
W_COMPETITION = 0.06  # 11
W_RESOLUTION = 0.04  # 12

_WEIGHTS = (
    W_TVL,
    W_BOUNTY_SIZE,
    W_BOUNTY_CALC,
    W_PROGRAM_UPDATE,
    W_PROGRAM_AGE,
    W_KNOWN_ISSUES,
    W_AUDIT_GAP,
    W_ARCHITECTURE,
    W_UPGRADE_ACTIVITY,
    W_EDGE_MATCH,
    W_COMPETITION,
    W_RESOLUTION,
)
assert abs(sum(_WEIGHTS) - 1.0) < 1e-9, "bounty priority weights must sum to 1.0"

NEUTRAL = 5.0

# An audit older than this is treated as no longer covering the deployed code:
# 18 months of active development on a DeFi protocol rewrites enough of the
# fund-exit paths that the report describes a different system.
AUDIT_STALE_DAYS = 540
# Full staleness credit once the newest audit is this old (~3 years).
AUDIT_FULLY_STALE_DAYS = 1095
# Most a stale audit record can add back to the audit-gap score. Capped below
# the full 10 because a stale audit still removed the shallow bugs.
MAX_STALENESS_BONUS = 3.0

# Criterion 5 calibration, from the live catalogue (247 programs, 2026-08):
# 15 programs are under 90d old, 34 under a year, 98 over three years. A program
# in its first quarter has had the fewest eyes on it; past three years the
# accessible surface has been swept many times over.
PROGRAM_AGE_FRESH_DAYS = 90
PROGRAM_AGE_EXHAUSTED_DAYS = 1095

# Criterion 4 calibration: every live program had been touched within 730 days,
# so that is the full-decay point rather than an arbitrary cutoff.
PROGRAM_UPDATE_STALE_DAYS = 730

# Criterion 9 calibration: 19 programs added smart-contract scope in the last
# 30d and 48 within 90d, so a 30d window is genuinely selective. Beyond a year,
# scope is settled and any fresh code in it is invisible from the catalogue.
SCOPE_FRESH_DAYS = 30
SCOPE_SETTLED_DAYS = 365

# Criterion 8 calibration: median program lists 8 in-scope contracts, p75 is 25,
# p90 is 54, max 355. Three to twenty-five is the band a solo researcher can
# actually read end-to-end inside a bounty's economics.
SCOPE_SWEET_MIN = 3
SCOPE_SWEET_MAX = 25
SCOPE_WIDE_MAX = 100


def _clamp(value: float) -> float:
    return max(0.0, min(10.0, value))


def _decay(days: int | None, full_days: int, *, flat_days: int = 0) -> float:
    """10 for the first `flat_days`, then linear decay to 0 at `full_days`.

    Returns the neutral 5.0 when `days` is unknown, so a program that omits the
    underlying timestamp is not scored as though it were maximally stale.
    """
    if days is None:
        return NEUTRAL
    if days <= flat_days:
        return 10.0
    if days >= full_days:
        return 0.0
    span = full_days - flat_days
    return 10.0 * (1.0 - (days - flat_days) / span)


# ---------------------------------------------------------------------------
# 2. Maximum + minimum bounty
# ---------------------------------------------------------------------------


def bounty_size_score(profile: BountyProfile | None) -> float:
    """Payout ceiling blended with the realistic floor.

    The headline max is what programs advertise, but a solo researcher's
    expected value is dominated by what a *typical* accepted critical pays, and
    the floor of the critical band is the only published proxy for that. A
    program advertising $1M with a $1K critical floor is a far weaker target
    than one advertising $250K with a $50K floor, and ranking on `maxBounty`
    alone cannot tell them apart.

    Ceiling: $10K → 0, $100K → 5, $1M → 10 (log-scaled, matching how payouts
    are actually distributed). Floor: $1K → 0, $10K → 5, $100K → 10. Weighted
    60/40 toward the ceiling; ceiling-only when no floor is published (126 of
    247 live programs publish no smart-contract minimum).
    """
    if profile is None:
        return NEUTRAL
    ceiling = profile.max_bounty_usd
    if not ceiling or ceiling <= 0:
        return 0.0 if ceiling == 0 else NEUTRAL

    ceiling_score = _clamp((math.log10(ceiling) - 4.0) * 5.0)

    floor = profile.critical_min_usd or profile.min_bounty_usd
    if not floor or floor <= 0:
        return ceiling_score
    floor_score = _clamp((math.log10(floor) - 3.0) * 5.0)
    return 0.6 * ceiling_score + 0.4 * floor_score


# ---------------------------------------------------------------------------
# 3. Bounty calculation
# ---------------------------------------------------------------------------


def _reward_model_score(profile: BountyProfile) -> float:
    """How trustworthy and how scaling the published payout formula is."""
    pct = profile.reward_calculation_percentage
    model = (profile.reward_model or "").lower()

    if pct is not None and pct >= 10:
        # Pays a real fraction of what an attacker would take — the payout
        # scales with the damage prevented instead of a fixed marketing number.
        base = 10.0
    elif pct is not None and pct >= 5:
        base = 8.0
    elif pct is not None and pct > 0:
        base = 6.5
    elif pct == 0:
        # Explicitly zero: the program publishes the field and sets no
        # funds-at-risk component, so the cap binds no matter the impact.
        base = 3.0
    elif model == "range":
        base = 5.5  # a published band, triager picks within it
    elif model == "fixed":
        base = 4.0  # predictable, but a critical on $500M pays the same as on $5M
    elif model == "up_to":
        base = 3.0  # ceiling only, entirely discretionary
    else:
        return NEUTRAL

    if profile.ten_percent_economic_rule:
        # Immunefi's standard rule puts a floor under the discretion — the
        # single strongest payout-integrity signal in the catalogue.
        base = min(10.0, base + 1.5)
    return base


def bounty_calc_score(profile: BountyProfile | None) -> float:
    """Criterion 3: what a critical is actually worth, not what is advertised.

    Two halves. The reward *model* says whether the payout scales with impact
    or is a flat number. The payout *ratio* (`max_payout_vs_tvl_pct`) says what
    the cap is worth against the funds actually at risk — a $50K ceiling over
    $2B is 0.0025%, and no reward model can rescue that. Scored on a log scale
    where 10% of TVL → 10, 1% → 5, 0.1% → 0.

    The ratio half is only available when TVL resolved; otherwise the model
    score stands alone.
    """
    if profile is None:
        return NEUTRAL
    model_score = _reward_model_score(profile)

    pct = profile.max_payout_vs_tvl_pct
    if pct is None or pct <= 0:
        return model_score
    ratio_score = _clamp((math.log10(pct) + 1.0) * 5.0)
    return 0.5 * model_score + 0.5 * ratio_score


# ---------------------------------------------------------------------------
# 4. Last update  /  5. Program age
# ---------------------------------------------------------------------------


def program_update_score(profile: BountyProfile | None) -> float:
    """Criterion 4: how recently the program itself was touched.

    A program updated last month has a team that maintains its scope, responds
    to submissions and keeps the reward table current. One untouched for two
    years frequently means a dormant bounty whose triage queue nobody reads —
    the failure mode that costs a researcher a month with no reply.
    """
    if profile is None:
        return NEUTRAL
    return _decay(
        profile.days_since_program_update, PROGRAM_UPDATE_STALE_DAYS, flat_days=30
    )


def program_age_score(profile: BountyProfile | None) -> float:
    """Criterion 5: younger programs are less picked-over.

    Every month a bounty is live is another month of researchers sweeping the
    same accessible surface. A program in its first quarter is scored full;
    past three years the shallow findings are gone and what remains needs depth
    the other criteria (scope churn, audit staleness) are better at locating.
    """
    if profile is None:
        return NEUTRAL
    return _decay(
        profile.program_age_days,
        PROGRAM_AGE_EXHAUSTED_DAYS,
        flat_days=PROGRAM_AGE_FRESH_DAYS,
    )


# ---------------------------------------------------------------------------
# 6. Known issues
# ---------------------------------------------------------------------------


def known_issues_score(profile: BountyProfile | None) -> float:
    """Criterion 6: published known issues are pre-closed submissions.

    Each entry is an area where a finding returns "known issue / duplicate" no
    matter how good the write-up, and a long list is also evidence the program
    has already been mined hard. 196 of 247 live programs publish none, so any
    list at all is a real differentiator.

    A single acknowledged issue is barely a penalty (10 → 8.5); the 37-entry
    program in the live catalogue floors out. Absence is scored 10 rather than
    neutral: it genuinely is the better case, and it is also the norm.
    """
    if profile is None:
        return NEUTRAL
    return _clamp(10.0 - 1.5 * profile.known_issue_count)


# ---------------------------------------------------------------------------
# 7. Audit history
# ---------------------------------------------------------------------------


def audit_history_score(candidate: AuditedCandidate) -> float:
    """Criterion 7: the audit gap, adjusted for how stale the coverage is.

    Starts from `rank/priority.audit_gap_score` (density inverted, unresolved
    records neutral), then adds back up to 3 points when the newest known audit
    predates the deployed code by enough to no longer describe it. An 18-month-
    old report on an actively developed protocol has been overtaken by the
    commits since; at three years it is a historical document.

    The bonus never applies to an unresolved record — "we could not find an
    audit" plus "the audit we could not find is old" is one unknown, not two.
    """
    base = audit_gap_score(
        candidate.audit_density_score, resolved=candidate.audit_record_resolved
    )
    if not candidate.audit_record_resolved:
        return base

    profile = candidate.bounty_profile
    days = profile.days_since_latest_audit if profile else None
    if days is None or days <= AUDIT_STALE_DAYS:
        return base

    span = AUDIT_FULLY_STALE_DAYS - AUDIT_STALE_DAYS
    staleness = min(1.0, (days - AUDIT_STALE_DAYS) / span)
    return _clamp(base + MAX_STALENESS_BONUS * staleness)


# ---------------------------------------------------------------------------
# 8. Protocol architecture
# ---------------------------------------------------------------------------


def architecture_score(profile: BountyProfile | None) -> float:
    """Criterion 8: is this scope one researcher can actually cover?

    Two halves. Scope *size*: 3-25 in-scope contracts is the band where a solo
    researcher can read the whole system and still reason about cross-contract
    invariants. Below that there is little surface; a 355-contract scope cannot
    be covered at all, so any single finding competes against everyone who
    picked the same corner. Scope *composition*: a program whose assets are
    mostly websites and apps pays for a different skillset, and its
    smart-contract share is the fraction of the program this scanner's user can
    actually compete for.
    """
    if profile is None:
        return NEUTRAL

    sc = profile.smart_contract_assets
    total = sc + profile.web_app_assets + profile.blockchain_dlt_assets
    if total == 0:
        return NEUTRAL

    if sc == 0:
        # Primacy-of-impact only: any contract of the protocol is fair game,
        # which is broad scope with no map. Workable, not ideal.
        size = 5.0 if profile.primacy_of_impact else 2.0
    elif sc < SCOPE_SWEET_MIN:
        size = 7.0
    elif sc <= SCOPE_SWEET_MAX:
        size = 10.0
    elif sc <= SCOPE_WIDE_MAX:
        size = 6.0
    else:
        size = 3.0

    composition = 10.0 * (sc / total)
    return _clamp(0.6 * size + 0.4 * composition)


# ---------------------------------------------------------------------------
# 9. Recent upgrades / features
# ---------------------------------------------------------------------------


def upgrade_activity_score(profile: BountyProfile | None) -> float:
    """Criterion 9: fresh code entering scope, seen from the bounty side.

    Delta-watch's thesis is that the highest-yield surface is the delta of an
    actively developed protocol rather than a protocol audited cold. The
    catalogue exposes that delta directly: `addedAt` on each in-scope contract
    dates when it entered the bounty, and a contract added after the last audit
    was priced is unreviewed code on a permissionless path.

    Recency of the newest addition carries 70% (30d → 10, a year → 0), volume of
    additions in the last 90 days the remaining 30%, with in-place revisions
    counted at half weight since a revision may be a description edit rather
    than a redeploy.
    """
    if profile is None:
        return NEUTRAL
    if profile.days_since_newest_asset is None:
        return NEUTRAL

    recency = _decay(
        profile.days_since_newest_asset, SCOPE_SETTLED_DAYS, flat_days=SCOPE_FRESH_DAYS
    )
    churn = profile.assets_added_90d + 0.5 * min(profile.assets_revised, 10)
    volume = _clamp(churn * 2.0)
    return _clamp(0.7 * recency + 0.3 * volume)


# ---------------------------------------------------------------------------
# 11. Likely researcher competition
# ---------------------------------------------------------------------------


def competition_score(profile: BountyProfile | None) -> float:
    """Criterion 11: inverse crowding — higher means fewer researchers to race.

    No source publishes submission counts, so this composes the structural
    proxies the catalogue does carry, starting from neutral:

      - invite-only            floors the score; without an invite you cannot
                               submit at all, so crowding is moot
      - live Boost/competition -3, and -1 per 10 leaderboard researchers: a
                               competition is the definition of many eyes at once
      - headline max > $1M     -2, every hunter's shortlist starts there
      - headline max < $50K    +1, too small to attract a crowd
      - KYC required           +1.5, a real deterrent for a slice of the field
      - Pay to Submit          +1.0, a per-report fee prices out speculative
                               submissions and thins the field (the same feature
                               costs the program points on criterion 12, where it
                               is a cost shifted onto the researcher — it really
                               does cut both ways)
      - Immunefi Standard      -0.5, standardised scope is easier to pick up cold

    Program age is deliberately NOT folded in here — criterion 5 already scores
    it, and double-counting would let one signal drive two weights. The project's
    subscription tier is likewise left out: it describes what the project buys
    from Immunefi, not how many researchers are competing.
    """
    if profile is None:
        return NEUTRAL
    if profile.invite_only:
        return 0.0

    score = NEUTRAL
    if profile.is_boosted:
        score -= 3.0
    if profile.boosted_researcher_count:
        score -= min(3.0, profile.boosted_researcher_count / 10.0)

    max_bounty = profile.max_bounty_usd or 0
    if max_bounty >= 1_000_000:
        score -= 2.0
    elif 0 < max_bounty < 50_000:
        score += 1.0

    if profile.kyc_required:
        score += 1.5
    if profile.pay_to_submit:
        score += 1.0
    if profile.immunefi_standard:
        score -= 0.5
    return _clamp(score)


# ---------------------------------------------------------------------------
# 12. Historical payout / resolution quality
# ---------------------------------------------------------------------------


def resolution_quality_score(profile: BountyProfile | None) -> float:
    """Criterion 12: will they pay, and can a dispute be resolved?

    The one piece of hard evidence in the catalogue is a boosted program's
    leaderboard: money already paid to named researchers. Everything else is
    policy — escrowed Vault funds, a signed Safe Harbor, available arbitration,
    a responsible-publication commitment — so those move the score in smaller
    steps from neutral.

    Two entries subtract, both for the same reason: they move a cost off the
    program and onto the researcher. "Pay to Mediate - No Free Mediations" makes
    you pay to contest a triage decision; "Pay to Submit" charges you per report,
    win or lose, which is the harsher of the two because it lands on every
    submission rather than only on disputes. (The same fee *helps* on criterion
    11, where it thins the field — the two effects are real and opposite, so
    each is scored where it belongs rather than netted into one number.)
    """
    if profile is None:
        return NEUTRAL

    score = NEUTRAL
    if profile.boosted_total_paid_usd > 0:
        # Documented payouts to named researchers.
        score += 2.0
    if profile.vault_escrow:
        # Funds sit in an on-chain vault; ability to pay is verifiable rather
        # than promised.
        score += 2.0
    if profile.safe_harbor:
        score += 1.5
    if profile.arbitration_available:
        score += 1.5

    category = profile.responsible_publication_category
    if category == "category_1":
        score += 1.5
    elif category == "category_2":
        score += 1.0
    elif category == "category_3":
        score += 0.5

    if profile.pay_to_mediate:
        score += 0.5
    if profile.no_free_mediation:
        score -= 1.5
    if profile.pay_to_submit:
        score -= 2.0
    if profile.managed_triage:
        score += 0.5
    if profile.immunefi_standard:
        score += 0.5
    return _clamp(score)


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


def _bounty_why_interesting(
    candidate: AuditedCandidate, profile: BountyProfile | None, edge_keywords: list[str]
) -> str:
    """One-line summary tuned for a bounty report rather than a TVL scan.

    Leads with the payout and the funds behind it, because that is what a
    target-selection pass is deciding on.
    """
    parts: list[str] = []
    if profile and profile.max_bounty_usd:
        floor = profile.critical_min_usd
        parts.append(
            f"${profile.max_bounty_usd:,} max"
            + (f" / ${floor:,} critical floor" if floor else "")
        )
    parts.append(
        f"${int(candidate.tvl_usd):,} TVL"
        if candidate.tvl_resolved
        else "TVL unresolved (not a measured $0 — verify on-chain)"
    )
    if profile and profile.max_payout_vs_tvl_pct is not None:
        parts.append(f"pays {profile.max_payout_vs_tvl_pct:.3g}% of funds at risk")
    if profile and profile.program_age_days is not None:
        parts.append(f"program {profile.program_age_days}d old")
    if candidate.audit_density_score == 0 and candidate.audit_record_resolved:
        parts.append("no prior audits found")
    elif profile and profile.days_since_latest_audit is not None:
        parts.append(f"last audit {profile.days_since_latest_audit}d ago")
    if profile and profile.assets_added_90d:
        parts.append(f"{profile.assets_added_90d} contract(s) added to scope in 90d")
    if profile and profile.known_issue_count:
        parts.append(f"{profile.known_issue_count} known issue(s)")
    if profile and profile.invite_only:
        parts.append("⚠ INVITE-ONLY — you cannot submit without an invitation")
    if edge_keywords:
        parts.append(f"edge-match: {', '.join(edge_keywords)}")
    return " • ".join(parts)


def _bounty_focus_areas(
    candidate: AuditedCandidate, profile: BountyProfile | None, edge_keywords: list[str], *, scan_date: date
) -> list[str]:
    """Focus areas with the bounty-specific hints in front of the generic ones.

    The base list (`rank/priority._focus_areas`) covers the code: proxies,
    oracle exposure, verification red flags. These prepend what the *program*
    tells the researcher — where fresh scope landed, which dead zones to avoid,
    and what the program says it will pay top dollar for.
    """
    hints: list[str] = []
    if profile is not None:
        if profile.invite_only:
            hints.append(
                "⚠ **Invite-only program** — submissions are not open. Do not spend research "
                "time here unless you already hold an invitation."
            )
        if profile.assets_added_90d:
            when = (
                f" (newest {profile.days_since_newest_asset}d ago)"
                if profile.days_since_newest_asset is not None
                else ""
            )
            hints.append(
                f"{profile.assets_added_90d} contract(s) entered bounty scope in the last 90 days{when} "
                "— start there. Scope added after the last audit is unreviewed code on a live "
                "fund path, which is the highest-yield surface a program exposes."
            )
        if (
            profile.days_since_latest_audit is not None
            and profile.days_since_latest_audit > AUDIT_STALE_DAYS
        ):
            firms = ", ".join(profile.auditors[:3]) or "the prior auditor"
            hints.append(
                f"Newest audit is {profile.days_since_latest_audit}d old ({firms}) — diff the "
                "deployed code against the audited commit and concentrate on what changed since."
            )
        if profile.known_issue_count:
            hints.append(
                f"⚠ {profile.known_issue_count} published known issue(s) — read them BEFORE "
                "starting; findings in those areas are closed as duplicates regardless of quality."
            )
        if profile.critical_impacts:
            hints.append(
                "Program pays critical for: "
                + "; ".join(profile.critical_impacts[:2])
                + " — scope the hunt to reaching one of these, not to bug count."
            )
        if profile.poc_required_for_critical:
            hints.append(
                "PoC is REQUIRED for a critical payout — budget for a runnable exploit "
                "(fork test), not a written argument."
            )

    hints.extend(_focus_areas(candidate, edge_keywords, scan_date=scan_date))
    return hints[:8]


def rank_candidate_bounty(candidate: AuditedCandidate, *, scan_date: date) -> CandidateRecord:
    """Score one bounty candidate on the 12 target-selection criteria."""
    s = settings()
    profile = candidate.bounty_profile
    age_days = max(0, (scan_date - candidate.first_seen).days)

    tvl_s = tvl_score(candidate.tvl_usd, resolved=candidate.tvl_resolved)
    size_s = bounty_size_score(profile)
    calc_s = bounty_calc_score(profile)
    update_s = program_update_score(profile)
    prog_age_s = program_age_score(profile)
    known_s = known_issues_score(profile)
    audit_s = audit_history_score(candidate)
    arch_s = architecture_score(profile)
    upgrade_s = upgrade_activity_score(profile)
    edge_s, edge_keywords = edge_match_score(candidate)
    comp_s = competition_score(profile)
    resolution_s = resolution_quality_score(profile)

    priority = (
        tvl_s * W_TVL
        + size_s * W_BOUNTY_SIZE
        + calc_s * W_BOUNTY_CALC
        + update_s * W_PROGRAM_UPDATE
        + prog_age_s * W_PROGRAM_AGE
        + known_s * W_KNOWN_ISSUES
        + audit_s * W_AUDIT_GAP
        + arch_s * W_ARCHITECTURE
        + upgrade_s * W_UPGRADE_ACTIVITY
        + edge_s * W_EDGE_MATCH
        + comp_s * W_COMPETITION
        + resolution_s * W_RESOLUTION
    )

    return CandidateRecord(
        **candidate.model_dump(),
        priority_score=round(priority, 2),
        priority_formula="bounty",
        # Shared with the discovery formula.
        tvl_score=round(tvl_s, 2),
        audit_gap_score=round(audit_s, 2),
        edge_match_score=round(edge_s, 2),
        # Carried for schema compatibility with `run` reports. Neither is a term
        # of this formula: contract freshness is superseded by criteria 5 and 9,
        # and Immunefi publishes no user counts so activity is always neutral.
        freshness_score=round(freshness_score(age_days, s.MAX_AGE_DAYS), 2),
        activity_score=round(activity_score(candidate.unique_users_30d), 2),
        bounty_score=10.0,  # constant across this population — every candidate has a bounty
        # Bounty-only sub-scores.
        bounty_size_score=round(size_s, 2),
        bounty_calc_score=round(calc_s, 2),
        program_update_score=round(update_s, 2),
        program_age_score=round(prog_age_s, 2),
        known_issues_score=round(known_s, 2),
        architecture_score=round(arch_s, 2),
        upgrade_activity_score=round(upgrade_s, 2),
        competition_score=round(comp_s, 2),
        resolution_quality_score=round(resolution_s, 2),
        edge_match_keywords=edge_keywords,
        focus_areas_suggested=_bounty_focus_areas(
            candidate, profile, edge_keywords, scan_date=scan_date
        ),
        inferred_platform=_infer_platform(candidate),  # type: ignore[arg-type]
        inferred_mode=_infer_mode(candidate),  # type: ignore[arg-type]
        why_interesting=_bounty_why_interesting(candidate, profile, edge_keywords),
        scan_date=scan_date,
        age_days=age_days,
    )


def rank_all_bounty(
    candidates: list[AuditedCandidate],
    *,
    scan_date: date,
    cutoff: float = PRIORITY_CUTOFF,
    cap: int = 60,
    exclude_slugs: set[str] | None = None,
    exclude_invite_only: bool = False,
) -> list[CandidateRecord]:
    """Rank on the 12 criteria, filter by cutoff, sort descending, cap.

    `exclude_invite_only` drops programs you cannot submit to without an
    invitation. They are kept by default (and flagged loudly in the record)
    because an invitation may already be held; pass True to hide them.
    """
    ranked = [rank_candidate_bounty(c, scan_date=scan_date) for c in candidates]
    kept = [r for r in ranked if r.priority_score >= cutoff]
    if exclude_invite_only:
        kept = [
            r for r in kept if not (r.bounty_profile and r.bounty_profile.invite_only)
        ]
    if exclude_slugs:
        skip = {s.strip().lower() for s in exclude_slugs if s.strip()}
        kept = [r for r in kept if (r.target_name or "").lower() not in skip]
    kept.sort(key=lambda r: r.priority_score, reverse=True)
    return kept[:cap]
