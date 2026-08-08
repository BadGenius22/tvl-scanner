"""Stage 4 report writer — dual output (summary + per-candidate YAML records).

Two artifacts per scan:

  1. `reports/YYYY-MM-DD-scan.md`
     Human-browsable summary with a ranked table. Dewangga reads this to pick
     candidates.

  2. `reports/YYYY-MM-DD-scan/candidates/<rank>-<slug>.md`
     One file per ranked candidate, YAML frontmatter (Stage 3.5 schema) +
     prose body. Vault Stage A reads exactly one of these files when the
     user says "new audit on <slug> at <path>" and lifts YAML fields into
     `VAULT_CONTEXT.md` (Phase 2a sections 1/2/6/7).

The per-candidate YAML field layout MUST NOT drift from the Stage 3.5 schema
in the plan file — field names are the handoff contract with the vault.
"""

from __future__ import annotations

import logging
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from tvl_scanner.config import settings
from tvl_scanner.models import CandidateRecord

log = logging.getLogger(__name__)


def _fmt_tvl(tvl: float) -> str:
    if tvl >= 1_000_000:
        return f"${tvl / 1_000_000:.1f}M"
    if tvl >= 1_000:
        return f"${tvl / 1_000:.0f}K"
    return f"${int(tvl)}"


def _fmt_age(days: int) -> str:
    if days < 30:
        return f"{days}d"
    if days < 365:
        return f"{days // 30}mo"
    return f"{days // 365}y{(days % 365) // 30}mo"


def _fmt_loc(loc: int | None) -> str:
    if loc is None:
        return "?"
    if loc >= 1000:
        return f"{loc // 1000}k"
    return str(loc)


def _verification_cell(candidate: CandidateRecord) -> str:
    """Compact verification status for the summary table.

    EVM values: '✓' verified, '✗' unverified (RED FLAG), 'P' proxy, '?' not-checked
    Solana values: '✓' OtterSec-registered, '—' not-registered (neutral default)
    """
    is_solana = candidate.chain.value == "solana"
    if is_solana:
        return "✓" if candidate.is_verified else "—"
    # EVM
    if candidate.is_verified is None:
        return "?"
    if not candidate.is_verified:
        return "✗"
    if candidate.is_proxy:
        return "P"
    return "✓"


def _fmt_usd(value: int | None) -> str:
    """Compact USD for table cells. '—' when unknown."""
    if not value:
        return "—"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value // 1_000}K"
    return f"${value}"


def _audits_cell(c: CandidateRecord) -> str:
    """'?' = no source consultable (UNKNOWN), '—' = checked and none found."""
    if not c.audit_record_resolved:
        return "?"
    return str(c.audit_density_score) if c.audit_density_score > 0 else "—"


def _bounty_summary_table(candidates: list[CandidateRecord]) -> str:
    """Ranked table for an immunefi-scan report.

    Different columns from the discovery table because the decision is
    different: what a critical pays, what it pays *relative to* the funds at
    risk, how picked-over the program is, and how much fresh scope landed
    recently. LOC and verification are dropped — they are near-universally
    unknown on catalogue-sourced candidates and were rendering as dead columns.
    """
    lines: list[str] = []
    lines.append(
        "| Rank | Program | Chain | TVL | Max | Crit floor | %TVL | Prog age | Scope | New 90d | Audits | Known | Comp | Priority | Record |"
    )
    lines.append(
        "|------|---------|-------|-----|-----|-----------|------|----------|-------|---------|--------|-------|------|----------|--------|"
    )
    for i, c in enumerate(candidates, start=1):
        p = c.bounty_profile
        flag = " ⚠IOP" if p and p.invite_only else ""
        lines.append(
            "| {rank} | {name} | {chain} | {tvl} | {mx} | {floor} | {pct} | {page} | {scope} | {new} | {audits} | {known} | {comp} | {prio} | {link} |".format(
                rank=i,
                name=c.display_name[:34] + flag,
                chain=c.chain.value,
                tvl=_fmt_tvl(c.tvl_usd) if c.tvl_resolved else "?",
                mx=_fmt_usd(p.max_bounty_usd if p else c.bounty_max_payout_usd),
                floor=_fmt_usd(p.critical_min_usd if p else None),
                pct=(
                    f"{p.max_payout_vs_tvl_pct:.3g}%"
                    if p and p.max_payout_vs_tvl_pct is not None
                    else "?"
                ),
                page=_fmt_age(p.program_age_days) if p and p.program_age_days is not None else "?",
                scope=(str(p.smart_contract_assets) if p else "?"),
                new=(str(p.assets_added_90d) if p and p.assets_added_90d else "—"),
                audits=_audits_cell(c),
                known=(str(p.known_issue_count) if p and p.known_issue_count else "—"),
                comp=f"{c.competition_score:.0f}" if c.competition_score is not None else "?",
                prio=f"{c.priority_score:.1f}",
                link=f"[→](./{{scan_slug}}/candidates/{i:02d}-{c.target_name}.md)",
            )
        )
    return "\n".join(lines)


def _summary_table(candidates: list[CandidateRecord]) -> str:
    """Render the ranked summary table for the scan report."""
    lines: list[str] = []
    lines.append(
        "| Rank | Protocol | Chain | TVL | Age | LOC | Audits | Under-audited | Ver | Bounty | Priority | Record |"
    )
    lines.append(
        "|------|----------|-------|-----|-----|-----|--------|---------------|-----|--------|----------|--------|"
    )
    for i, c in enumerate(candidates, start=1):
        record_link = f"[→](./{{scan_slug}}/candidates/{i:02d}-{c.target_name}.md)"
        # "?" = no audit source was consultable, so the count is UNKNOWN.
        # "—" = we checked and found nothing. Printing "—" for both used to
        # read as "zero audits" for protocols whose audits are simply
        # published somewhere the scanner cannot see (own docs site).
        audits_cell = _audits_cell(c)
        under_cell = "✓" if c.under_audited else ""
        bounty_cell = c.bounty_program if c.bounty_program != "none" else "—"
        lines.append(
            "| {rank} | {name} | {chain} | {tvl} | {age} | {loc} | {audits} | {under} | {ver} | {bounty} | {prio} | {link} |".format(
                rank=i,
                name=c.display_name[:40],
                chain=c.chain.value,
                tvl=_fmt_tvl(c.tvl_usd) if c.tvl_resolved else "?",
                age=_fmt_age(c.age_days),
                loc=_fmt_loc(c.loc_estimate),
                audits=audits_cell,
                under=under_cell,
                ver=_verification_cell(c),
                bounty=bounty_cell,
                prio=f"{c.priority_score:.1f}",
                link=record_link,
            )
        )
    return "\n".join(lines)


