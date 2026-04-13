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
    log_level: str = typer.Option("INFO", "--log-level", help="Python logging level."),
) -> None:
    """Run the full discover → enrich → audit-check → rank pipeline."""
    _setup_logging(log_level)
    s = settings()

    # Allow CLI override of thresholds. These mutate the cached Settings instance.
    if min_tvl is not None:
        s.MIN_TVL_USD = min_tvl  # type: ignore[misc]
        console.print(f"[yellow]Override: MIN_TVL_USD = ${min_tvl:,}[/]")

    if chains is not None:
        chain_list = [Chain(c.strip()) for c in chains.split(",") if c.strip()]
    else:
        chain_list = [Chain(c) for c in s.chain_list]

    console.print(
        f"[bold cyan]tvl-scanner {__version__}[/]  "
        f"chains={', '.join(c.value for c in chain_list)}  "
        f"min_tvl=${s.MIN_TVL_USD:,}  "
        f"cutoff={cutoff}  cap={cap}"
    )

    summary = asyncio.run(run_pipeline(chain_list, cutoff=cutoff, cap=cap))
    console.print(f"\n[bold green]✓ Report written:[/] {summary}")


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
