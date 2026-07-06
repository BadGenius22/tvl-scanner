"""Enable `python -m tvl_scanner ...` (the form documented in CLAUDE.md).

Delegates to the same Typer app as the `tvl-scanner` console script.
"""

from __future__ import annotations

from tvl_scanner.cli import app

if __name__ == "__main__":
    app()