def _bounty_summary_header(
    candidates: list[CandidateRecord], scan_date: date, filter_summary: str | None = None
) -> str:
    total = len(candidates)
    under = sum(1 for c in candidates if c.under_audited)
    chains = sorted({c.chain.value for c in candidates})
    profiles = [c.bounty_profile for c in candidates if c.bounty_profile]
    fresh_scope = sum(1 for p in profiles if p.assets_added_90d)
    iop = sum(1 for p in profiles if p.invite_only)
    max_sum = sum(p.max_bounty_usd or 0 for p in profiles)
    audit_dir = settings().AUDIT_DIR.rstrip("/")
    # The funnel goes directly under the counts, not in an appendix: a reader
    # looking at three candidates needs to know whether that is the whole
    # universe or the residue of a narrow filter before reading any further.
    funnel = f"{filter_summary}\n\n" if filter_summary else ""
    return (
        f"# Immunefi Bounty Scan — {scan_date.isoformat()}\n\n"
        f"**Programs ranked**: {total}  \n"
        f"**Under-audited** (audit_density_score ≤ 2): {under}  \n"
        f"**With scope added in the last 90d**: {fresh_scope}  \n"
        f"**Invite-only (cannot submit without an invitation)**: {iop}  \n"
        f"**Chains**: {', '.join(chains)}  \n"
        f"**Combined max payout**: {_fmt_usd(max_sum)}\n\n"
        f"{funnel}"
        f"Ranked on the 12 target-selection criteria (see the breakdown in each record). "
        f"Generated by [tvl-scanner](https://github.com/BadGenius22/tvl-scanner). "
        f"To audit a candidate, say to Claude Code: `new audit on <target_name> at "
        f"{audit_dir}/{scan_date.isoformat()}-<slug>/`.\n\n"
        f"---\n\n"
    )


def _bounty_summary_usage() -> str:
    return (
        "\n\n---\n\n"
        "## How to use this report\n\n"
        "Priority is a 0-10 weighted sum of the 12 target-selection criteria:\n\n"
        "| # | Criterion | Weight | Column |\n"
        "|---|-----------|--------|--------|\n"
        "| 1 | Current TVL / funds at risk | 0.12 | `TVL` |\n"
        "| 2 | Maximum + minimum bounty | 0.12 | `Max`, `Crit floor` |\n"
        "| 3 | Bounty calculation | 0.08 | `%TVL` |\n"
        "| 4 | Last update | 0.05 | — (in record) |\n"
        "| 5 | Program age | 0.06 | `Prog age` |\n"
        "| 6 | Known issues | 0.07 | `Known` |\n"
        "| 7 | Audit history | 0.15 | `Audits` |\n"
        "| 8 | Protocol architecture | 0.07 | `Scope` |\n"
        "| 9 | Recent upgrades / features | 0.10 | `New 90d` |\n"
        "| 10 | Your technical edge | 0.08 | — (in record) |\n"
        "| 11 | Likely researcher competition | 0.06 | `Comp` |\n"
        "| 12 | Historical payout / resolution quality | 0.04 | — (in record) |\n\n"
        "Reading the columns:\n\n"
        "1. **`%TVL`** — the max payout as a percent of funds at risk. This, not `Max`, is what a "
        "critical is really worth: a $50K cap over $2B of TVL is 0.0025%. `?` means TVL is unresolved.\n"
        "2. **`Crit floor`** — the *minimum* a critical pays. Expected value tracks the floor far more "
        "closely than the advertised ceiling; `—` means the program publishes no minimum.\n"
        "3. **`New 90d`** — in-scope contracts added in the last 90 days. Scope that entered the bounty "
        "after the last audit priced it is unreviewed code on a live fund path — start there.\n"
        "4. **`Known`** — published known issues. Each is a pre-closed area: read them before starting, "
        "because findings there return as duplicates regardless of quality.\n"
        "5. **`Comp`** — inverse crowding (higher = fewer researchers to race). Boosts, competitions and "
        "$1M+ headline payouts pull it down; KYC and small obscure programs push it up.\n"
        "6. **`Audits`** — a number is a resolved count, `—` means checked-and-none-found, and **`?` means "
        "UNRESOLVED** — no source was consultable, so the count is unknown, NOT zero. Unresolved candidates "
        "score neutrally, so they are neither rewarded nor punished.\n"
        "7. **`TVL`** — `?` means UNRESOLVED, never a measured $0. Verify on-chain before writing a "
        "protocol off as empty.\n"
        "8. **`⚠IOP`** next to a name — invite-only. You cannot submit without an invitation; "
        "rerun with `--exclude-invite-only` to hide these.\n\n"
        "Priority scores from this report are **not comparable** to those from a `run` scan — "
        "that report uses the 6-factor discovery formula.\n"
    )


