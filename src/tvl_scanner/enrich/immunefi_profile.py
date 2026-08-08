"""Extract a `BountyProfile` from one raw Immunefi catalogue program.

`immunefi_catalog.py` answers "which protocol is this, and is its code audited?".
This module answers the other half of target selection: **is this program worth
a solo researcher's weeks?** Those are different questions — an unaudited $500M
protocol whose bounty pays a flat $5K, published a 37-item known-issues list and
has not been touched in two years is a worse target than a freshly-launched $2M
one paying 10% of funds at risk on scope that changed last month.

Everything here is derived from fields the public catalogue already carries, so
it costs no extra network call:

  2. max/min bounty        `maxBounty`, `rewards[].minReward/maxReward`
  3. bounty calculation    `rewards[].rewardModel/rewardCalculationPercentage`,
                           `tenPercentEconomicRule`
  4. last update           `updatedDate`
  5. program age           `launchDate`, `endDate`
  6. known issues          `knownIssues[]`
  8. architecture          `assets[].type`, `ecosystem`, `programType`, `impacts`
  9. recent upgrades       `assets[].addedAt/revision` — scope churn is the
                           bounty-side shadow of a code delta: an asset added
                           last month is code that entered scope after the last
                           audit priced it
 11. competition           `kyc`, `inviteOnly`, `features`, `boostedLeaderboard`
 12. resolution quality    `responsiblePublicationCategory`, `features`,
                           `boostedLeaderboard[].earnings`

Criterion 7's audit *recency* is taken from `audits[].date` here; its count stays
on `defillama_audit_count` where Stage 3 already reads it.

Pure and total: every extractor degrades to a neutral default on a missing or
malformed field, because one odd program must never abort a 247-program scan.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from tvl_scanner.models import BountyProfile, KnownIssue, RewardTier

log = logging.getLogger(__name__)

# Rewards are published per asset type; only the smart-contract table is
# relevant to this scanner (the web/app tiers pay a different skillset).
SMART_CONTRACT = "smart_contract"

# `features` entries that carry target-selection signal. Immunefi's vocabulary
# is prose, so match on substrings rather than exact labels — the list grows
# without notice ("Subscription Plan: Pro" appeared after "Subscription Plan").
_FEATURE_BOOSTED = ("boost", "attackathon")
_FEATURE_MANAGED_TRIAGE = "managed triage"
_FEATURE_SAFE_HARBOR = "safe harbor"
_FEATURE_ARBITRATION = "arbitration"
_FEATURE_VAULT = "vault"
_FEATURE_PAY_TO_MEDIATE = "pay to mediate"
_FEATURE_NO_FREE_MEDIATION = "no free mediation"

# An asset added within this window is treated as fresh scope for criterion 9.
RECENT_ASSET_WINDOW_DAYS = 90

# Longest known-issue text kept per entry. The full prose is on the program
# page; the record only needs enough to recognise the dead zone.
_KNOWN_ISSUE_CHARS = 400


def _parse_date(raw: Any) -> date | None:
    """Parse an Immunefi ISO-8601 timestamp to a date. None on anything else."""
    if not isinstance(raw, str) or len(raw) < 10:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC).date()
    except ValueError:
        # A few records carry a bare "YYYY-MM-DD"; fromisoformat handles those
        # above, so reaching here means the field is genuinely unusable.
        return None


def _days_since(when: date | None, ref: date) -> int | None:
    """Whole days from `when` to `ref`. None if unknown, 0 if in the future.

    A future-dated field (a program that has not launched yet, an audit dated
    ahead of the scan) is clamped rather than returned negative, so downstream
    decay curves never invert.
    """
    if when is None:
        return None
    return max(0, (ref - when).days)


def _as_int(raw: Any) -> int | None:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return int(raw)


_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _reward_tiers(program: dict[str, Any]) -> list[RewardTier]:
    """Parse the reward table, keeping every asset type but ordering SC first."""
    tiers: list[RewardTier] = []
    for raw in program.get("rewards") or []:
        if not isinstance(raw, dict):
            continue
        severity = raw.get("severity")
        asset_type = raw.get("assetType")
        if not isinstance(severity, str) or not isinstance(asset_type, str):
            # A row with neither is a payout-pool placeholder for a competition,
            # not a severity tier — `rewardsPool` covers those separately.
            continue
        pct = raw.get("rewardCalculationPercentage")
        # `fixedReward` supersedes the range when present: the program pays a
        # flat amount for that severity regardless of the min/max columns.
        fixed = _as_int(raw.get("fixedReward"))
        tiers.append(
            RewardTier(
                severity=severity.lower(),
                asset_type=asset_type,
                reward_model=str(raw["rewardModel"]) if raw.get("rewardModel") else None,
                min_usd=fixed if fixed is not None else _as_int(raw.get("minReward")),
                max_usd=_as_int(raw.get("maxReward")) or fixed,
                calculation_percentage=float(pct) if isinstance(pct, (int, float)) else None,
                poc_required=bool(raw["pocRequired"]) if raw.get("pocRequired") is not None else None,
            )
        )
    tiers.sort(key=lambda t: (t.asset_type != SMART_CONTRACT, _SEVERITY_RANK.get(t.severity, 9)))
    return tiers


def _known_issues(program: dict[str, Any]) -> tuple[list[KnownIssue], date | None]:
    """Parse the published known-issues list and the most recent update to it."""
    issues: list[KnownIssue] = []
    latest: date | None = None
    for raw in program.get("knownIssues") or []:
        if not isinstance(raw, dict):
            continue
        description = str(raw.get("description") or "").strip()
        if not description:
            continue
        updated = _parse_date(raw.get("lastUpdatedAt"))
        if updated is not None and (latest is None or updated > latest):
            latest = updated
        issues.append(
            KnownIssue(
                description=description[:_KNOWN_ISSUE_CHARS],
                link=str(raw["link"]) if isinstance(raw.get("link"), str) else None,
                last_updated=updated,
                related_impact=(
                    str(raw["relatedImpactInScope"])
                    if isinstance(raw.get("relatedImpactInScope"), str)
                    else None
                ),
            )
        )
    return issues, latest


def _audit_history(program: dict[str, Any], scan_date: date) -> tuple[int, date | None, list[str]]:
    """Count, most-recent date, and named firms from the program's audit list."""
    audits = [a for a in (program.get("audits") or []) if isinstance(a, dict)]
    latest: date | None = None
    auditors: list[str] = []
    for a in audits:
        when = _parse_date(a.get("date"))
        # A future-dated audit is a data error, not a real review — ignore it
        # for recency so it cannot make a stale record look fresh.
        if when is not None and when <= scan_date and (latest is None or when > latest):
            latest = when
        name = a.get("auditor")
        if isinstance(name, str) and name.strip() and name.strip() not in auditors:
            auditors.append(name.strip())
    return len(audits), latest, auditors


