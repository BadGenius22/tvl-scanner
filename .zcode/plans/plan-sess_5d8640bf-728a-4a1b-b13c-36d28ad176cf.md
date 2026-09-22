# Red-team funnel: implement the recon stage (R1)

## Priority order (what gets built first, and why)

The conversation settled a 3-layer red-team funnel: **target selection** (exists: `run` + `immunefi-scan`) → **recon** (NEW: code-level signals on the shortlist) → **deep audit** (exists as skills: x-ray → dewaxguard → fizz). Within that:

- **R1 — Recon core (implement now)**: shortlist → fetch source → deterministic code signals → `attack_surface_score` → report + YAML records + payout-path split. This is the only missing piece of the funnel; everything else already exists.
- **R2 — Deeper signals (deferred)**: source-level fork-vs-custom ratio, Anchor/Solana content patterns, exploit-pattern greps (share inflation, oracle-manip recipes), repo-provenance field (org-guessed vs authoritative), LLM brief hook (ROADMAP Batch L convergence).
- **R3 — Automation glue (deferred)**: materialize `~/audit/<date>-<slug>/` workspaces and an x-ray queue driver.

R1 design decisions locked earlier: union of both discovery paths, `$100K` TVL floor everywhere (existing `MIN_TVL_USD` default), volume controlled by `--top N` (score-ranked) not by TVL, `payout_path` splits bounty-backed targets from a pre-bounty watch bucket.

## R1 implementation

### 1. Enabler: persist ranked shortlists (small)

The ranked shortlist exists only as markdown today (immunefi path) — recon needs it machine-readable.

- `pipeline.py`: after `write_report` in **both** `run_pipeline` (line ~122) and `run_immunefi_scan` (line ~203), add `write_ranked(ranked, scan_date, label)` → `artifacts/ranked-{label}.json` (`ranked-scan.json`, `ranked-ranked-immunefi-scan.json` naming follows the report labels). New small writer (mirrors `write_audit_status`: `model_dump(mode="json")` + scan_date/formula header fields).

### 2. Enabler: two small additions to shared layers

- `http.py`: add `get_bytes(url, *, headers=None, client=None) -> bytes` — same retry/rate-limit semantics as `get_json`, for tarball download. Size guard via `Content-Length` against a new setting.
- `enrich/github_delta.py`: add `get_commit_before(owner, repo, until_iso, *, client) -> str | None` — `GET /repos/{o}/{r}/commits?until=...&per_page=1` → sha. Reuses `_auth_headers` + `get_json`; returns None on any failure (never raises).

### 3. New package `src/tvl_scanner/recon/`

Mirrors the delta-watch alternate-entry convention (own orchestrator, state file, report dir), split into modules because it has more concerns:

