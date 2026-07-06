"""Typer CLI entry point.

Usage:
    tvl-scanner run [--chains solana,arbitrum,base] [--min-tvl 100000] [--cutoff 5.0]
    tvl-scanner check-secrets
    tvl-scanner version
"""

from __future__ import annotations

import asyncio
import logging

import typer
from rich.console import Console
from rich.logging import RichHandler

from tvl_scanner import __version__
from tvl_scanner.config import SecretsError, get_secret, settings
from tvl_scanner.models import Chain
from tvl_scanner.pipeline import run_pipeline

app = typer.Typer(
    help="TVL scanner — surfaces under-audited protocols for audit hunting.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


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

    exclude_slugs: set[str] = set()
    if exclude_slugs_file:
        import re
        from pathlib import Path
        path = Path(exclude_slugs_file).expanduser()
        if not path.is_file():
            console.print(f"[red]exclude-slugs-file not found: {path}[/]")
            raise typer.Exit(code=1)
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Tolerate markdown table cells like `| Protocol | … |` — extract slug-like token
            tokens = [t.strip() for t in stripped.split("|")]
            for token in tokens or [stripped]:
                if not token:
                    continue
                # Take the first token that looks like a slug (lowercase, hyphenated)
                slug = re.sub(r"[^a-z0-9-]", "", token.lower())
                if slug:
                    exclude_slugs.add(slug)
                    break
        console.print(f"[yellow]Excluding {len(exclude_slugs)} slug(s) from {path.name}[/]")

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
