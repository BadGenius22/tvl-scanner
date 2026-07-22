"""Typer CLI entry point.

Usage:
    job-scanner run [--profile profile.yaml] [--cutoff 5.0] [--cap 40] [--new-only]
    job-scanner show-profile
    job-scanner version
"""

from __future__ import annotations

import asyncio
import logging

import typer
from rich.console import Console
from rich.logging import RichHandler

from job_scanner import __version__
from job_scanner.profile import load_profile
from job_scanner.score import SUITABILITY_CUTOFF

app = typer.Typer(
    help="job-scanner — surfaces open roles ranked by personal suitability.",
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
    # httpx logs every request at INFO, burying the stage-boundary lines.
    if level.upper() != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


@app.command()
def run(
    profile: str | None = typer.Option(
        None, "--profile", help="Path to a profile.yaml (default: repo-root profile.yaml, then packaged default)."
    ),
    cutoff: float = typer.Option(
        SUITABILITY_CUTOFF, "--cutoff", help="Suitability cutoff for inclusion in the report."
    ),
    cap: int = typer.Option(40, "--cap", help="Maximum roles in the report."),
    new_only: bool = typer.Option(
        False, "--new-only", help="Report only roles not seen by a previous scan (daily digest)."
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Python logging level."),
) -> None:
    """Run the full discover → score → report scan."""
    _setup_logging(log_level)
    from job_scanner.pipeline import run_job_scan

    prof = load_profile(profile)
    console.print(
        f"[bold cyan]job-scanner {__version__}[/]  "
        f"profile={prof.name}  cutoff={cutoff}  cap={cap}"
        f"{'  new-only' if new_only else ''}"
    )
    summary = asyncio.run(
        run_job_scan(profile=prof, cutoff=cutoff, cap=cap, new_only=new_only)
    )
    console.print(f"\n[bold green]✓ Report written:[/] {summary}")


@app.command("show-profile")
def show_profile(
    profile: str | None = typer.Option(None, "--profile", help="Path to a profile.yaml."),
) -> None:
    """Print the resolved profile — what 'suitable' currently means."""
    _setup_logging("WARNING")
    prof = load_profile(profile)
    console.print_json(prof.model_dump_json(indent=2))


@app.command()
def version() -> None:
    """Show the scanner version."""
    console.print(f"job-scanner {__version__}")


if __name__ == "__main__":
    app()