def _asset_stats(program: dict[str, Any], scan_date: date) -> dict[str, Any]:
    """Per-type asset counts plus the scope-churn signals behind criterion 9."""
    counts = {SMART_CONTRACT: 0, "websites_and_applications": 0, "blockchain_dlt": 0}
    primacy = False
    revised = 0
    added_recently = 0
    newest: date | None = None

    for asset in program.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        asset_type = str(asset.get("type") or "")
        if asset_type in counts:
            counts[asset_type] += 1
        if asset.get("isPrimacyOfImpact"):
            primacy = True
        if (_as_int(asset.get("revision")) or 0) > 0:
            revised += 1
        added = _parse_date(asset.get("addedAt"))
        if added is None:
            continue
        # Only smart-contract scope churn counts: a new marketing page entering
        # scope says nothing about fresh on-chain surface.
        if asset_type != SMART_CONTRACT:
            continue
        if newest is None or added > newest:
            newest = added
        age = _days_since(added, scan_date)
        if age is not None and age <= RECENT_ASSET_WINDOW_DAYS:
            added_recently += 1

    return {
        "smart_contract_assets": counts[SMART_CONTRACT],
        "web_app_assets": counts["websites_and_applications"],
        "blockchain_dlt_assets": counts["blockchain_dlt"],
        "primacy_of_impact": primacy,
        "assets_revised": revised,
        "assets_added_90d": added_recently,
        "newest_asset_added_at": newest,
        "days_since_newest_asset": _days_since(newest, scan_date),
    }