def _summary_header(candidates: list[CandidateRecord], scan_date: date) -> str:
    total = len(candidates)
    under = sum(1 for c in candidates if c.under_audited)
    chains = sorted({c.chain.value for c in candidates})
    tvl_sum = sum(c.tvl_usd for c in candidates)
    audit_dir = settings().AUDIT_DIR.rstrip("/")
    return (
        f"# TVL Scanner Report — {scan_date.isoformat()}\n\n"
        f"**Total candidates**: {total}  \n"
        f"**Under-audited** (audit_density_score ≤ 2): {under}  \n"
        f"**Chains scanned**: {', '.join(chains)}  \n"
        f"**Aggregate TVL**: {_fmt_tvl(tvl_sum)}\n\n"
        f"Generated by [tvl-scanner](https://github.com/BadGenius22/tvl-scanner). "
        f"To audit a candidate, say to Claude Code: `new audit on <target_name> at {audit_dir}/{scan_date.isoformat()}-<slug>/` — "
        f"Stage A (Phase 2a) will lift the per-candidate YAML into VAULT_CONTEXT.md.\n\n"
        f"---\n\n"
    )


def _summary_usage() -> str:
    return (
        "\n\n---\n\n"
        "## How to use this report\n\n"
        "1. Skim the ranked table above. Priority is on a 0-10 scale "
        "(tvl × 0.25 + freshness × 0.20 + audit-gap × 0.30 + activity × 0.15 + edge-match × 0.10 + bounty × 0.10).\n"
        "2. Click the `→` link on any row to open the full per-candidate record.\n"
        "3. When you want to audit one, invoke the vault Phase 2a handoff via Claude Code "
        "(see header above for the exact trigger phrase).\n"
        "4. **`TVL` column**: `?` means UNRESOLVED — DefiLlama had no usable figure, so the protocol may still hold real value. Never read it as a measured $0; verify on-chain.\n"
        "5. **`Audits` column**: a number is a resolved count, `—` means checked-and-none-found, "
        "and **`?` means UNRESOLVED** — no audit source was consultable, so the count is unknown, "
        "NOT zero. Protocols that publish audits only on their own docs site read as `?`; verify "
        "manually before believing an audit gap. Unresolved candidates get a neutral audit-gap "
        "score, so they are neither rewarded nor punished by the ranking.\n"
        "6. Skip candidates with `audit_density_score > 2` unless they are a re-audit of code changes since their last review.\n"
    )


