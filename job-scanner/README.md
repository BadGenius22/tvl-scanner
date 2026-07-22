# job-scanner

Daily open-role scanner: discovers jobs from public boards, judges each one
against **your** profile (skills, seniority, salary floor, location, benefits),
and writes a ranked report — new listings flagged since the last run.

Sibling tool to [tvl-scanner](https://github.com/BadGenius22/tvl-scanner): same
architecture (async sources → weighted scoring formula → markdown + per-record
YAML reports), pointed at job boards instead of DeFi protocols.

## How it works

```
Discover   sources/  → Remotive · RemoteOK · Arbeitnow · Greenhouse* · Lever*   (JobPosting)
Score      score.py  → 6 sub-scores, weighted suitability on a 0-10 scale       (ScoredJob)
Flag new   state.py  → artifacts/job_scan_state.json (seen job_ids)
Report     report.py → reports/YYYY-MM-DD-job-scan.md + roles/<rank>-<slug>.md
```

\* Greenhouse/Lever pull directly from the boards of companies you watchlist in
the profile — no aggregator lag for dream-company openings.

All sources are public, keyless JSON APIs. No secrets needed.

### Suitability formula

```
suitability = 0.30·skill_match + 0.20·compensation + 0.15·location
            + 0.15·seniority   + 0.10·benefits     + 0.10·freshness
```

Each sub-score is normalized to [0, 10]. Skill match carries the most weight by
design — a perfectly-paid job you're not a fit for is still not suitable.
Unknown facts (no salary stated, no posting date) score neutral, never zero.
Hard dealbreakers (excluded title keywords, below the seniority floor,
onsite-only outside your locations) drop a listing before scoring — counted in
the report, never silently.

## Quick start

```bash
pip install -e ".[dev]"

# Everything reads from the profile — copy the default and make it yours
cp src/job_scanner/data/profile.yaml profile.yaml
$EDITOR profile.yaml        # skills, salary floor, locations, benefits, watchlist

job-scanner run                       # full scan → reports/YYYY-MM-DD-job-scan.md
job-scanner run --new-only            # daily digest: only unseen roles
job-scanner run --cutoff 6 --cap 20   # stricter, shorter report
job-scanner show-profile              # print the resolved profile

# Tests / lint / typecheck (HTTP is mocked; no live calls)
pytest
ruff check src/ tests/
mypy src/
```

The default profile is tuned for a blockchain-security / smart-contract
engineering profile — edit `profile.yaml` to redefine "suitable" for you.

## Running daily

`.github/workflows/job-scan.yml` runs the scan every day at 05:00 WIB
(22:00 UTC) and commits the report + seen-state back to the repo, so each day's
report lands in `reports/` with 🆕 markers on listings the previous scans never
saw.

GitHub only runs scheduled workflows from a repo's **default branch** — the
cron goes live once this directory is pushed to its own repository (see below).
Until then, run manually (`job-scanner run --new-only`) or via the Actions tab
(`workflow_dispatch`) after the move.

## Moving to its own repository

This project is fully self-contained (its own `pyproject.toml`, no imports
from tvl_scanner). To give it its own repo:

```bash
# 1. Create an empty repo on GitHub (e.g. BadGenius22/job-scanner, private)
# 2. From the tvl-scanner checkout:
cp -r job-scanner ~/job-scanner && cd ~/job-scanner
git init -b main && git add -A && git commit -m "job-scanner v0.1.0"
git remote add origin git@github.com:BadGenius22/job-scanner.git
git push -u origin main
```

The daily cron activates on the first push.

## Layout

| Module | Purpose |
| ------ | ------- |
| `sources/` | one async fetcher per board + `merge.py` orchestrator (dedupe by company+title) |
| `profile.py` | loads `profile.yaml` — the single definition of "suitable" |
| `salary.py` | best-effort salary text → annualized USD (feeds compensation score) |
| `score.py` | sub-scores, dealbreakers, weighted formula |
| `state.py` | seen job_ids → the 🆕 flag on daily runs |
| `report.py` | summary markdown + per-role YAML records |
| `pipeline.py` | discover → score → flag → report |

### Adding a new source

1. Drop `sources/<board>.py` exposing a single async `fetch_<board>()` returning `list[JobPosting]`.
2. Wire it into `sources/merge.py`.
3. Use `http.get_json(client=client)` — never instantiate `httpx.AsyncClient` directly.
4. Mock it in tests with `pytest-httpx` (see `tests/test_sources_remotive.py` for the pattern).
