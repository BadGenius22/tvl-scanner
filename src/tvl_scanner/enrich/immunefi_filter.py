"""Declarative filtering for the Immunefi bounty universe.

The catalogue is 247 programs. Almost none of them are a fit for any given
researcher, so the filters are not a convenience — they are how the scan gets
from "every live bounty" to a shortlist worth reading. Two design rules:

**Filtering happens before enrichment.** `discover_from_immunefi_catalog` builds
every candidate first (pure, no I/O), applies these filters, and only then spends
the deploy-date, audits-folder, homepage-scrape and on-chain-TVL passes on the
survivors. A filter that drops 200 programs saves 200 programs' worth of network
work, so filters must never be applied at rank time when they could run here.

**Every drop is counted and reported.** A filter that silently removes the thing
you were looking for is worse than no filter. `FilterFunnel` records the reason
for every rejection and the scan prints the funnel, so a shortlist of three is
always traceable to the criteria that produced it.

On unknown values: a filter is a request for a *guarantee*, so a program whose
value cannot be confirmed does not qualify — but it is counted under its own
reason ("no max payout published", not "max payout below floor") so the funnel
shows the difference between "this failed your bar" and "this could not be
checked". That is deliberately the opposite of the *scoring* convention, where
unknown is neutral: a score is an estimate, a filter is a constraint.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date

from pydantic import BaseModel, Field

from tvl_scanner.models import EnrichedCandidate, Language

log = logging.getLogger(__name__)

# Rejection reasons, in the order they are checked and rendered. Keeping the
# order explicit (rather than relying on Counter insertion order) makes the
# funnel stable across runs, so two scans can be diffed.
REASON_NO_CHAIN = "no in-scope contract on a supported chain"
REASON_CLOSED = "program closed (competition ended)"
REASON_INVITE_ONLY = "--exclude-invite-only: invitation required"
REASON_EXCLUDED_SLUG = "--exclude: named on the exclusion list"
REASON_KYC = "--no-kyc: KYC required"
REASON_BOUNTY_UNKNOWN = "--min-bounty: no max payout published"
REASON_BOUNTY_LOW = "--min-bounty: max payout below floor"
REASON_FLOOR_UNKNOWN = "--min-critical-floor: no critical minimum published"
REASON_FLOOR_LOW = "--min-critical-floor: critical minimum below floor"
REASON_UPDATED_UNKNOWN = "--updated-within: no update date published"
REASON_UPDATED_STALE = "--updated-within: program not updated recently enough"
REASON_AGE_UNKNOWN = "--max-program-age: no launch date published"
REASON_AGE_OLD = "--max-program-age: program older than limit"
REASON_KNOWN_ISSUES = "--max-known-issues: too many published known issues"
REASON_AUDIT_RECENT = "--audit-older-than: audited too recently"
REASON_SCOPE_SMALL = "--min-scope: too few in-scope contracts"
REASON_SCOPE_LARGE = "--max-scope: too many in-scope contracts"
REASON_SCOPE_STALE_UNKNOWN = "--fresh-scope: no scope-addition dates published"
REASON_SCOPE_STALE = "--fresh-scope: no contracts added to scope recently"
REASON_LANGUAGE = "--languages: no matching language"
REASON_BOOSTED = "--exclude-boosted: live boost / competition"
REASON_PAY_TO_SUBMIT = "--exclude-pay-to-submit: charges a fee per report"
REASON_PREMIUM = "--exclude-premium: project is on a paid Immunefi subscription plan"
REASON_NO_VAULT = "--require-vault: no escrowed payout vault"
REASON_TVL_UNKNOWN = "--min-tvl: TVL unresolved"
REASON_TVL_LOW = "--min-tvl: TVL below floor"
REASON_RATIO_UNKNOWN = "--min-payout-ratio: TVL unresolved, ratio not computable"
REASON_RATIO_LOW = "--min-payout-ratio: max payout too small against funds at risk"
REASON_NOT_UNDER_AUDITED = "--under-audited-only: audit density above 2"

REASON_ORDER: tuple[str, ...] = (
    REASON_NO_CHAIN,
    REASON_CLOSED,
    REASON_INVITE_ONLY,
    REASON_EXCLUDED_SLUG,
    REASON_KYC,
    REASON_BOUNTY_UNKNOWN,
    REASON_BOUNTY_LOW,
    REASON_FLOOR_UNKNOWN,
    REASON_FLOOR_LOW,
    REASON_UPDATED_UNKNOWN,
    REASON_UPDATED_STALE,
    REASON_AGE_UNKNOWN,
    REASON_AGE_OLD,
    REASON_KNOWN_ISSUES,
    REASON_AUDIT_RECENT,
    REASON_SCOPE_SMALL,
    REASON_SCOPE_LARGE,
    REASON_SCOPE_STALE_UNKNOWN,
    REASON_SCOPE_STALE,
    REASON_LANGUAGE,
    REASON_BOOSTED,
    REASON_PAY_TO_SUBMIT,
    REASON_PREMIUM,
    REASON_NO_VAULT,
    REASON_TVL_UNKNOWN,
    REASON_TVL_LOW,
    REASON_RATIO_UNKNOWN,
    REASON_RATIO_LOW,
    REASON_NOT_UNDER_AUDITED,
)


def _norm_slug(raw: str) -> str:
    return raw.strip().lower().replace(" ", "-")


class ProgramFilter(BaseModel):
    """Declarative filter over the Immunefi bounty universe.

    Grouped by the target-selection criterion each field serves. Every field
    defaults to "no constraint", so `ProgramFilter()` keeps everything except
    closed programs — see `include_closed`.
    """

    # --- Availability: can you actually submit? ---
    include_closed: bool = Field(
        default=False,
        description=(
            "Keep programs whose endDate has passed. Off by default because a "
            "closed competition accepts no submissions — 59 of the 247 live "
            "catalogue entries are already-ended competitions (one closed in "
            "2024), and they were ranking alongside open bounties."
        ),
    )
    exclude_invite_only: bool = False
    exclude_slugs: set[str] = Field(default_factory=set)

    # --- 1-3. Economics ---
    min_tvl_usd: float | None = None
    min_max_bounty_usd: int | None = None
    min_critical_floor_usd: int | None = Field(
        default=None,
        description=(
            "Floor on what a critical *minimum* pays. Expected value tracks the "
            "floor far more closely than the advertised ceiling, so this is "
            "usually a sharper filter than --min-bounty."
        ),
    )
    min_payout_ratio_pct: float | None = Field(
        default=None,
        description="Floor on max payout as a percent of TVL — drops caps that bind hard.",
    )

    # --- 4-6. Program health ---
    updated_within_days: int | None = None
    max_program_age_days: int | None = None
    max_known_issues: int | None = None

    # --- 7. Audit history ---
    audit_older_than_days: int | None = Field(
        default=None,
        description=(
            "Keep only programs whose newest listed audit is at least this old. "
            "Programs with NO listed audit are kept — an unaudited program is "
            "the limiting case of stale coverage, not an exception to it."
        ),
    )

    # --- 8-9. Scope ---
    min_scope_contracts: int | None = None
    max_scope_contracts: int | None = None
    fresh_scope_days: int | None = Field(
        default=None,
        description="Keep only programs that added an in-scope contract within this window.",
    )

    # --- 10. Technical edge ---
    languages: set[Language] | None = None

    # --- 11-12. Competition and payout quality ---
    kyc: bool | None = None
    exclude_boosted: bool = False
    exclude_pay_to_submit: bool = Field(
        default=False,
        description=(
            "Drop 'Pay to Submit' programs, which charge the researcher a fee per "
            "report. 28 of 247 live programs carry it."
        ),
    )
    exclude_premium: bool = Field(
        default=False,
        description=(
            "Drop programs whose PROJECT is on a paid Immunefi subscription plan "
            "(Essential / Pro / Elite) — 52 of 247 live programs. Immunefi publishes "
            "no field called 'premium'; the subscription tier is the closest real "
            "concept, and it is a property of what the project buys from Immunefi, "
            "not a researcher-facing gate. Use --exclude-pay-to-submit for the fee "
            "that actually lands on you; 20 programs carry both."
        ),
    )
    require_vault: bool = False

    # --- Post-Stage-3 (needs the resolved audit record) ---
    under_audited_only: bool = False

    @property
    def is_active(self) -> bool:
        """True when any constraint beyond the closed-program default is set."""
        default = ProgramFilter()
        return self.model_dump(exclude={"include_closed"}) != default.model_dump(
            exclude={"include_closed"}
        )

    def reject_reason(self, candidate: EnrichedCandidate, *, scan_date: date) -> str | None:
        """Why this candidate should be dropped, or None to keep it.

        Covers every constraint that can be evaluated without network I/O, so
        the caller can run it before enrichment. TVL-dependent constraints are
        in `tvl_reject_reason`; the audit-record constraint is in
        `audit_reject_reason`.
        """
        p = candidate.bounty_profile

        # --- Availability first: an unsubmittable program fails every other
        # test vacuously, and saying "closed" is more useful than "payout low".
        if (
            p is not None
            and not self.include_closed
            and p.program_ends_at is not None
            and p.program_ends_at < scan_date
        ):
            return REASON_CLOSED
        if self.exclude_invite_only and p is not None and p.invite_only:
            return REASON_INVITE_ONLY
        if self.exclude_slugs and self._is_excluded(candidate):
            return REASON_EXCLUDED_SLUG

        if p is None:
            # No program record: nothing below is checkable. Keep it — a missing
            # profile is a scanner gap, not a property of the program.
            return None

        # --- 11. Competition ---
        if self.kyc is not None and p.kyc_required != self.kyc:
            return REASON_KYC
        if self.exclude_boosted and p.is_boosted:
            return REASON_BOOSTED
        if self.exclude_pay_to_submit and p.pay_to_submit:
            return REASON_PAY_TO_SUBMIT
        if self.exclude_premium and p.subscription_plan:
            return REASON_PREMIUM

        # --- 2. Bounty size ---
        if self.min_max_bounty_usd is not None:
            if not p.max_bounty_usd:
                return REASON_BOUNTY_UNKNOWN
            if p.max_bounty_usd < self.min_max_bounty_usd:
                return REASON_BOUNTY_LOW
        if self.min_critical_floor_usd is not None:
            floor = p.critical_min_usd or p.min_bounty_usd
            if not floor:
                return REASON_FLOOR_UNKNOWN
            if floor < self.min_critical_floor_usd:
                return REASON_FLOOR_LOW

        # --- 4. Last update ---
        if self.updated_within_days is not None:
            if p.days_since_program_update is None:
                return REASON_UPDATED_UNKNOWN
            if p.days_since_program_update > self.updated_within_days:
                return REASON_UPDATED_STALE

        # --- 5. Program age ---
        if self.max_program_age_days is not None:
            if p.program_age_days is None:
                return REASON_AGE_UNKNOWN
            if p.program_age_days > self.max_program_age_days:
                return REASON_AGE_OLD

        # --- 6. Known issues ---
        if self.max_known_issues is not None and p.known_issue_count > self.max_known_issues:
            return REASON_KNOWN_ISSUES

        # --- 7. Audit staleness ---
        if self.audit_older_than_days is not None:
            days = p.days_since_latest_audit
            # No listed audit → kept: never audited is maximally stale coverage.
            if days is not None and days < self.audit_older_than_days:
                return REASON_AUDIT_RECENT

        # --- 8. Scope size ---
        if self.min_scope_contracts is not None and p.smart_contract_assets < self.min_scope_contracts:
            return REASON_SCOPE_SMALL
        if self.max_scope_contracts is not None and p.smart_contract_assets > self.max_scope_contracts:
            return REASON_SCOPE_LARGE

        # --- 9. Scope freshness ---
        if self.fresh_scope_days is not None:
            if p.days_since_newest_asset is None:
                return REASON_SCOPE_STALE_UNKNOWN
            if p.days_since_newest_asset > self.fresh_scope_days:
                return REASON_SCOPE_STALE

        # --- 10. Technical edge ---
        if self.languages and not (set(candidate.languages) & self.languages):
            return REASON_LANGUAGE

        # --- 12. Payout quality ---
        if self.require_vault and not p.vault_escrow:
            return REASON_NO_VAULT

        return None

    def tvl_reject_reason(self, candidate: EnrichedCandidate) -> str | None:
        """Constraints that need TVL, so they run after the on-chain fallback."""
        if self.min_tvl_usd is not None:
            if not candidate.tvl_resolved:
                return REASON_TVL_UNKNOWN
            if candidate.tvl_usd < self.min_tvl_usd:
                return REASON_TVL_LOW
        if self.min_payout_ratio_pct is not None:
            p = candidate.bounty_profile
            ratio = p.max_payout_vs_tvl_pct if p else None
            if ratio is None:
                return REASON_RATIO_UNKNOWN
            if ratio < self.min_payout_ratio_pct:
                return REASON_RATIO_LOW
        return None

    def audit_reject_reason(self, under_audited: bool) -> str | None:
        """The one constraint that needs Stage 3's resolved audit record."""
        if self.under_audited_only and not under_audited:
            return REASON_NOT_UNDER_AUDITED
        return None

    def _is_excluded(self, candidate: EnrichedCandidate) -> bool:
        """Match the exclusion list against every name the program is known by.

        A user reads a slug off the report table, the record filename or the
        DefiLlama link and types it back — all three should work, so the match
        covers the Immunefi slug, the DefiLlama slug and the display name.
        """
        skip = {_norm_slug(s) for s in self.exclude_slugs if s.strip()}
        if not skip:
            return False
        names = {
            _norm_slug(candidate.target_name),
            _norm_slug(candidate.display_name),
        }
        if candidate.defillama_slug:
            names.add(_norm_slug(candidate.defillama_slug))
        return bool(names & skip)


