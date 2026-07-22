"""Top-level orchestration: discover → score → flag new → report.

One shared HTTP client for the whole scan; every stage is pure-python after
discovery so a network-side failure can only lose the fetch, never the report
of what did arrive.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from job_scanner.http import make_client
from job_scanner.profile import Profile, load_profile
from job_scanner.report import write_report
from job_scanner.score import SUITABILITY_CUTOFF, rank_all
from job_scanner.sources.merge import discover_all
from job_scanner.state import flag_and_record, load_state, save_state

log = logging.getLogger(__name__)


async def run_job_scan(
    *,
    profile: Profile | None = None,
    profile_path: str | None = None,
    cutoff: float = SUITABILITY_CUTOFF,
    cap: int = 40,
    new_only: bool = False,
    scan_date: date | None = None,
    reports_dir: Path | None = None,
    state_path: Path | None = None,
) -> Path:
    """Run the full scan and return the summary report path.

    Args:
        profile / profile_path: an in-memory Profile wins over a path.
        cutoff / cap: suitability threshold and report size limit.
        new_only: report only jobs not seen by a previous scan (daily digest mode).
        scan_date / reports_dir / state_path: overridable for tests.
    """
    sdate = scan_date or date.today()
    prof = profile or load_profile(profile_path)
    log.info(
        "=== job-scan: profile=%s remote_only=%s min_salary=$%s ===",
        prof.name,
        prof.remote_only,
        f"{prof.min_salary_usd:,}",
    )

    client = make_client()
    try:
        discovered = await discover_all(prof, client=client)
    finally:
        await client.aclose()

    ranked, dropped = rank_all(discovered, prof, scan_date=sdate, cutoff=cutoff, cap=cap)

    state = load_state(state_path)
    flag_and_record(ranked, state, scan_date=sdate)
    save_state(state, state_path)

    if new_only:
        before = len(ranked)
        ranked = [j for j in ranked if j.is_new]
        log.info("job-scan: new-only filter kept %d/%d", len(ranked), before)

    log.info(
        "=== job-scan: %d suitable role(s) of %d discovered (%d dropped by dealbreakers) ===",
        len(ranked),
        len(discovered),
        sum(dropped.values()),
    )

    summary_path, _ = write_report(
        ranked,
        sdate,
        dropped=dropped,
        total_discovered=len(discovered),
        reports_dir=reports_dir,
    )
    return summary_path