def _str_list(raw: Any) -> list[str]:
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def _critical_impacts(program: dict[str, Any]) -> list[str]:
    """Titles of the in-scope critical smart-contract impacts.

    This is the program's own statement of what it will pay top dollar for —
    the most direct answer to "what am I hunting here?" available anywhere in
    the catalogue.
    """
    out: list[str] = []
    for raw in program.get("impacts") or []:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("severity") or "").lower() != "critical":
            continue
        if str(raw.get("type") or "") != SMART_CONTRACT:
            continue
        title = str(raw.get("title") or "").strip()
        if title and title not in out:
            out.append(title)
    return out


def _leaderboard_stats(program: dict[str, Any]) -> tuple[int, int]:
    """(paid researcher count, total USD paid) from a boosted program's leaderboard.

    Only competitions publish this, but where it exists it is the single piece
    of *hard evidence* in the whole catalogue that a program actually pays —
    every other resolution-quality signal is a policy statement.
    """
    board = program.get("boostedLeaderboard")
    if not isinstance(board, list):
        return 0, 0
    researchers = 0
    total = 0
    for row in board:
        if not isinstance(row, dict):
            continue
        earned = _as_int(row.get("totalEarnings")) or _as_int(row.get("earnings")) or 0
        if earned > 0:
            researchers += 1
            total += earned
    return researchers, total


def _payout_basis(
    critical: RewardTier | None, ten_percent_rule: bool, max_bounty: int | None
) -> str:
    """One-line plain-English summary of how a critical payout is computed."""
    if critical is None:
        return "no critical smart-contract tier published"

    cap = f"${critical.max_usd:,}" if critical.max_usd else (
        f"${max_bounty:,}" if max_bounty else "an unpublished cap"
    )
    pct = critical.calculation_percentage

    if pct:
        base = f"{pct:g}% of funds at risk, capped at {cap}"
    elif critical.reward_model == "fixed":
        return f"flat {cap} — does NOT scale with funds at risk"
    elif critical.reward_model == "up_to":
        base = f"up to {cap}, fully at the program's discretion"
    elif critical.min_usd and critical.max_usd and critical.min_usd != critical.max_usd:
        base = f"triager-set within ${critical.min_usd:,}–{cap}"
    else:
        base = f"up to {cap}"

    if ten_percent_rule:
        # Immunefi's standard rule: the payout floor is 10% of funds at risk,
        # which is what makes a percentage-based tier trustworthy rather than
        # discretionary.
        base += "; Immunefi 10% economic rule applies"
    return base