class FilterFunnel:
    """Counts what each filter removed, so a small shortlist is explainable."""

    def __init__(self, fetched: int = 0) -> None:
        self.fetched = fetched
        self.dropped: Counter[str] = Counter()

    def drop(self, reason: str) -> None:
        self.dropped[reason] += 1

    @property
    def total_dropped(self) -> int:
        return sum(self.dropped.values())

    @property
    def kept(self) -> int:
        return self.fetched - self.total_dropped

    def rows(self) -> list[tuple[str, int]]:
        """(reason, count) in the canonical order, omitting reasons that fired zero times."""
        ordered = [(r, self.dropped[r]) for r in REASON_ORDER if self.dropped[r]]
        # Any reason not in REASON_ORDER (future additions) still gets reported.
        extra = sorted(
            (r, n) for r, n in self.dropped.items() if r not in REASON_ORDER and n
        )
        return ordered + extra

    def render(self, *, indent: str = "  ") -> str:
        """Plain-text funnel, widest number right-aligned."""
        rows = self.rows()
        lines = [f"{indent}{self.fetched:>5}  programs fetched from the catalogue"]
        for reason, count in rows:
            lines.append(f"{indent}{-count:>5}  {reason}")
        lines.append(f"{indent}{'-' * 5}")
        lines.append(f"{indent}{self.kept:>5}  candidates kept")
        return "\n".join(lines)

    def render_markdown(self) -> str:
        """Funnel as a markdown list, for the report header."""
        rows = self.rows()
        if not rows:
            return f"All {self.fetched} catalogue programs kept — no filter removed anything."
        lines = [f"**Filter funnel** — {self.fetched} programs fetched:", ""]
        lines.extend(f"- −{count} {reason}" for reason, count in rows)
        lines.append("")
        lines.append(f"**{self.kept} candidates kept** for enrichment and ranking.")
        return "\n".join(lines)
