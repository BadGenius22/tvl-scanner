"""Typer CLI entry point.

Usage:
    tvl-scanner run [--chains solana,arbitrum,base] [--min-tvl 100000] [--cutoff 5.0]
    tvl-scanner check-secrets
    tvl-scanner version
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.logging import RichHandler

if TYPE_CHECKING:
    from tvl_scanner.enrich.immunefi_filter import ProgramFilter

from tvl_scanner import __version__
from tvl_scanner.config import SecretsError, get_secret, settings
from tvl_scanner.models import Chain, Language
from tvl_scanner.pipeline import run_pipeline

app = typer.Typer(
    help="TVL scanner — surfaces under-audited protocols for audit hunting.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _parse_exclude_slugs(text: str) -> set[str]:
    """Parse an exclude-slugs file: one slug per line, or markdown table rows.

    For table rows (`| 1 | Aave V3 | ... |`) the first cell that slugifies to
    something non-numeric wins — pure-numeric cells are rank columns, not
    slugs. Display names slugify with hyphens ("Aave V3" → "aave-v3") so they
    match `target_name` the way the ranked report renders it.
    """
    import re

    slugs: set[str] = set()
    for line in text.splitlines():
        # Strip trailing comments, not just whole-line ones: a kill list is far
        # more useful when each slug carries the reason it was killed, and
        # without this the reason slugifies into the token itself
        # ("kast-already-audited-by-us") and silently matches nothing.
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        tokens = [t.strip() for t in stripped.split("|")]
        for token in tokens or [stripped]:
            if not token:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", token.lower()).strip("-")
            if slug and not slug.isdigit():
                slugs.add(slug)
                break
    return slugs


def _resolve_exclude_slugs(exclude: str | None, exclude_slugs_file: str | None) -> set[str]:
    """Union inline `--exclude` slugs with those from `--exclude-slugs-file`.

    Inline tokens are slugified the same way `_parse_exclude_slugs` does, so
    `--exclude "Aave V3,onre"` matches the `aave-v3` / `onre` target_name the
    ranked report renders. Passing both flags is additive, not either/or.
    """
    import re

    slugs: set[str] = set()
    if exclude:
        for token in exclude.split(","):
            slug = re.sub(r"[^a-z0-9]+", "-", token.lower()).strip("-")
            if slug:
                slugs.add(slug)
    if exclude_slugs_file:
        from pathlib import Path

        path = Path(exclude_slugs_file).expanduser()
        if not path.is_file():
            console.print(f"[red]exclude-slugs-file not found: {path}[/]")
            raise typer.Exit(code=1)
        file_slugs = _parse_exclude_slugs(path.read_text())
        console.print(f"[yellow]Excluding {len(file_slugs)} slug(s) from {path.name}[/]")
        slugs |= file_slugs
    return slugs


def _describe_filters(filters: ProgramFilter) -> str:
    """One-line echo of the active constraints, printed before a scan starts.

    A scan that returns three candidates should never leave the user guessing
    which flag did that, so the constraints are echoed up front and the funnel
    accounts for them afterwards.
    """
    parts: list[str] = []
    if not filters.include_closed:
        parts.append("open programs only")
    else:
        parts.append("including CLOSED programs")
    labels: list[tuple[object, str]] = [
        (filters.min_tvl_usd, "min-tvl=${:,.0f}"),
        (filters.min_max_bounty_usd, "min-bounty=${:,}"),
        (filters.min_critical_floor_usd, "min-critical-floor=${:,}"),
        (filters.min_payout_ratio_pct, "min-payout-ratio={:g}%"),
        (filters.updated_within_days, "updated-within={}d"),
        (filters.max_program_age_days, "max-program-age={}d"),
        (filters.max_known_issues, "max-known-issues={}"),
        (filters.audit_older_than_days, "audit-older-than={}d"),
        (filters.min_scope_contracts, "min-scope={}"),
        (filters.max_scope_contracts, "max-scope={}"),
        (filters.fresh_scope_days, "fresh-scope={}d"),
    ]
    parts.extend(template.format(value) for value, template in labels if value is not None)
    if filters.languages:
        parts.append("languages=" + ",".join(sorted(x.value for x in filters.languages)))
    if filters.kyc is False:
        parts.append("no-kyc")
    for flag, label in (
        (filters.exclude_invite_only, "no-invite-only"),
        (filters.exclude_boosted, "no-boosted"),
        (filters.exclude_pay_to_submit, "no-pay-to-submit"),
        (filters.exclude_level_gated, "no-level-gated"),
        (filters.require_vault, "vault-only"),
        (filters.under_audited_only, "under-audited-only"),
    ):
        if flag:
            parts.append(label)
    if filters.exclude_slugs:
        parts.append(f"exclude={len(filters.exclude_slugs)} slug(s)")
    return ", ".join(parts)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )
    # BATCH H fix #3: quieter HTTP logs. httpx logs every single request at
    # INFO level which buries the useful stage-boundary + summary lines in a
    # ~5000-line wall of "HTTP Request: GET ... 200 OK". Move httpx and
    # httpcore to WARNING so normal INFO runs are skimmable. Users who want
    # the full HTTP trace can pass --log-level DEBUG.
    if level.upper() != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


@app.command()
def run(
    chains: str | None = typer.Option(
        None,
        "--chains",
        help="Comma-separated chain list (e.g. solana,arbitrum,base). Defaults to .env CHAINS.",
    ),
    min_tvl: int | None = typer.Option(
        None, "--min-tvl", help="Override MIN_TVL_USD threshold from .env."
    ),
    cutoff: float = typer.Option(5.0, "--cutoff", help="Priority cutoff for inclusion in report."),
    cap: int = typer.Option(50, "--cap", help="Maximum candidates in report."),
    exclude: str | None = typer.Option(
        None,
        "--exclude",
        help="Comma-separated slugs to drop from the ranked output "
        "(e.g. --exclude twyne,onre,gmtrade). Additive with --exclude-slugs-file.",
    ),
    exclude_slugs_file: str | None = typer.Option(
        None,
        "--exclude-slugs-file",
        help="Path to a file with one slug per line (or one slug per markdown table row). "
        "Excluded slugs are removed from the ranked output before the cap is applied — "
        "useful for follow-up scans that should surface only fresh candidates.",
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Python logging level."),
) -> None:
    """Run the full discover → enrich → audit-check → rank pipeline."""
    _setup_logging(log_level)
    s = settings()

    # Allow CLI override of thresholds. These mutate the cached Settings instance.
    if min_tvl is not None:
        s.MIN_TVL_USD = min_tvl
        console.print(f"[yellow]Override: MIN_TVL_USD = ${min_tvl:,}[/]")

    if chains is not None:
        chain_list = [Chain(c.strip()) for c in chains.split(",") if c.strip()]
    else:
        chain_list = [Chain(c) for c in s.chain_list]

    exclude_slugs = _resolve_exclude_slugs(exclude, exclude_slugs_file)

    console.print(
        f"[bold cyan]tvl-scanner {__version__}[/]  "
        f"chains={', '.join(c.value for c in chain_list)}  "
        f"min_tvl=${s.MIN_TVL_USD:,}  "
        f"cutoff={cutoff}  cap={cap}"
        f"{f'  exclude={len(exclude_slugs)}' if exclude_slugs else ''}"
    )

    summary = asyncio.run(
        run_pipeline(
            chain_list,
            cutoff=cutoff,
            cap=cap,
            exclude_slugs=exclude_slugs or None,
        )
    )
    console.print(f"\n[bold green]✓ Report written:[/] {summary}")


@app.command("immunefi-scan")
def immunefi_scan(
    chains: str | None = typer.Option(
        None,
        "--chains",
        help="Comma-separated chain filter (e.g. ethereum,arbitrum,base). "
        "Default: ALL supported chains — the point is to rank the whole bounty universe.",
    ),
    # --- Availability ---
    include_closed: bool = typer.Option(
        False,
        "--include-closed",
        help="Keep programs whose end date has passed. OFF by default: a closed "
        "competition accepts no submissions, and ~24% of the live catalogue is "
        "already-ended competitions.",
    ),
    exclude_invite_only: bool = typer.Option(
        False,
        "--exclude-invite-only",
        help="Drop invite-only programs (IOP). You cannot submit to those without an "
        "invitation; they are kept by default and flagged in the record.",
    ),
    # --- Criteria 1-3: economics ---
    min_tvl: float | None = typer.Option(
        None, "--min-tvl", help="[1] Drop programs whose protocol TVL is below this floor (USD)."
    ),
    min_bounty: int | None = typer.Option(
        None, "--min-bounty", help="[2] Drop programs whose max payout is below this floor (USD)."
    ),
    min_critical_floor: int | None = typer.Option(
        None,
        "--min-critical-floor",
        help="[2] Drop programs whose critical MINIMUM is below this (USD). Usually a "
        "sharper filter than --min-bounty: expected value tracks the floor, not the ceiling.",
    ),
    min_payout_ratio: float | None = typer.Option(
        None,
        "--min-payout-ratio",
        help="[3] Drop programs whose max payout is below this percent of TVL. "
        "e.g. --min-payout-ratio 1 drops caps worth under 1% of the funds at risk.",
    ),
    # --- Criteria 4-6: program health ---
    updated_within: int | None = typer.Option(
        None,
        "--updated-within",
        help="[4] Keep only programs updated within this many days (drops dormant programs).",
    ),
    max_program_age: int | None = typer.Option(
        None,
        "--max-program-age",
        help="[5] Keep only programs launched within this many days (less picked-over).",
    ),
    max_known_issues: int | None = typer.Option(
        None,
        "--max-known-issues",
        help="[6] Drop programs with more than this many published known issues "
        "(each one is a pre-closed submission area).",
    ),
    # --- Criterion 7: audit history ---
    audit_older_than: int | None = typer.Option(
        None,
        "--audit-older-than",
        help="[7] Keep only programs whose newest listed audit is at least this many days "
        "old. Never-audited programs are kept.",
    ),
    under_audited_only: bool = typer.Option(
        False,
        "--under-audited-only",
        help="[7] Keep only candidates Stage 3 resolves to audit_density_score <= 2.",
    ),
    # --- Criteria 8-9: scope ---
    min_scope: int | None = typer.Option(
        None, "--min-scope", help="[8] Drop programs with fewer in-scope contracts than this."
    ),
    max_scope: int | None = typer.Option(
        None,
        "--max-scope",
        help="[8] Drop programs with more in-scope contracts than this — a 355-contract "
        "scope cannot be covered solo.",
    ),
    fresh_scope: int | None = typer.Option(
        None,
        "--fresh-scope",
        help="[9] Keep only programs that added an in-scope contract within this many days. "
        "Scope added after the last audit priced it is the highest-yield surface.",
    ),
    # --- Criterion 10: technical edge ---
    languages: str | None = typer.Option(
        None,
        "--languages",
        help="[10] Comma-separated language filter (solidity,rust,move). Keeps programs "
        "with at least one match.",
    ),
    # --- Criteria 11-12: competition and payout quality ---
    no_kyc: bool = typer.Option(
        False,
        "--no-kyc",
        help="[11] Only programs that do NOT require KYC (full-payout solo hunting).",
    ),
    exclude_boosted: bool = typer.Option(
        False,
        "--exclude-boosted",
        help="[11] Drop Boosts / audit competitions — many researchers on the same scope at once.",
    ),
    exclude_pay_to_submit: bool = typer.Option(
        False,
        "--exclude-pay-to-submit",
        help="[12] Drop 'Pay to Submit' programs, which charge you a fee per report "
        "regardless of outcome (28 of 247 live programs).",
    ),
    exclude_level_gated: bool = typer.Option(
        False,
        "--exclude-level-gated",
        help="[11] Drop programs that only accept reports from researchers above a given "
        "Immunefi level. LOW RECALL: no structured field exists, so this only catches "
        "programs that say so in prose (1 of 247). Pair it with --exclude-pay-to-submit, "
        "the higher-recall proxy for the same barrier.",
    ),
    require_vault: bool = typer.Option(
        False,
        "--require-vault",
        help="[12] Only programs with an Immunefi Vault (payout funds escrowed on-chain).",
    ),
    cutoff: float = typer.Option(5.0, "--cutoff", help="Priority cutoff for inclusion in report."),
    cap: int = typer.Option(60, "--cap", help="Maximum candidates in report."),
    exclude: str | None = typer.Option(
        None,
        "--exclude",
        help="Comma-separated slugs to drop from the ranked output "
        "(e.g. --exclude twyne,onre,gmtrade). Use for programs already audited or "
        "gate-checked to a dead end, so they stop resurfacing every scan. "
        "Additive with --exclude-slugs-file.",
    ),
    exclude_slugs_file: str | None = typer.Option(
        None,
        "--exclude-slugs-file",
        help="Path to a file with one slug per line (or one slug per markdown table row).",
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Python logging level."),
) -> None:
    """Rank the FULL live Immunefi bounty catalogue on the 12 target-selection criteria.

    Seeds a candidate from every active Immunefi program (not just the TVL-pool
    intersection that `run` covers), resolves TVL + deploy-age best-effort, folds
    in each program's prior-audit record, and ranks on: funds at risk, max/min
    bounty, how the payout is calculated, last program update, program age, known
    issues, audit history, scope architecture, recent scope additions, your
    technical edge, likely researcher competition, and payout/resolution quality.
    Writes reports/YYYY-MM-DD-immunefi-scan.md.

    Note: audit-checking the 0-audit candidates does a rate-limited GitHub contest
    search, so a full pass can take a few minutes.
    """
    _setup_logging(log_level)
    from tvl_scanner.enrich.immunefi_filter import ProgramFilter
    from tvl_scanner.pipeline import run_immunefi_scan

    s = settings()
    if chains is not None:
        chain_list: list[Chain] | None = [Chain(c.strip()) for c in chains.split(",") if c.strip()]
    else:
        chain_list = None  # None → all supported chains
    _ = s  # settings loaded (validates .env) even though thresholds aren't overridden here

    lang_set = (
        {Language(x.strip().lower()) for x in languages.split(",") if x.strip()}
        if languages
        else None
    )

    filters = ProgramFilter(
        include_closed=include_closed,
        exclude_invite_only=exclude_invite_only,
        exclude_slugs=_resolve_exclude_slugs(exclude, exclude_slugs_file),
        min_tvl_usd=min_tvl,
        min_max_bounty_usd=min_bounty,
        min_critical_floor_usd=min_critical_floor,
        min_payout_ratio_pct=min_payout_ratio,
        updated_within_days=updated_within,
        max_program_age_days=max_program_age,
        max_known_issues=max_known_issues,
        audit_older_than_days=audit_older_than,
        min_scope_contracts=min_scope,
        max_scope_contracts=max_scope,
        fresh_scope_days=fresh_scope,
        languages=lang_set,
        kyc=False if no_kyc else None,
        exclude_boosted=exclude_boosted,
        exclude_pay_to_submit=exclude_pay_to_submit,
        exclude_level_gated=exclude_level_gated,
        require_vault=require_vault,
        under_audited_only=under_audited_only,
    )

    console.print(
        f"[bold cyan]tvl-scanner {__version__}[/]  immunefi-scan  "
        f"chains={'all' if chain_list is None else ', '.join(c.value for c in chain_list)}  "
        f"cutoff={cutoff}  cap={cap}"
    )
    console.print(f"[dim]filters: {_describe_filters(filters)}[/]")
    summary = asyncio.run(
        run_immunefi_scan(chain_list, cutoff=cutoff, cap=cap, filters=filters)
    )
    console.print(f"\n[bold green]✓ Immunefi-scan report written:[/] {summary}")


@app.command("delta-watch")
def delta_watch(
    targets: str | None = typer.Option(
        None,
        "--targets",
        help="Comma-separated target slugs to check (e.g. omnipair,project-0). "
        "Defaults to the full data/delta_watch_targets.yaml watchlist.",
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Python logging level."),
) -> None:
    """Flag new commits to fund-exit paths in watched protocols since their last audit.

    The highest-yield audit surface is fresh, unaudited code on permissionless
    paths in an actively-developed protocol. This compares each watched repo's
    baseline (known audited commit, or last-checked commit) against current HEAD
    and reports changes to withdraw/borrow/liquidate/collateral/mint/flashloan files.
    """
    _setup_logging(log_level)
    from tvl_scanner.delta_watch import run_delta_watch

    target_set: set[str] | None = (
        {t.strip().lower() for t in targets.split(",") if t.strip()} if targets else None
    )
    console.print(
        f"[bold cyan]tvl-scanner {__version__}[/]  delta-watch"
        f"{f'  targets={len(target_set)}' if target_set else '  (full watchlist)'}"
    )
    summary = asyncio.run(run_delta_watch(targets=target_set))
    console.print(f"\n[bold green]✓ Delta-watch report written:[/] {summary}")


@app.command("deploy-watch")
def deploy_watch(
    targets: str | None = typer.Option(
        None,
        "--targets",
        help="Comma-separated target slugs to check (e.g. marinade,defisaver-aavev4). "
        "Defaults to the full data/deploy_watch_targets.yaml watchlist.",
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Python logging level."),
) -> None:
    """Flag on-chain DEPLOY/UPGRADE of a watched program or contract.

    Complements delta-watch: some audit triggers are on-chain deploy events, not
    git commits. A protocol can ship already-written, repo-visible code to mainnet
    (flipping a dormant in-scope surface live) — a git watcher can't see that, this
    can. Compares each target's current deploy fingerprint (Solana program slot /
    EVM code hash) to a baseline and reports any that just went live.
    """
    _setup_logging(log_level)
    from tvl_scanner.deploy_watch import run_deploy_watch

    target_set: set[str] | None = (
        {t.strip().lower() for t in targets.split(",") if t.strip()} if targets else None
    )
    console.print(
        f"[bold cyan]tvl-scanner {__version__}[/]  deploy-watch"
        f"{f'  targets={len(target_set)}' if target_set else '  (full watchlist)'}"
    )
    summary = asyncio.run(run_deploy_watch(targets=target_set))
    console.print(f"\n[bold green]✓ Deploy-watch report written:[/] {summary}")


@app.command("check-secrets")
def check_secrets() -> None:
    """Verify all pass-backed API keys are reachable. Does NOT print the secret values."""
    _setup_logging("INFO")
    required = ["github"]
    optional = ["birdeye", "alchemy", "etherscan", "dune"]

    console.print("[bold]Required secrets[/]")
    any_fail = False
    for name in required:
        try:
            value = get_secret(name, required=True)
            assert value is not None
            console.print(f"  ✓ [green]{name}[/]  (length={len(value)})")
        except SecretsError as exc:
            console.print(f"  ✗ [red]{name}[/]  {exc}")
            any_fail = True

    console.print("\n[bold]Optional secrets[/]")
    for name in optional:
        value = get_secret(name, required=False)
        if value:
            console.print(f"  ✓ [green]{name}[/]  (length={len(value)})")
        else:
            console.print(f"  – [dim]{name}[/]  (not configured)")

    if any_fail:
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show the scanner version."""
    console.print(f"tvl-scanner {__version__}")


if __name__ == "__main__":
    app()