def _bounty_profile_section(candidate: CandidateRecord) -> list[str]:
    """Render the 12-criteria program profile for an immunefi-scan record.

    Laid out criterion by criterion, in the rubric's order, so the record reads
    as the answer to the target-selection checklist rather than as a field dump.
    """
    p = candidate.bounty_profile
    if p is None:
        return []

    lines: list[str] = ["## Bounty program profile (12-criteria rubric)", ""]

    if p.invite_only:
        lines.append(
            "> ⚠ **INVITE-ONLY PROGRAM (IOP).** Submissions are closed unless you hold an "
            "invitation. Everything below is moot without one — confirm access before "
            "spending research time."
        )
        lines.append("")
    if p.researcher_level_gate:
        # Same class of blocker as invite-only, so it gets the same top-of-record
        # treatment: whether you can submit at all decides everything below it.
        lines.append(
            "> ⚠ **RESEARCHER-LEVEL GATE.** This program limits who may submit, in its own "
            f"words: “{p.researcher_level_gate}” Check your Immunefi level before starting."
        )
        lines.append("")

    # 1. Funds at risk
    lines.append("### 1. Funds at risk")
    lines.append("")
    if candidate.tvl_resolved:
        lines.append(f"- **TVL**: {_fmt_tvl(candidate.tvl_usd)} (${int(candidate.tvl_usd):,})")
    else:
        lines.append(
            "- **TVL: UNRESOLVED** — no usable DefiLlama figure and the on-chain fallback "
            "did not resolve. This is NOT a measured $0; measure the in-scope contracts "
            "before judging the program's economics."
        )
    lines.append(f"- **In-scope smart contracts**: {p.smart_contract_assets}")
    lines.append("")

    # 2. Max + min bounty
    lines.append("### 2. Maximum + minimum bounty")
    lines.append("")
    lines.append(f"- **Max payout**: {_fmt_usd(p.max_bounty_usd)}")
    lines.append(
        f"- **Critical band**: {_fmt_usd(p.critical_min_usd)} – {_fmt_usd(p.critical_max_usd)}"
    )
    if p.min_bounty_usd:
        lines.append(f"- **Lowest published floor** (any severity): {_fmt_usd(p.min_bounty_usd)}")
    sc_tiers = [t for t in p.reward_tiers if t.asset_type == "smart_contract"]
    if sc_tiers:
        lines.append("- **Smart-contract reward table**:")
        for t in sc_tiers:
            band = (
                f"{_fmt_usd(t.min_usd)} – {_fmt_usd(t.max_usd)}"
                if t.min_usd and t.max_usd and t.min_usd != t.max_usd
                else _fmt_usd(t.max_usd or t.min_usd)
            )
            model = f" ({t.reward_model})" if t.reward_model else ""
            pct = (
                f", {t.calculation_percentage:g}% of funds at risk"
                if t.calculation_percentage
                else ""
            )
            lines.append(f"  - `{t.severity}`: {band}{model}{pct}")
    lines.append("")

    # 3. Bounty calculation
    lines.append("### 3. Bounty calculation")
    lines.append("")
    lines.append(f"- **A critical pays**: {p.payout_basis}")
    if p.max_payout_vs_tvl_pct is not None:
        lines.append(
            f"- **Max payout vs funds at risk**: {p.max_payout_vs_tvl_pct:.4g}% of TVL"
        )
        if p.max_payout_vs_tvl_pct < 1.0:
            lines.append(
                "  - ⚠ The cap binds hard: a full drain of this protocol pays out less than "
                "1% of what it would cost. Weigh the effort against that ceiling, not against "
                "the advertised headline."
            )
    else:
        lines.append(
            "- **Max payout vs funds at risk**: unknown (TVL unresolved) — resolve TVL "
            "before trusting the headline payout."
        )
    if p.poc_required_for_critical:
        lines.append("- **PoC required for critical**: yes — budget for a runnable exploit.")
    lines.append("")

    # 4 + 5. Recency and age of the program
    lines.append("### 4-5. Program update & age")
    lines.append("")
    if p.program_updated_at:
        lines.append(
            f"- **Last updated**: {p.program_updated_at.isoformat()} "
            f"({p.days_since_program_update}d ago)"
        )
        if (p.days_since_program_update or 0) > 365:
            lines.append(
                "  - ⚠ Untouched for over a year. Often a dormant program whose triage queue "
                "nobody reads — check for recent public submissions before committing."
            )
    if p.program_launched_at:
        lines.append(
            f"- **Launched**: {p.program_launched_at.isoformat()} "
            f"({_fmt_age(p.program_age_days or 0)} old)"
        )
    if p.is_time_boxed and p.program_ends_at:
        lines.append(
            f"- **Ends**: {p.program_ends_at.isoformat()} — time-boxed competition, not an "
            "open-ended bounty. Confirm it is still live before starting."
        )
    lines.append("")

    # 6. Known issues
    lines.append("### 6. Known issues")
    lines.append("")
    if not p.known_issue_count:
        lines.append("- None published — no declared dead zones.")
    else:
        lines.append(
            f"- **{p.known_issue_count} published known issue(s)** — findings in these areas "
            "are closed as duplicates regardless of quality. Read all of them first."
        )
        if p.known_issues_last_updated:
            lines.append(f"- **List last updated**: {p.known_issues_last_updated.isoformat()}")
        for issue in p.known_issues[:6]:
            summary = issue.description.replace("\n", " ")[:200]
            link = f" ([ref]({issue.link}))" if issue.link else ""
            lines.append(f"  - {summary}{link}")
        if p.known_issue_count > 6:
            lines.append(f"  - …and {p.known_issue_count - 6} more on the program page.")
    lines.append("")

    # 7. Audit history (recency; the density detail lives in its own section)
    # Named "per Immunefi" to keep it distinct from the scanner's own
    # independently-resolved audit-history section further down the record.
    lines.append("### 7. Audit history (per Immunefi)")
    lines.append("")
    lines.append(f"- **Audits listed by Immunefi**: {p.audit_count}")
    if p.auditors:
        lines.append(f"- **Auditors**: {', '.join(p.auditors)}")
    if p.latest_audit_at:
        lines.append(
            f"- **Most recent audit**: {p.latest_audit_at.isoformat()} "
            f"({p.days_since_latest_audit}d ago)"
        )
        if (p.days_since_latest_audit or 0) > 540:
            lines.append(
                "  - ⚠ Over 18 months old. On an actively developed protocol the report no "
                "longer describes the deployed system — diff against the audited commit and "
                "hunt in what changed since."
            )
    else:
        lines.append(
            "- **Most recent audit**: not dated in the program record — see the audit-history "
            "section below for what the scanner could resolve independently."
        )
    lines.append("")

    # 8. Architecture
    lines.append("### 8. Protocol architecture")
    lines.append("")
    lines.append(
        f"- **In-scope assets**: {p.smart_contract_assets} smart contract, "
        f"{p.web_app_assets} web/app, {p.blockchain_dlt_assets} blockchain/DLT"
    )
    if p.primacy_of_impact:
        lines.append(
            "- **Primacy of Impact**: yes — impact on any contract of the protocol counts, "
            "listed or not. Broad scope, but no map: you pick the entry points."
        )
    if p.ecosystems:
        lines.append(f"- **Ecosystems**: {', '.join(p.ecosystems)}")
    if p.project_types:
        lines.append(f"- **Project type**: {', '.join(p.project_types)}")
    if p.critical_impacts:
        lines.append("- **Pays critical for**:")
        for impact in p.critical_impacts[:5]:
            lines.append(f"  - {impact}")
    lines.append("")

    # 9. Recent upgrades
    lines.append("### 9. Recent upgrades / scope changes")
    lines.append("")
    if p.newest_asset_added_at:
        lines.append(
            f"- **Newest in-scope contract added**: {p.newest_asset_added_at.isoformat()} "
            f"({p.days_since_newest_asset}d ago)"
        )
    if p.assets_added_90d:
        lines.append(
            f"- **{p.assets_added_90d} contract(s) entered scope in the last 90 days** — "
            "the highest-yield surface here. Code added after the last audit priced it is "
            "unreviewed code on a live fund path."
        )
    else:
        lines.append(
            "- No contracts added to scope in the last 90 days — settled scope, so any fresh "
            "code is invisible from the catalogue. Check the repo directly (`delta-watch`)."
        )
    if p.assets_revised:
        lines.append(
            f"- **{p.assets_revised} in-scope asset(s) revised** since being listed "
            "(Immunefi revision counter above zero)."
        )
    lines.append("")

    # 11. Competition
    lines.append("### 11. Likely researcher competition")
    lines.append("")
    signals: list[str] = []
    if p.is_boosted:
        signals.append("live Boost / competition (many eyes at once)")
    if p.boosted_researcher_count:
        signals.append(f"{p.boosted_researcher_count} researchers already paid on the leaderboard")
    if (p.max_bounty_usd or 0) >= 1_000_000:
        signals.append("$1M+ headline payout — on every hunter's shortlist")
    if p.kyc_required:
        signals.append("KYC required (deters part of the field)")
    if p.pay_to_submit:
        signals.append(
            "⚠ Pay to Submit — you are charged a fee per report, win or lose "
            "(also thins the field, so it helps the crowding score and hurts the payout score)"
        )
    if p.researcher_level_gate:
        signals.append(
            f"⚠ **Researcher-level gate** — the program states: “{p.researcher_level_gate}” "
            "Confirm your own Immunefi level clears it before spending any time here."
        )
    if p.immunefi_standard:
        signals.append("Immunefi Standard scope (easy to pick up cold)")
    lines.append(
        f"- **Crowding score**: {candidate.competition_score:.1f}/10 (higher = fewer to race)"
        if candidate.competition_score is not None
        else "- **Crowding score**: unknown"
    )
    for signal in signals:
        lines.append(f"  - {signal}")
    lines.append("")

    # 12. Payout / resolution quality
    lines.append("### 12. Payout & resolution quality")
    lines.append("")
    if p.boosted_total_paid_usd:
        lines.append(
            f"- **Documented payouts**: ${p.boosted_total_paid_usd:,} paid across "
            f"{p.boosted_researcher_count} researchers (leaderboard) — hard evidence this "
            "program pays."
        )
    if p.vault_escrow:
        lines.append(
            "- **Immunefi Vault**: payout funds are escrowed on-chain — ability to pay is "
            "verifiable, not promised."
        )
    if p.safe_harbor:
        lines.append("- **Safe Harbor documents signed** — defined legal cover for whitehat action.")
    if p.arbitration_available:
        lines.append("- **Arbitration available** — triage decisions can be independently contested.")
    if p.pay_to_submit:
        lines.append(
            "- ⚠ **Pay to Submit** — a fee is charged per report regardless of outcome. "
            "Price that into every speculative submission, not just the ones you expect "
            "to be disputed."
        )
    if p.subscription_plan:
        lines.append(
            f"- **Project subscription tier**: {p.subscription_plan} — what the project "
            "pays Immunefi. Usually means a more serviced program (triage, mediation), "
            "not a researcher-facing gate."
        )
    if p.no_free_mediation:
        lines.append(
            "- ⚠ **No free mediations** — contesting a triage decision costs the researcher. "
            "Factor that into disputed-severity risk."
        )
    elif p.pay_to_mediate:
        lines.append("- **Pay to Mediate** — the program prepaid mediation, so disputes get heard.")
    if p.responsible_publication_category:
        lines.append(
            f"- **Responsible publication**: `{p.responsible_publication_category}` — "
            "the program commits to a disclosure category, so a finding can eventually be published."
        )
    if p.managed_triage:
        lines.append("- **Managed Triage** — Immunefi triages first, which usually means faster replies.")
    if not any(
        (
            p.boosted_total_paid_usd,
            p.vault_escrow,
            p.safe_harbor,
            p.arbitration_available,
            p.pay_to_mediate,
            p.pay_to_submit,
            p.subscription_plan,
            p.responsible_publication_category,
            p.managed_triage,
        )
    ):
        lines.append(
            "- No payout-integrity signals published (no Vault, Safe Harbor, arbitration, "
            "or disclosure commitment). Nothing here says they *won't* pay — but nothing "
            "verifies that they will either."
        )
    lines.append("")
    return lines


