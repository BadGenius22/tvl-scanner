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
  8. architecture          `assets[]`, `ecosystem`, `programType`, `impacts`
  9. recent upgrades       `assets[].addedAt/revision` — scope churn is the
                           bounty-side shadow of a code delta: an asset added
                           last month is code that entered scope after the last
                           audit priced it
 11. competition           `kyc`, `inviteOnly`, `features`, `boostedLeaderboard`
 12. resolution quality    `responsiblePublicationCategory`, `features`,
                           `boostedLeaderboard[].earnings`

Criterion 7's audit *recency* is taken from `audits[].date` here; its count stays
on `defillama_audit_count` where Stage 3 already reads it.

Alongside the rubric, the module reads the program as a *document*: the full
assets-in-scope table (`scope_assets`), the impact table at every severity
(`impacts`), the seven prose fields that define what will be rejected
(`exclusions`), the PoC requirement (`pocPerTypeAndSeverity`) and the links the
program publishes about itself (`resources`). Those decide whether a finding is
submittable at all, which is upstream of how well it scores.

Pure and total: every extractor degrades to a neutral default on a missing or
malformed field, because one odd program must never abort a 247-program scan.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse

from tvl_scanner.enrich import immunefi
from tvl_scanner.models import (
    AuditRecord,
    BountyProfile,
    KnownIssue,
    ProgramExclusions,
    ProgramImpact,
    ProgramResource,
    RewardTier,
    ScopeAsset,
)

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
_FEATURE_PAY_TO_SUBMIT = "pay to submit"
# "Subscription Plan: Elite" → the project's paid Immunefi tier. Note this is a
# PREFIX match with the tier taken from after the colon, because Immunefi adds
# tiers without notice (Pro appeared after Essential and Elite).
_FEATURE_SUBSCRIPTION = "subscription plan"

# An asset added within this window is treated as fresh scope for criterion 9.
RECENT_ASSET_WINDOW_DAYS = 90

# Longest known-issue text kept per entry. The full prose is on the program
# page; the record only needs enough to recognise the dead zone.
_KNOWN_ISSUE_CHARS = 400

# Longest exclusion-section text kept. Sized from the live catalogue, where the
# largest of the seven sections (defaultFeasibilityLimitations) runs to ~1.4K
# characters — the cap should not be biting on a typical program.
EXCLUSION_TEXT_CHARS = 2000

# Non-mainnet explorer subdomains — never treat these as a live target.
# `immunefi_catalog` imports this rather than keeping its own copy, so the two
# modules cannot drift on what counts as a testnet.
TESTNET_MARKERS: tuple[str, ...] = (
    "sepolia.",
    "goerli.",
    "hoodi.",
    "holesky.",
    "testnet.",
    "-testnet",
    "mumbai.",
)

# Immunefi's Primacy-of-Impact sentinel: an assets-in-scope row that is not an
# asset. It carries `isPrimacyOfImpact: true` and points at immunefi.com itself.
# 80 of these sit across 61 of the 247 programs in the 2026-08 catalogue, so
# counting them as contracts inflates scope for a quarter of the universe.
_PLACEHOLDER_ASSET_HOST = "immunefi.com"

# Audit-list entries whose "auditor" is a category label rather than a firm.
# These accompany a link to the project's own security page, so the row is a
# pointer to audits, not a record of one.
_PLACEHOLDER_AUDITOR_NAMES = frozenset(
    {"all audits", "audit", "audits", "audit report", "audit reports", "see website", "n/a", "-"}
)

# Longest per-asset description retained, so a program that writes an essay in
# one scope row cannot dominate the record.
_ASSET_DESCRIPTION_CHARS = 200

# What a program writes into a prose section it did not fill in. Compared
# lower-cased with trailing dots stripped, so "To be determined." matches too.
_EMPTY_TEXT_SENTINELS = frozenset({"_blank_", "", "tbd", "to be determined", "n/a", "na", "-"})


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


def _poc_tiers(program: dict[str, Any]) -> list[str]:
    """Rows of `pocPerTypeAndSeverity`, each '<assetType> - <severity>'.

    Every program in the catalogue publishes this list and the scanner used to
    read none of it, so `poc_required` came out null on every tier of every
    record. A mandatory PoC is a real cost to budget for before picking a
    target, and on a fork-only protocol it can be the deciding constraint.
    """
    out: list[str] = []
    for raw in program.get("pocPerTypeAndSeverity") or []:
        if isinstance(raw, str) and raw.strip() and raw.strip() not in out:
            out.append(raw.strip())
    return out