- **`shortlist.py`** — `load_ranked(label)` reads `artifacts/ranked-{label}.json` back into `CandidateRecord`s; `select_shortlist(from_="union", top=20, min_tvl, targets=None)` interleaves the two lists by rank position (never compares tvl-formula vs bounty-formula scores — documented as incomparable), dedupes by `target_name` preferring the immunefi record (richer: `bounty_profile`, scope repo/branch), applies `--min-tvl` (default `MIN_TVL_USD`=$100K) and the `--top` cap. Also parses an optional watched branch out of `bounty_profile.scope_assets[].repo` paths (`owner/repo/tree/<branch>/...`).
- **`sources.py`** — repo snapshot fetcher: `GET {GITHUB_API_BASE}/repos/{o}/{r}/tarball/{ref}` via `get_bytes` with GitHub auth headers → streamed-safe full-body read → `tarfile` extraction with path-traversal guard (`..`, symlinks), file-count/total-bytes caps. Returns `RepoSnapshot`: all paths (+sizes) for tree signals, contents only for code extensions (`.sol/.rs/.move/.vy`, per-file 1MB cap). Disk cache under `artifacts/recon-cache/{owner}__{repo}__{sha[:10]}/` with a `.complete` marker so interrupted extractions never replay. Degradation rule: tarball over cap or fetch failure → content signals stay unknown (neutral 5.0), delta signals still computed — only "no repo at all" drops the candidate.
- **`signals.py`** — pure functions over the snapshot (no I/O, directly testable): tree signals (source/test file counts via the same exclusion rules as `classify_fund_path`, test-to-source ratio, fund-path file count, CI presence, foundry/hardhat detection) and content-signal greps (curated regex lists: privileged markers `onlyOwner/onlyRole/initializer/Ownable/AccessControlUpgradeable/require(msg.sender…` + Anchor `#[access_control]/has_authority/require_auth`; oracle markers `latestAnswer/latestRoundData/AggregatorV3/getReserves/pyth/switchboard/redstone…`; mitigation markers `nonReentrant/ReentrancyGuard` reported as context). Returns a `ReconSignals` pydantic model.
- **`score.py`** — `attack_surface_score` [0–10], weighted sum, **unknown = neutral 5.0** convention (same as `priority.py`): `0.40·fund_delta + 0.20·test_gap + 0.20·privileged_density + 0.20·oracle_exposure`. `fund_delta_score` log-scales window-delta fund-path additions; each sub-score documented with its normalization. Recon output ranks by `attack_surface_score`; the original `priority_score` is carried as a column (selection vs ranking separation — no formula mixing).
- **`orchestrator.py`** — `run_recon(...)` per candidate: resolve baseline (precedence mirroring delta-watch: scope/watch `audited_at_commit` → commit at `bounty_profile.latest_audit_at` → commit at `now − RECON_SOURCE_WINDOW_DAYS` (90d default, clamped to 365d max window) → state `last_checked_commit` → first-run pins HEAD with delta unknown) → `fetch_delta` (existing) for the window diff → `classify_fund_path`/`_fund_path_changes` (existing) → snapshot → signals → score → `ReconResult`. Funnel counts every drop with a named reason (`no github repo resolved`, `repo inaccessible`, …) via `FilterFunnel` (add a backward-compatible `subject` label param so it doesn't say "programs fetched from the catalogue"). State `artifacts/recon_state.json` (delta-watch format). Semaphore-bounded concurrency (`RECON_CONCURRENCY=3`), `return_exceptions=True` so one target never aborts the run, shared client with `_github_headers`-style auth.
- **`report.py`** — `reports/{date}-recon.md` (funnel block + summary table: rank, protocol, repo, fund-path Δ files/+lines (window), tests, privileged/oracle marker counts, bounty, attack-surface score, record link) + `reports/{date}-recon/candidates/{rank:02d}-{slug}.md`. Per-candidate files follow the delta-watch vault-liftable shape: identity frontmatter (existing key names) **plus new additive keys** `recon_signals:`, `attack_surface_score`, `attack_surface_subscores:`, `payout_path: bounty|none` — the Phase 2a lift ignores unknown keys, and existing keys are never renamed. Body: delta table (delta-watch style), signals breakdown, and a **next-step block**: `payout_path=bounty` → the `new audit on <slug>` trigger phrase + x-ray pointer; `payout_path=none` → a ready-to-paste `delta_watch_targets.yaml` entry (pre-bounty watch bucket; the editable install means pasting into the working-tree YAML is live immediately — recon never edits packaged data itself).

### 4. Models + config + CLI

- `models.py`: `ReconSignals` + `ReconResult` next to `DeltaWatchResult` (models.py:623-707), field names overlapping `CandidateRecord` for the same vault lift.
- `config.py` Settings: `RECON_STATE_FILE`, `RECON_CONCURRENCY=3`, `RECON_SOURCE_WINDOW_DAYS=90`, `RECON_MAX_BASELINE_WINDOW_DAYS=365`, `RECON_MAX_TARBALL_MB=300`, `RECON_CACHE_DIR="recon-cache"`.
- `cli.py`: `tvl-scanner recon [--top 20] [--from union|run|immunefi] [--min-tvl] [--targets slugs] [--refresh-cache] [--log-level]` — delta-watch command shape, lazy import, `asyncio.run(run_recon(...))`.

### 5. Tests + docs

- `tests/test_recon_signals.py` (pure, fake file maps), `test_recon_score.py` (normalization + unknown-neutral), `test_recon_shortlist.py` (load/union/dedupe/floor), `test_recon_sources.py` (in-test-built `tar.gz`, traversal guard, cache reuse; `get_bytes` via `httpx_mock`), `test_recon_orchestrator.py` (patched fetchers, tmp state/reports), `test_cli.py` recon smoke, `test_enrich_github_delta.py` `get_commit_before` case. All under the existing conftest HTTP-block + `pytest-httpx` conventions.
- Update `CLAUDE.md` (Recon mode section, delta-watch precedent), `README.md` usage, `ROADMAP.md` (R1 done, R2/R3 recorded).

### Verification

`make check` equivalent: `pytest`, `ruff check src/` (line-length 100), `mypy src/` (strict) — all green before done.

### Not doing in R1 (recorded so it's a decision, not an omission)

Source-level fork detection (bytecode/wrapper/homepage checks already cover the known false-positive classes), LLM passes (cost gate), auto-editing the delta-watch watchlist (paste-able YAML only), repo-provenance tracking on `github_repo` (report shows the URL for eyeball verification instead).