def _bounty_priority_breakdown(candidate: CandidateRecord) -> list[str]:
    """Render the 12-term weighted breakdown, in rubric order."""
    from tvl_scanner.rank import bounty_priority as bp

    rows: list[tuple[str, float | None, float]] = [
        ("1. funds at risk (tvl)", candidate.tvl_score, bp.W_TVL),
        ("2. bounty size (max+min)", candidate.bounty_size_score, bp.W_BOUNTY_SIZE),
        ("3. bounty calculation", candidate.bounty_calc_score, bp.W_BOUNTY_CALC),
        ("4. last program update", candidate.program_update_score, bp.W_PROGRAM_UPDATE),
        ("5. program age", candidate.program_age_score, bp.W_PROGRAM_AGE),
        ("6. known issues", candidate.known_issues_score, bp.W_KNOWN_ISSUES),
        ("7. audit history (gap + staleness)", candidate.audit_gap_score, bp.W_AUDIT_GAP),
        ("8. protocol architecture", candidate.architecture_score, bp.W_ARCHITECTURE),
        ("9. recent upgrades / scope churn", candidate.upgrade_activity_score, bp.W_UPGRADE_ACTIVITY),
        ("10. technical edge", candidate.edge_match_score, bp.W_EDGE_MATCH),
        ("11. researcher competition (inverse)", candidate.competition_score, bp.W_COMPETITION),
        ("12. payout / resolution quality", candidate.resolution_quality_score, bp.W_RESOLUTION),
    ]
    lines = ["## Priority breakdown (12-criteria bounty formula)", ""]
    lines.append(f"- **Composite**: {candidate.priority_score:.2f} / 10")
    for label, score, weight in rows:
        shown = f"{score:.1f}" if score is not None else "n/a"
        extra = ""
        if label.startswith("10.") and candidate.edge_match_keywords:
            extra = f" (keywords: {', '.join(candidate.edge_match_keywords)})"
        lines.append(f"  - {label}: {shown} × {weight:.2f}{extra}")
    lines.append("")
    lines.append(
        "> A 5.0 in any row means the input was **unknown**, not average — the formula scores "
        "missing catalogue data neutrally so a thin program record is neither rewarded nor punished."
    )
    lines.append("")
    return lines