def _poc_required_keys(poc_tiers: list[str]) -> set[tuple[str, str]]:
    """Parse the PoC rows into (asset_type, severity) pairs for tier lookup."""
    keys: set[tuple[str, str]] = set()
    for row in poc_tiers:
        asset_type, sep, severity = row.partition(" - ")
        if sep and asset_type.strip() and severity.strip():
            keys.add((asset_type.strip().lower(), severity.strip().lower()))
    return keys


def _reward_tiers(program: dict[str, Any], poc_keys: set[tuple[str, str]]) -> list[RewardTier]:
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
        # A per-row `pocRequired` wins where it exists; the live catalogue never
        # sets it, and states the same fact program-wide in pocPerTypeAndSeverity.
        if raw.get("pocRequired") is not None:
            poc = bool(raw["pocRequired"])
        elif poc_keys:
            poc = (asset_type.lower(), severity.lower()) in poc_keys
        else:
            poc = None
        tiers.append(
            RewardTier(
                severity=severity.lower(),
                asset_type=asset_type,
                reward_model=str(raw["rewardModel"]) if raw.get("rewardModel") else None,
                min_usd=fixed if fixed is not None else _as_int(raw.get("minReward")),
                max_usd=_as_int(raw.get("maxReward")) or fixed,
                calculation_percentage=float(pct) if isinstance(pct, (int, float)) else None,
                poc_required=poc,
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


def _audit_placeholder_reason(
    auditor: str | None, performed_at: date | None, launched: date | None
) -> str | None:
    """Why this audit row is a pointer rather than a review, or None if it is real.

    Two independent tests, either sufficient:

    * the "auditor" is a category label ("All Audits", "Audit") rather than a
      firm, which is how a program links its own security page from the audit
      list;
    * the audit is dated to the day the bounty launched, which is when the link
      was added, not when a review happened.

    Twyne is the worked example: one row, auditor "All Audits", url
    `twyne.gitbook.io/twyne/resources/security`, dated 2026-01-16 — the program
    launch date. Scored as a real audit it made `days_since_latest_audit` equal
    `program_age_days` exactly, so criterion 7's staleness bonus was reading a
    number that measures nothing.
    """
    name = (auditor or "").strip().lower()
    if not name or name in _PLACEHOLDER_AUDITOR_NAMES:
        return f"auditor is {auditor!r}, a category label rather than a firm"
    if performed_at is not None and launched is not None and performed_at == launched:
        return "dated to the program launch date, so it records the listing, not a review"
    return None


def _audit_history(
    program: dict[str, Any], scan_date: date, launched: date | None
) -> tuple[list[AuditRecord], date | None, list[str]]:
    """Parse the audit list into records, and take recency from the real ones only."""
    records: list[AuditRecord] = []
    latest: date | None = None
    auditors: list[str] = []
    for raw in program.get("audits") or []:
        if not isinstance(raw, dict):
            continue
        name = raw.get("auditor")
        name = name.strip() if isinstance(name, str) and name.strip() else None
        when = _parse_date(raw.get("date"))
        reason = _audit_placeholder_reason(name, when, launched)
        records.append(
            AuditRecord(
                auditor=name,
                url=str(raw["url"]) if isinstance(raw.get("url"), str) else None,
                performed_at=when,
                is_placeholder=reason is not None,
                placeholder_reason=reason,
            )
        )
        if reason is not None:
            continue
        # A future-dated audit is a data error, not a real review — ignore it
        # for recency so it cannot make a stale record look fresh.
        if when is not None and when <= scan_date and (latest is None or when > latest):
            latest = when
        if name and name not in auditors:
            auditors.append(name)
    return records, latest, auditors


def _is_testnet(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in TESTNET_MARKERS)


def _repo_path(url: str) -> str | None:
    """'owner/repo/tree/main/src' for a GitHub asset, else None.

    Repo- and path-level scope is a materially different audit than an address:
    the target is source on a branch, and matching it to deployed bytecode is
    work the researcher has to do. Recording it as such beats recording it as a
    contract with no address.
    """
    parsed = urlparse(url)
    if not parsed.netloc.lower().endswith("github.com"):
        return None
    path = parsed.path.strip("/")
    return path or None


def _scope_assets(program: dict[str, Any]) -> list[ScopeAsset]:
    """The program's assets-in-scope table, one row per published asset.

    Placeholders are kept and flagged rather than dropped: the sentinel row is
    where `isPrimacyOfImpact` actually lives, so discarding it would lose the
    flag, and hiding it would make the record disagree with the program page.
    """
    assets: list[ScopeAsset] = []
    for raw in program.get("assets") or []:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "").strip()
        if not url:
            continue
        host = urlparse(url).netloc.lower()
        is_placeholder = _PLACEHOLDER_ASSET_HOST in host
        match = immunefi._ADDR_RE.search(url)
        description = str(raw.get("description") or "").strip() or None
        assets.append(
            ScopeAsset(
                asset_type=str(raw.get("type") or "unknown"),
                url=url,
                description=description[:_ASSET_DESCRIPTION_CHARS] if description else None,
                address=match.group(0) if match and not is_placeholder else None,
                repo=_repo_path(url),
                explorer=host or None if match else None,
                added_at=_parse_date(raw.get("addedAt")),
                revision=_as_int(raw.get("revision")) or 0,
                primacy_of_impact=bool(raw.get("isPrimacyOfImpact")),
                safe_harbor=bool(raw.get("isSafeHarbor")),
                is_placeholder=is_placeholder,
                is_testnet=_is_testnet(url),
            )
        )
    return assets


def _asset_stats(assets: list[ScopeAsset], scan_date: date) -> dict[str, Any]:
    """Per-type asset counts plus the scope-churn signals behind criterion 9.

    Every count here excludes Primacy-of-Impact placeholders. They are not
    contracts, and counting them shifted criterion 8's scope-size band for the
    61 programs that publish one — Twyne read as 16 in-scope contracts against
    15 real addresses, in the same record that printed 15 elsewhere.
    """
    counts = {SMART_CONTRACT: 0, "websites_and_applications": 0, "blockchain_dlt": 0}
    primacy = False
    repo_scoped = 0
    revised = 0
    added_recently = 0
    newest: date | None = None

    for asset in assets:
        if asset.primacy_of_impact:
            primacy = True
        if asset.is_placeholder:
            continue
        if asset.asset_type in counts:
            counts[asset.asset_type] += 1
        if asset.repo:
            repo_scoped += 1
        if asset.revision > 0:
            revised += 1
        # Only smart-contract scope churn counts: a new marketing page entering
        # scope says nothing about fresh on-chain surface.
        if asset.asset_type != SMART_CONTRACT or asset.added_at is None:
            continue
        if newest is None or asset.added_at > newest:
            newest = asset.added_at
        age = _days_since(asset.added_at, scan_date)
        if age is not None and age <= RECENT_ASSET_WINDOW_DAYS:
            added_recently += 1

    return {
        "smart_contract_assets": counts[SMART_CONTRACT],
        "web_app_assets": counts["websites_and_applications"],
        "blockchain_dlt_assets": counts["blockchain_dlt"],
        "repo_scoped_assets": repo_scoped,
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


def _impacts(program: dict[str, Any]) -> list[ProgramImpact]:
    """The program's own impact table, every severity and asset type.

    This is the program's statement of what it will pay for, and it is the only
    severity rubric that governs a submission there. A finding that maps to no
    row is unpayable however good it is, so the whole table has to travel with
    the record — carrying only the critical tier hides the floor a finding can
    realistically reach.
    """
    out: list[ProgramImpact] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in program.get("impacts") or []:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        severity = str(raw.get("severity") or "unknown").lower()
        asset_type = str(raw.get("type") or "unknown")
        key = (severity, asset_type, title)
        if key in seen:
            continue
        seen.add(key)
        out.append(ProgramImpact(severity=severity, asset_type=asset_type, title=title))
    out.sort(key=lambda i: (i.asset_type != SMART_CONTRACT, _SEVERITY_RANK.get(i.severity, 9)))
    return out


def _critical_impacts(impacts: list[ProgramImpact]) -> list[str]:
    """Titles of the in-scope critical smart-contract impacts.

    The most direct answer to "what am I hunting here?" available anywhere in
    the catalogue, kept as its own field because it is what the summary line and
    the focus-area hints are built from.
    """
    return [
        i.title
        for i in impacts
        if i.severity == "critical" and i.asset_type == SMART_CONTRACT
    ]


def _text(program: dict[str, Any], key: str) -> str | None:
    """A prose field, capped. None when absent, blank, or a not-filled-in sentinel.

    Immunefi's rich-text editor writes `_blank_` for an empty section rather
    than leaving the key null: 118 of these sit across the prose fields of the
    2026-08 catalogue, alongside 35 bare `.` and 34 variants of "To be
    determined". Passing them through would quote an empty section as if it were
    a published constraint, and would make `published_sections()` report scope
    limits a program never wrote.
    """
    raw = program.get(key)
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if not cleaned or cleaned.lower().rstrip(".") in _EMPTY_TEXT_SENTINELS:
        return None
    return cleaned[:EXCLUSION_TEXT_CHARS]


def _exclusions(program: dict[str, Any]) -> ProgramExclusions:
    """The seven prose fields that decide what a program will reject.

    Previously read by nothing in the scanner. They carry the auto-invalidators:
    which actors are assumed trusted, which preconditions are ruled infeasible,
    which activities are prohibited outright. On a typical program that is
    ~3.5K characters of constraints that change whether a finding is
    submittable, which is upstream of how highly it would score.
    """
    return ProgramExclusions(
        rules=_text(program, "outOfScopeAndRules"),
        out_of_scope_general=_text(program, "defaultOutOfScopeGeneral"),
        out_of_scope_smart_contract=_text(program, "defaultOutOfScopeSmartContract"),
        out_of_scope_blockchain=_text(program, "defaultOutOfScopeBlockchain"),
        out_of_scope_web=_text(program, "defaultOutOfScopeWebAndApplications"),
        custom_out_of_scope=_text(program, "customOutOfScopeInformation"),
        feasibility_limitations=_text(program, "defaultFeasibilityLimitations"),
        prohibited_activities=_text(program, "defaultProhibitedActivities"),
        custom_prohibited_activities=[
            s[:EXCLUSION_TEXT_CHARS] for s in _str_list(program.get("customProhibitedActivities"))
        ],
        prioritized_vulnerabilities=_text(program, "prioritizedVulnerabilities"),
    )


def _resources(program: dict[str, Any], audits: list[AuditRecord]) -> list[ProgramResource]:
    """Links the program publishes about itself: site, repo, audit reports.

    Only structured fields are used. The catalogue has no `programDocumentations`
    key (checked across all 247 programs in the 2026-08 feed), so a docs link
    only appears here when the program files it as its website or as an audit.
    """
    out: list[ProgramResource] = []
    seen: set[str] = set()

    def _add(kind: str, url: Any, label: str | None = None) -> None:
        if not isinstance(url, str) or not url.startswith("http") or url in seen:
            return
        seen.add(url)
        out.append(ProgramResource(kind=kind, url=url, label=label))  # type: ignore[arg-type]

    _add("website", program.get("websiteUrl"))
    _add("repo", program.get("githubUrl"))
    for record in audits:
        _add("audit", record.url, record.auditor)
    return out


# Immunefi researcher levels. Some programs will only review reports from
# researchers at or above a given level — everyone below either cannot submit
# or must pay the per-report fee. Immunefi exposes this NOWHERE in the public
# catalogue's structured fields, so it has to be read out of the program prose.
_LEVEL_NAMES = r"novice|junior|associate|intermediate|advanced|senior|expert|elite"

# All three conditions must hold in the SAME sentence:
#   1. an Immunefi level name
#   2. the literal word "level" / "levels" / "levelled up"
#   3. a researcher-facing word (report, submit, researcher, ...)
# Condition 2 is what makes this safe. "Junior" and "Senior" are also DeFi
# tranche names — Royco and Strata both describe junior/senior tranches at
# length — and those sentences never say "level", so they cannot match.
_LEVEL_TOKEN_RE = re.compile(r"\blevel(?:s|led|ed)?\b", re.I)
_LEVEL_NAME_RE = re.compile(rf"\b(?:{_LEVEL_NAMES})\b", re.I)
_RESEARCHER_RE = re.compile(
    r"\b(?:researcher|whitehat|white-hat|hunter|submit\w*|submission|report)\w*\b", re.I
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")

# Prose fields worth reading, in the order a gate is most likely to be stated.
_LEVEL_GATE_FIELDS = ("programOverview", "description", "rewardsBody", "outOfScopeAndRules")

# Longest gate excerpt retained — enough to judge the gate without the essay.
_LEVEL_GATE_CHARS = 300


def _detect_level_gate(program: dict[str, Any]) -> str | None:
    """Find a researcher-level submission gate stated in the program's prose.

    Returns the sentence as evidence rather than a bare bool: whether a gate
    blocks *you* depends on your own Immunefi level, which the scanner cannot
    know, so the record must show the claim and let the reader decide.
    """
    for field in _LEVEL_GATE_FIELDS:
        text = program.get(field)
        if not isinstance(text, str) or not text:
            continue
        for sentence in _SENTENCE_SPLIT_RE.split(text):
            if not _LEVEL_TOKEN_RE.search(sentence):
                continue
            if not _LEVEL_NAME_RE.search(sentence):
                continue
            if not _RESEARCHER_RE.search(sentence):
                continue
            # Strip markdown emphasis so the excerpt reads cleanly in a report.
            cleaned = re.sub(r"[*_`]+", "", sentence).strip()
            cleaned = re.sub(r"\s+", " ", cleaned)
            if cleaned:
                return cleaned[:_LEVEL_GATE_CHARS]
    return None


def _subscription_plan(features: list[str]) -> str | None:
    """The project's Immunefi tier from a 'Subscription Plan: X' feature label.

    Returns just the tier ("Elite"), or the whole label when it carries no colon
    so an unrecognised future shape is surfaced rather than silently dropped.
    """
    for feature in features:
        if _FEATURE_SUBSCRIPTION in feature.lower():
            _, sep, tier = feature.partition(":")
            return tier.strip() if sep and tier.strip() else feature.strip()
    return None


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
    poc_tiers = _poc_tiers(program)
    tiers = _reward_tiers(program, _poc_required_keys(poc_tiers))
    sc_tiers = [t for t in tiers if t.asset_type == SMART_CONTRACT]
    critical = next((t for t in sc_tiers if t.severity == "critical"), None)

    floors = [t.min_usd for t in sc_tiers if t.min_usd]
    max_bounty = _as_int(program.get("maxBounty"))
    ten_percent = bool(program.get("tenPercentEconomicRule"))

    launched = _parse_date(program.get("launchDate"))
    updated = _parse_date(program.get("updatedDate"))
    ends = _parse_date(program.get("endDate"))

    issues, issues_updated = _known_issues(program)
    audit_records, latest_audit, auditors = _audit_history(program, scan_date, launched)
    scope_assets = _scope_assets(program)
    assets = _asset_stats(scope_assets, scan_date)
    impacts = _impacts(program)

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
        poc_required_tiers=poc_tiers,
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
        audit_count=len(audit_records),
        verified_audit_count=sum(1 for r in audit_records if not r.is_placeholder),
        audit_records=audit_records,
        latest_audit_at=latest_audit,
        days_since_latest_audit=_days_since(latest_audit, scan_date),
        auditors=auditors,
        # 8. Protocol architecture
        scope_assets=scope_assets,
        smart_contract_assets=assets["smart_contract_assets"],
        web_app_assets=assets["web_app_assets"],
        blockchain_dlt_assets=assets["blockchain_dlt_assets"],
        repo_scoped_assets=assets["repo_scoped_assets"],
        primacy_of_impact=assets["primacy_of_impact"],
        ecosystems=_str_list(program.get("ecosystem")),
        program_types=_str_list(program.get("programType")),
        project_types=_str_list(program.get("projectType")) or _str_list(program.get("productType")),
        impacts=impacts,
        critical_impacts=_critical_impacts(impacts),
        # Scope limits and published resources
        exclusions=_exclusions(program),
        resources=_resources(program, audit_records),
        # 9. Recent upgrades / features
        newest_asset_added_at=assets["newest_asset_added_at"],
        days_since_newest_asset=assets["days_since_newest_asset"],
        assets_added_90d=assets["assets_added_90d"],
        assets_revised=assets["assets_revised"],
        # 11. Likely researcher competition
        kyc_required=bool(program.get("kyc")),
        invite_only=bool(program.get("inviteOnly")) or _has("invite only"),
        pay_to_submit=_has(_FEATURE_PAY_TO_SUBMIT),
        subscription_plan=_subscription_plan(features),
        researcher_level_gate=_detect_level_gate(program),
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