def build_profile(program: dict[str, Any], *, scan_date: date) -> BountyProfile:
    """Build the target-selection profile for one raw Immunefi program dict.

    Never raises on malformed input: each section degrades to its neutral
    default independently, so a program with (say) a broken rewards table still
    contributes its known-issues and scope-churn signal.
    """
    tiers = _reward_tiers(program)
    sc_tiers = [t for t in tiers if t.asset_type == SMART_CONTRACT]
    critical = next((t for t in sc_tiers if t.severity == "critical"), None)

    floors = [t.min_usd for t in sc_tiers if t.min_usd]
    max_bounty = _as_int(program.get("maxBounty"))
    ten_percent = bool(program.get("tenPercentEconomicRule"))

    launched = _parse_date(program.get("launchDate"))
    updated = _parse_date(program.get("updatedDate"))
    ends = _parse_date(program.get("endDate"))

    issues, issues_updated = _known_issues(program)
    audit_count, latest_audit, auditors = _audit_history(program, scan_date)
    assets = _asset_stats(program, scan_date)

    features = _str_list(program.get("features"))
    features_lower = [f.lower() for f in features]

    def _has(marker: str) -> bool:
        return any(marker in f for f in features_lower)

    researchers, total_paid = _leaderboard_stats(program)

    return BountyProfile(
        # 2. Maximum + minimum bounty
        max_bounty_usd=max_bounty,
        min_bounty_usd=min(floors) if floors else None,
        critical_min_usd=critical.min_usd if critical else None,
        critical_max_usd=critical.max_usd if critical else None,
        reward_tiers=tiers,
        # 3. Bounty calculation
        reward_model=critical.reward_model if critical else None,
        reward_calculation_percentage=critical.calculation_percentage if critical else None,
        ten_percent_economic_rule=ten_percent,
        poc_required_for_critical=critical.poc_required if critical else None,
        payout_basis=_payout_basis(critical, ten_percent, max_bounty),
        # max_payout_vs_tvl_pct is filled by the caller once TVL resolves.
        # 4. Last update
        program_updated_at=updated,
        days_since_program_update=_days_since(updated, scan_date),
        # 5. Program age
        program_launched_at=launched,
        program_age_days=_days_since(launched, scan_date),
        program_ends_at=ends,
        is_time_boxed=ends is not None,
        # 6. Known issues
        known_issue_count=len(issues),
        known_issues=issues,
        known_issues_last_updated=issues_updated,
        # 7. Audit history (recency)
        audit_count=audit_count,
        latest_audit_at=latest_audit,
        days_since_latest_audit=_days_since(latest_audit, scan_date),
        auditors=auditors,
        # 8. Protocol architecture
        smart_contract_assets=assets["smart_contract_assets"],
        web_app_assets=assets["web_app_assets"],
        blockchain_dlt_assets=assets["blockchain_dlt_assets"],
        primacy_of_impact=assets["primacy_of_impact"],
        ecosystems=_str_list(program.get("ecosystem")),
        program_types=_str_list(program.get("programType")),
        project_types=_str_list(program.get("projectType")) or _str_list(program.get("productType")),
        critical_impacts=_critical_impacts(program),
        # 9. Recent upgrades / features
        newest_asset_added_at=assets["newest_asset_added_at"],
        days_since_newest_asset=assets["days_since_newest_asset"],
        assets_added_90d=assets["assets_added_90d"],
        assets_revised=assets["assets_revised"],
        # 11. Likely researcher competition
        kyc_required=bool(program.get("kyc")),
        invite_only=bool(program.get("inviteOnly")) or _has("invite only"),
        immunefi_standard=bool(program.get("immunefiStandard")),
        is_boosted=any(_has(m) for m in _FEATURE_BOOSTED) or bool(program.get("rewardsPool")),
        boosted_researcher_count=researchers,
        boosted_total_paid_usd=total_paid,
        program_features=features,
        # 12. Historical payout / resolution quality
        responsible_publication_category=(
            str(program["responsiblePublicationCategory"])
            if isinstance(program.get("responsiblePublicationCategory"), str)
            else None
        ),
        safe_harbor=_has(_FEATURE_SAFE_HARBOR),
        arbitration_available=_has(_FEATURE_ARBITRATION),
        pay_to_mediate=_has(_FEATURE_PAY_TO_MEDIATE),
        no_free_mediation=_has(_FEATURE_NO_FREE_MEDIATION),
        vault_escrow=_has(_FEATURE_VAULT),
        managed_triage=_has(_FEATURE_MANAGED_TRIAGE),
    )


def attach_payout_ratio(profile: BountyProfile, tvl_usd: float, tvl_resolved: bool) -> None:
    """Fill `max_payout_vs_tvl_pct` once the candidate's TVL is known.

    Split out from `build_profile` because TVL resolution happens later in the
    discovery flow (DefiLlama match, then an on-chain fallback), and this ratio
    is the single most decision-relevant number in criterion 3: it converts the
    advertised cap into the fraction of at-risk funds a critical actually pays.
    """
    if not tvl_resolved or tvl_usd <= 0 or not profile.max_bounty_usd:
        profile.max_payout_vs_tvl_pct = None
        return
    profile.max_payout_vs_tvl_pct = round(profile.max_bounty_usd / tvl_usd * 100.0, 4)