def _candidate_body(candidate: CandidateRecord) -> str:
    """Render the human-readable body of a per-candidate file (after YAML frontmatter)."""
    lines: list[str] = []
    lines.append(f"# {candidate.display_name}")
    lines.append("")
    lines.append(f"> {candidate.why_interesting}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Chain**: {candidate.chain.value}")
    lines.append(f"- **Primary contract**: `{candidate.primary_contract}`")
    if candidate.tvl_resolved:
        lines.append(f"- **TVL**: {_fmt_tvl(candidate.tvl_usd)} ({int(candidate.tvl_usd):,})")
    else:
        lines.append(
            "- **TVL: UNRESOLVED** — DefiLlama has no usable figure for this protocol "
            "(no name-match, or it is listed with a null tvl). This is NOT a measured "
            "$0; the protocol may hold substantial value. Measure the in-scope "
            "contracts on-chain before judging whether it is worth auditing."
        )
    lines.append(f"- **Age**: {_fmt_age(candidate.age_days)} (first seen {candidate.first_seen.isoformat()})")
    if candidate.unique_users_30d is not None:
        lines.append(f"- **Unique users 30d**: {candidate.unique_users_30d:,}")
    if candidate.loc_estimate:
        lines.append(f"- **LOC estimate**: ~{candidate.loc_estimate:,}")
    if candidate.github_repo:
        lines.append(f"- **GitHub**: {candidate.github_repo}")
    if candidate.docs_url:
        lines.append(f"- **Docs**: {candidate.docs_url}")
    lines.append(f"- **Languages**: {', '.join(lang.value for lang in candidate.languages)}")
    lines.append("")

    # Verification status. Render differently per chain:
    #   EVM (Etherscan): is_verified is True/False, never None. False = red flag.
    #   Solana (OtterSec): is_verified is True (verified) or False (not in OtterSec
    #                      DB, which is the DEFAULT for most programs). False here
    #                      does NOT mean "unverified source" — it means "reproducible
    #                      build not registered". Render it as neutral informational.
    is_solana = candidate.chain.value == "solana"
    if is_solana:
        lines.append("## Reproducible build (OtterSec)")
        lines.append("")
        if candidate.is_verified:
            lines.append("- **Status**: ✓ Registered in OtterSec verified-builds DB")
            if candidate.compiler_version:
                lines.append(f"- **Verification ref**: `{candidate.compiler_version}`")
            lines.append(
                "  - The deployed program bytecode matches a reproducible build from the published source. "
                "You can trust the github_repo above represents the audited code."
            )
        else:
            lines.append("- **Status**: — Not registered in OtterSec")
            lines.append(
                "  - This is the default for most Solana programs (<20% are registered). "
                "NOT a red flag — but you cannot trust that the github_repo matches the deployed "
                "bytecode byte-for-byte without running `solana-verify` yourself."
            )
        lines.append("")

        # On-chain program resolved from the DefiLlama TVL adapter. Only present
        # when the walk (token account → SPL authority → owning program)
        # succeeded — i.e. the TVL is held by a custom program, not a plain
        # wallet or multisig.
        if candidate.solana_program_id:
            lines.append("## On-chain program (resolved on-chain)")
            lines.append("")
            lines.append(
                f"- **Program ID**: `{candidate.solana_program_id}` "
                "(walked from the DefiLlama TVL adapter's token account → SPL authority → owning program)"
            )
            auth_type = candidate.solana_upgrade_authority_type
            if auth_type == "immutable":
                lines.append(
                    "- **Upgrade authority**: none — the program is **IMMUTABLE** "
                    "(cannot be redeployed). Deployed code is the final code."
                )
            elif candidate.solana_upgrade_authority:
                label = {
                    "single_keypair": "⚠ SINGLE KEYPAIR (not a multisig)",
                    "squads_multisig": "Squads multisig (shared custody)",
                }.get(auth_type or "", auth_type or "unknown")
                lines.append(
                    f"- **Upgrade authority**: `{candidate.solana_upgrade_authority}` — {label}"
                )
                if auth_type == "single_keypair":
                    lines.append(
                        "  - ⚠ **Centralization**: a single keypair can redeploy this "
                        "program and reach every account it controls, including the TVL. "
                        "Any code-level finding sits *beneath* a drain risk the operator "
                        "already holds — weigh submission value accordingly, and treat the "
                        "authority key's custody as the dominant risk."
                    )
            lines.append("")
    elif candidate.is_verified is not None:
        lines.append("## On-chain verification (Etherscan V2)")
        lines.append("")
        if candidate.is_verified:
            lines.append("- **Status**: ✓ Verified")
            if candidate.contract_name:
                lines.append(f"- **Contract name**: `{candidate.contract_name}`")
            if candidate.compiler_version:
                lines.append(f"- **Compiler**: `{candidate.compiler_version}`")
            if candidate.is_proxy:
                lines.append(
                    f"- **Proxy**: ✓ EIP-1967 proxy detected → impl `{candidate.proxy_impl_address or 'not set'}`"
                )
                lines.append(
                    "  - ⚠ When auditing, check BOTH the proxy and the implementation. "
                    "Unverified implementation behind a verified proxy is a common obfuscation pattern."
                )
        else:
            lines.append("- **Status**: ✗ UNVERIFIED")
            lines.append(
                "  - ⚠ **Red flag**: the deployed bytecode is not verified on Etherscan. "
                "Either the team hasn't verified yet (ultra-fresh deployment) or they're hiding source. "
                "Do not audit without source — confirm the team has a plan to verify before committing time."
            )
        lines.append("")

    if candidate.bounty_program != "none":
        lines.append("## Bounty program")
        lines.append("")
        lines.append(f"- **Platform**: {candidate.bounty_program}")
        if candidate.bounty_url:
            lines.append(f"- **URL**: {candidate.bounty_url}")
        if candidate.bounty_max_payout_usd:
            lines.append(f"- **Max payout**: ${candidate.bounty_max_payout_usd:,}")
        lines.append("")

    # Full 12-criteria profile — only immunefi-scan candidates carry one.
    lines.extend(_bounty_profile_section(candidate))

    lines.append("## Audit history")
    lines.append("")
    if not candidate.audit_record_resolved:
        lines.append(
            "- **Audit record: UNRESOLVED** — no audit source was consultable "
            "(no DefiLlama audit field, no GitHub repo, no audit URL cited in the "
            "bounty prose). The density score below is *unknown*, not zero. Many "
            "protocols publish audits only on their own docs site, which this "
            "scanner cannot see. **Verify manually before treating as a gap.**"
        )
    lines.append(f"- **Audit density score**: {candidate.audit_density_score} "
                 f"({'unknown — see above' if not candidate.audit_record_resolved else 'under-audited' if candidate.under_audited else 'already audited'})")
    if candidate.defillama_audit_count is not None:
        lines.append(
            f"- **DefiLlama audit count**: {candidate.defillama_audit_count} "
            f"(from /protocol/{{slug}} detail)".replace("{slug}", candidate.defillama_slug or "")
        )
    if candidate.defillama_audit_note:
        lines.append(f"- **DefiLlama audit note**: *{candidate.defillama_audit_note}*")
    if not candidate.audit_sources_found:
        lines.append(
            "- **Audit record unresolved** — nothing to check, see caveat above."
            if not candidate.audit_record_resolved
            else "- **No audits found** in any checked source."
        )
    else:
        lines.append("- Sources found:")
        for src in candidate.audit_sources_found:
            title = src.title or str(src.url or src.source)
            lines.append(f"  - `{src.source}` ({src.weight}pt): {title}")
    lines.append("")

    if candidate.priority_formula == "bounty":
        lines.extend(_bounty_priority_breakdown(candidate))
    else:
        lines.append("## Priority breakdown")
        lines.append("")
        lines.append(f"- **Composite**: {candidate.priority_score:.2f} / 10")
        lines.append(f"  - tvl: {candidate.tvl_score:.1f} × 0.25")
        lines.append(f"  - freshness: {candidate.freshness_score:.1f} × 0.20")
        lines.append(f"  - audit_gap: {candidate.audit_gap_score:.1f} × 0.30")
        lines.append(f"  - activity: {candidate.activity_score:.1f} × 0.15")
        lines.append(f"  - edge_match: {candidate.edge_match_score:.1f} × 0.10 "
                     f"(keywords: {', '.join(candidate.edge_match_keywords) or 'none'})")
        lines.append(f"  - bounty: {candidate.bounty_score:.1f} × 0.10")
        lines.append("")

    lines.append("## Suggested focus areas")
    lines.append("")
    for area in candidate.focus_areas_suggested:
        lines.append(f"- {area}")
    lines.append("")

    lines.append("## Vault handoff (Phase 2a)")
    lines.append("")
    lines.append("To audit this candidate, say to Claude Code:")
    lines.append("")
    audit_dir = settings().AUDIT_DIR.rstrip("/")
    lines.append(
        f"> `new audit on {candidate.target_name} at {audit_dir}/"
        f"{candidate.scan_date.isoformat()}-{candidate.target_name}/`"
    )
    lines.append("")
    lines.append(
        "Stage A will read this file, lift the YAML frontmatter fields into "
        "VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable "
        "patterns and case studies (sections 3/4), and propose the full file "
        "per Phase 2a safety gates."
    )
    lines.append("")
    return "\n".join(lines)


def _bounty_frontmatter(candidate: CandidateRecord) -> dict[str, Any]:
    """Section-7 extension for immunefi-scan records. Empty dict for `run` records.

    Additive by design: the vault's Phase 2a template reads the Stage 3.5 field
    names, and unknown keys are ignored by the lift, so adding the program
    profile here cannot break an existing handoff. Nested under
    `bounty_program_profile` rather than flattened so the top-level namespace
    the vault template does read stays exactly as it was.
    """
    p = candidate.bounty_profile
    if p is None:
        return {}
    return {
        "bounty_min_payout_usd": p.min_bounty_usd,
        "bounty_critical_min_usd": p.critical_min_usd,
        "bounty_critical_max_usd": p.critical_max_usd,
        "bounty_payout_basis": p.payout_basis,
        "bounty_max_payout_vs_tvl_pct": p.max_payout_vs_tvl_pct,
        "bounty_invite_only": p.invite_only,
        "bounty_kyc_required": p.kyc_required,
        "bounty_known_issue_count": p.known_issue_count,
        "bounty_program_age_days": p.program_age_days,
        "bounty_days_since_program_update": p.days_since_program_update,
        "bounty_days_since_latest_audit": p.days_since_latest_audit,
        "bounty_assets_added_90d": p.assets_added_90d,
        "bounty_in_scope_contracts": p.smart_contract_assets,
        "bounty_critical_impacts": p.critical_impacts,
        # Full profile + per-criterion scores, for anything that wants the detail.
        "bounty_program_profile": p.model_dump(mode="json"),
        "priority_formula": candidate.priority_formula,
        "priority_subscores": {
            "tvl": candidate.tvl_score,
            "bounty_size": candidate.bounty_size_score,
            "bounty_calc": candidate.bounty_calc_score,
            "program_update": candidate.program_update_score,
            "program_age": candidate.program_age_score,
            "known_issues": candidate.known_issues_score,
            "audit_gap": candidate.audit_gap_score,
            "architecture": candidate.architecture_score,
            "upgrade_activity": candidate.upgrade_activity_score,
            "edge_match": candidate.edge_match_score,
            "competition": candidate.competition_score,
            "resolution_quality": candidate.resolution_quality_score,
        },
    }


def _frontmatter_dict(candidate: CandidateRecord) -> dict[str, Any]:
    """Build the YAML frontmatter dict. Field names MUST match Stage 3.5 schema."""
    return {
        # --- Section 1: Target Identification ---
        "target_name": candidate.target_name,
        "display_name": candidate.display_name,
        "protocol_type": candidate.protocol_type,
        "languages": [lang.value for lang in candidate.languages],
        "chains": [candidate.chain.value],
        "inferred_platform": candidate.inferred_platform,
        "inferred_mode": candidate.inferred_mode,
        # --- Section 2: Prior Audits ---
        "audit_density_score": candidate.audit_density_score,
        "audit_sources_found": [
            {
                "source": src.source,
                "url": str(src.url) if src.url else None,
                "title": src.title,
                "published_at": src.published_at.isoformat() if src.published_at else None,
            }
            for src in candidate.audit_sources_found
        ],
        "under_audited": candidate.under_audited,
        # False = no audit source was consultable, so audit_density_score is
        # UNKNOWN rather than zero. Lifted into the vault so a downstream audit
        # never reads an unresolved record as a confirmed audit gap.
        "audit_record_resolved": candidate.audit_record_resolved,
        # --- Section 6: Suggested Focus Areas ---
        "edge_match_keywords": candidate.edge_match_keywords,
        "focus_areas_suggested": candidate.focus_areas_suggested,
        # --- Section 7: Submission Platform Context ---
        "bounty_program": candidate.bounty_program,
        "bounty_url": str(candidate.bounty_url) if candidate.bounty_url else None,
        "bounty_max_payout_usd": candidate.bounty_max_payout_usd,
        **_bounty_frontmatter(candidate),
        # --- Scanner metadata (not lifted but useful) ---
        "tvl_usd": candidate.tvl_usd,
        # False = unmeasured; tvl_usd is a 0.0 placeholder, not a real zero.
        "tvl_resolved": candidate.tvl_resolved,
        "first_seen": candidate.first_seen.isoformat(),
        "age_days": candidate.age_days,
        "unique_users_30d": candidate.unique_users_30d,
        "github_repo": str(candidate.github_repo) if candidate.github_repo else None,
        "loc_estimate": candidate.loc_estimate,
        "docs_url": str(candidate.docs_url) if candidate.docs_url else None,
        # Real on-chain contract resolved from the DefiLlama detail endpoint
        # (chain-qualified). None for catalog candidates whose address couldn't
        # be resolved (BSC free-tier, Solana, no detail address) and for pool
        # candidates (whose `address` is already the real contract).
        "onchain_address": candidate.onchain_address,
        # Solana program resolved from the DefiLlama TVL adapter (None for EVM
        # and for custodied Solana protocols with no custom program). The
        # upgrade-authority type is a centralization signal the auditor must
        # weigh: "single_keypair" = one key can redeploy and reach all funds.
        "solana_program_id": candidate.solana_program_id,
        "solana_upgrade_authority": candidate.solana_upgrade_authority,
        "solana_upgrade_authority_type": candidate.solana_upgrade_authority_type,
        "primary_contract": candidate.primary_contract,
        "priority_score": candidate.priority_score,
        "why_interesting": candidate.why_interesting,
        "scan_date": candidate.scan_date.isoformat(),
        # --- Etherscan V2 verification (EVM only; None on Solana/synthetic) ---
        "is_verified": candidate.is_verified,
        "contract_name": candidate.contract_name,
        "is_proxy": candidate.is_proxy,
        "proxy_impl_address": candidate.proxy_impl_address,
        "compiler_version": candidate.compiler_version,
        # --- DefiLlama audit history deep enrichment ---
        "defillama_audit_count": candidate.defillama_audit_count,
        "defillama_audit_note": candidate.defillama_audit_note,
    }


def write_candidate_file(
    candidate: CandidateRecord, rank: int, out_dir: Path
) -> Path:
    """Write one per-candidate file to `<out_dir>/candidates/<rank>-<slug>.md`."""
    candidates_dir = out_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    path = candidates_dir / f"{rank:02d}-{candidate.target_name}.md"

    frontmatter = _frontmatter_dict(candidate)
    yaml_text = yaml.safe_dump(
        frontmatter, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
    body = _candidate_body(candidate)
    content = f"---\n{yaml_text}---\n\n{body}"
    path.write_text(content)
    return path


def write_report(
    candidates: list[CandidateRecord],
    scan_date: date,
    *,
    reports_dir: Path | None = None,
    label: str = "scan",
    filter_summary: str | None = None,
) -> tuple[Path, list[Path]]:
    """Write both the summary report and per-candidate files.

    Returns (summary_path, candidate_file_paths).

    `filter_summary` is the rendered filter funnel (immunefi-scan only). It is
    written into the summary header so a short candidate list is always
    attributable to the constraints that produced it rather than read as
    "this is all there was".

    BUGFIX (post-Batch I.2): the per-candidate directory is purged before
    writing new files. Without this, multiple scans on the same date
    accumulated files like `01-pendle.md` (v0.4.0) + `01-jagpool-staked-sol.md`
    (v0.4.1) side-by-side, making the folder visually misleading even
    though the summary table was correct. The cleanup wipes the
    `<scan_slug>/candidates/` subdirectory entirely before recreating it.
    The summary `.md` itself is naturally overwritten so doesn't need
    explicit cleanup.
    """
    s = settings()
    reports_dir = reports_dir or s.reports_path
    reports_dir.mkdir(parents=True, exist_ok=True)
    scan_slug = f"{scan_date.isoformat()}-{label}"

    # Purge stale per-candidate files from prior scans on the same date.
    out_dir = reports_dir / scan_slug
    candidates_dir = out_dir / "candidates"
    if candidates_dir.exists():
        shutil.rmtree(candidates_dir)

    # Per-candidate files
    candidate_paths: list[Path] = []
    for i, candidate in enumerate(candidates, start=1):
        candidate_paths.append(write_candidate_file(candidate, i, out_dir))

    # Summary report. The bounty layout is selected by what the candidates
    # actually carry, not by the label: a record scored on the 12-criteria
    # formula has columns (payout ratio, scope churn, crowding) that the
    # discovery table has no place for, and vice versa.
    summary_path = reports_dir / f"{scan_slug}.md"
    # `filter_summary` is passed only by the immunefi path, so it also selects
    # the bounty layout when every candidate was filtered out — an empty scan
    # must still show the funnel that emptied it, not a bare discovery table.
    is_bounty = filter_summary is not None or (
        bool(candidates) and all(c.priority_formula == "bounty" for c in candidates)
    )
    if is_bounty:
        body = (
            _bounty_summary_header(candidates, scan_date, filter_summary)
            + _bounty_summary_table(candidates).replace("{scan_slug}", scan_slug)
            + _bounty_summary_usage()
        )
    else:
        body = (
            _summary_header(candidates, scan_date)
            + _summary_table(candidates).replace("{scan_slug}", scan_slug)
            + _summary_usage()
        )
    summary_path.write_text(body)

    log.info(
        "wrote %s and %d per-candidate files under %s",
        summary_path,
        len(candidate_paths),
        out_dir,
    )
    return summary_path, candidate_paths
