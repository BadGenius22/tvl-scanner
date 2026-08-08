# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

TVL-weighted attack-surface scanner that surfaces under-audited smart contract protocols (>$100K TVL, <12 months old, ≤2 prior audits). Output feeds the `VAULT_CONTEXT.md` Phase 2a handoff in the Dewaxindo workspace — picked candidates flow directly into DewaxGuard/Plamen audit pipelines.

Each scan writes a summary at `reports/YYYY-MM-DD-scan.md` plus per-candidate YAML records at `reports/YYYY-MM-DD-scan/candidates/<rank>-<slug>.md`. The YAML frontmatter is shaped to match `VAULT_CONTEXT.md` sections so it lifts without transformation.

## Common commands

```bash
# Run full pipeline (Stage 1 → 4)
python -m tvl_scanner run --chains solana,arbitrum,base --min-tvl 100000

# Override scoring cutoff / cap
python -m tvl_scanner run --cutoff 5.0 --cap 50

# Debug mode (httpx request logs)
python -m tvl_scanner run --log-level DEBUG

# Delta-watch: flag NEW commits to fund-exit paths in watched protocols since
# their last audit (the highest-yield surface — fresh unaudited code on
# permissionless paths). Watchlist: src/tvl_scanner/data/delta_watch_targets.yaml
python -m tvl_scanner delta-watch
python -m tvl_scanner delta-watch --targets omnipair,project-0

# Immunefi-scan: rank the FULL live Immunefi bounty catalogue by the priority
# formula (bounty-first discovery — seeds a candidate from EVERY active program,
# not just the TVL-pool intersection `run` covers). Best for target selection.
python -m tvl_scanner immunefi-scan --no-kyc --min-bounty 500000
python -m tvl_scanner immunefi-scan --chains ethereum,arbitrum,base --cap 60
# Solo-hunter slice: real payout floor, readable scope, fresh code, no crowds
python -m tvl_scanner immunefi-scan --min-critical-floor 25000 --max-scope 60 \
    --fresh-scope 180 --updated-within 180 --exclude-boosted --exclude-invite-only

# Verify pass-backed secrets are reachable
tvl-scanner check-secrets

# Tests / lint / typecheck
pytest                                  # all tests (pythonpath=src, asyncio_mode=auto)
pytest tests/test_enrich_etherscan.py   # single file
pytest -k "test_score_compute"          # single test by name
ruff check src/                         # lint
mypy src/                               # type check (strict mode)
```

Tests use `pytest-httpx` fixtures — HTTP is mocked, no live API calls.

## Secrets — pass (not .env)

Secrets live in the `pass` GPG store under the `tvl-scanner/` prefix; only non-secret config lives in `.env`. `config.get_secret(name)` is the single read path — every module calls it instead of touching `pass` or env vars directly. Resolution order: `pass show tvl-scanner/<name>` → `TVL_SCANNER_<NAME_UPPER>` env var (CI fallback) → SecretsError if `required=True`.

Required: `github`. Optional: `birdeye`, `alchemy`, `etherscan`, `dune`.

**WSL/non-TTY note**: gpg-agent cache must be primed once per day from a real terminal (`pass show tvl-scanner/github >/dev/null`) — the scanner runs in a non-TTY subprocess and cannot prompt for passphrase.

## Pipeline architecture

Four sequential stages, each writing a JSON artifact at its boundary so a mid-pipeline failure does not lose prior work. Stages communicate in-memory during a run; the artifacts are inspection/debug aids, not the handoff mechanism.

```
Stage 1: Discover    → artifacts/candidates.json       (DiscoveredContract)
Stage 2: Enrich      → artifacts/enriched.json         (EnrichedCandidate)
Stage 3: Audit-check → artifacts/audit_status.json     (AuditedCandidate)
Stage 4: Rank+Report → reports/YYYY-MM-DD-scan.md + candidates/*.md (CandidateRecord)
```

### Delta-watch mode (alternate entry, not part of the 4-stage scan)

`delta_watch.py` (`tvl-scanner delta-watch`) is a separate entry point for a different question: *what fresh, unaudited code landed on fund-exit paths since a protocol's last audit?* It is independent of the discover→rank pipeline. For each entry in `data/delta_watch_targets.yaml` it GitHub-`compare`s a baseline commit (precedence: `audited_at_commit` → last-checked commit from `artifacts/delta_watch_state.json` → current HEAD on first run) against HEAD, classifies changed files against `Settings.FUND_PATH_KEYWORDS` (withdraw/borrow/liquidate/collateral/mint/flashloan/...), scores by fund-path-change magnitude, and writes `reports/YYYY-MM-DD-delta-watch.md` + per-target YAML records (same vault-liftable frontmatter as scan candidates). The GitHub `/compare` + `/commits` access lives in `enrich/github_delta.py` (reuses `enrich/github.py` auth + `http.get_json`). State persists so reruns are incremental. Rationale: the highest-yield audit surface is the delta of an actively-developed protocol, not a protocol audited cold.

### Immunefi-scan mode (bounty-first discovery — alternate entry)

`enrich/immunefi_catalog.py` (`tvl-scanner immunefi-scan`, orchestrated by `pipeline.run_immunefi_scan`) inverts the normal flow. The 4-stage `run` and the DefiLlama-catalog path discover protocols by TVL and then *tag* whichever ones happen to have a bounty (`enrich/immunefi.py`), so they are blind to any active bounty whose protocol the TVL/pool discovery never surfaces. Immunefi-scan instead seeds one `EnrichedCandidate` from EVERY active program in the live Immunefi catalogue (`immunefi.fetch_raw`), so the whole bounty universe gets ranked — this is the target-selection tool. It does NOT use the 6-factor discovery formula: every candidate here already has a bounty, so `bounty_score` is a constant and `activity_score` is always the neutral 5.0 (Immunefi publishes no user counts). It ranks on the 12-criteria bounty formula instead (`rank/bounty_priority.py`, below). Immunefi's catalogue already carries the bounty (payout/KYC/url), the in-scope contract addresses (chain inferred from the explorer domain — etherscan/arbiscan/basescan/…), the github repo, the languages, and the prior-audit record; the builder resolves only TVL + category (DefiLlama name-match, reusing `DefiLlamaCatalog.lookup`) and the TRUE deploy date (`enrich/etherscan.py`, EVM only) itself. A program with no in-scope contract on a supported `Chain` is skipped and counted, never silently dropped. The folded audit count (max of DefiLlama's and Immunefi's own `audits` list) feeds `defillama_audit_count`, which also makes Stage 3 skip the rate-limited GitHub contest search for already-audited programs. Writes `reports/YYYY-MM-DD-immunefi-scan.md`. Default chain scope is ALL supported chains (not the `.env` subset) — the point is the full universe.

#### Filtering (`enrich/immunefi_filter.py`)

The catalogue is ~247 programs and almost none fit any given researcher, so filtering is how the scan gets to a shortlist. `ProgramFilter` is one declarative object covering every constraint, with one flag per rubric criterion:

| Criterion | Flags |
|-----------|-------|
| availability | `--include-closed`, `--exclude-invite-only`, `--exclude` / `--exclude-slugs-file` |
| 1 funds at risk | `--min-tvl` |
| 2 bounty size | `--min-bounty`, `--min-critical-floor` |
| 3 bounty calculation | `--min-payout-ratio` |
| 4 last update | `--updated-within` |
| 5 program age | `--max-program-age` |
| 6 known issues | `--max-known-issues` |
| 7 audit history | `--audit-older-than`, `--under-audited-only` |
| 8 architecture | `--min-scope`, `--max-scope` |
| 9 recent upgrades | `--fresh-scope` |
| 10 technical edge | `--languages` |
| 11 competition | `--no-kyc`, `--exclude-boosted`, `--exclude-level-gated` |
| 12 payout quality | `--require-vault`, `--exclude-pay-to-submit` |

Three rules the module exists to enforce:

- **Closed programs are dropped by default.** Every `endDate` in the live feed is in the past — 59 of 247 entries are ended competitions (one closed in 2024), and they were ranking alongside open bounties where they cannot be submitted to. `--include-closed` restores the old behaviour.
- **Filtering happens before enrichment.** `_build_candidate` no longer filters at all; it decides scanner *coverage* only (returns None just for "no in-scope contract on a supported chain"). The user's constraints are applied to built candidates immediately afterwards, so the deploy-date, audits-folder, homepage-scrape and on-chain-TVL passes only ever touch survivors. Two constraints cannot run there: `--min-tvl` / `--min-payout-ratio` wait until after the on-chain TVL fallback, and `--under-audited-only` waits for Stage 3.
- **Submission barriers are two flags, because the catalogue only half-exposes them.** Immunefi gates some programs by researcher level — below the threshold you either cannot submit or you pay a per-report fee. Only the fee is structured: the `Pay to Submit` feature, on 28 of 247 programs (`--exclude-pay-to-submit`). The level gate itself has NO field, so `immunefi_profile._detect_level_gate` reads it out of the program prose and stores the verbatim sentence (`--exclude-level-gated`). That is deliberately low-recall — 1 of 247 in the 2026-08 snapshot (Alchemix: *"reports from researchers at the Intermediate level or higher"*) — so treat the fee flag as the higher-recall proxy for the same barrier. The detector requires a level name AND the literal word "level" AND a researcher-facing word in one sentence; the middle condition is what stops Royco's and Strata's junior/senior *tranches* from matching.
- **Scoring.** `pay_to_submit` moves BOTH ways and is scored in both places rather than netted: +1.0 on criterion 11 (a per-report fee thins the field) and −2.0 on criterion 12 (a cost shifted onto you, on every submission rather than only disputes). `researcher_level_gate` and `subscription_plan` are deliberately UNSCORED — whether a gate blocks you depends on your own Immunefi level, which the scanner cannot know, so the record quotes the claim and flags it at the top like invite-only. The project's subscription tier (Essential/Pro/Elite) is context only: it is what the project buys from Immunefi, not a gate on you, and it usually means a *better*-serviced program.
- **Every drop is counted and named.** `FilterFunnel` records a reason per rejection; the funnel is logged and written into the report header, so a three-candidate shortlist is never mistaken for "that is all there was". Unknown values get their *own* reason (`no max payout published` vs `max payout below floor`) — a filter is a constraint, so unverifiable means excluded, but the funnel shows which happened. That is deliberately the opposite of the *scoring* convention, where unknown is neutral.

`enrich/immunefi_profile.py` extracts a `BountyProfile` from each raw program dict — pure, no extra network call, since the catalogue already carries everything. It covers the criteria that live on the *program* rather than the code: the reward table (max/min per severity, `rewardModel`, `rewardCalculationPercentage`, the Immunefi 10% economic rule), `updatedDate`/`launchDate`/`endDate`, `knownIssues`, audit *recency* from `audits[].date`, per-type asset counts + `impacts`, scope churn from `assets[].addedAt/revision`, and the competition/resolution flags (`kyc`, `inviteOnly`, `features`, `boostedLeaderboard`, `responsiblePublicationCategory`). Every extractor degrades to a neutral default independently — one malformed program must never abort a 247-program scan. `attach_payout_ratio` fills `max_payout_vs_tvl_pct` once TVL resolves (again after the on-chain fallback), because a $50K cap over $2B of funds at risk is 0.0025% and that, not the headline, is what a critical is worth.

Top-level orchestration lives in `src/tvl_scanner/pipeline.py`. There are **two parallel discovery paths** that converge before Stage 2 enrichment, deduped by `defillama_slug`:

- **Pool-based** (`discover/`): GeckoTerminal + Birdeye + Alchemy fresh-deployments + RPC active-holders → `DiscoveredContract` → standard `enrich_all`
- **Catalog-based** (`enrich/defillama_protocols.py`): DefiLlama `/protocols` catalog → already an `EnrichedCandidate` (skips Stage 2)

The dedup step (`pipeline._dedupe_enriched`) prefers the DefiLlama catalog record when both paths match the same `defillama_slug`, because catalog TVL is protocol-level (higher) while pool TVL is just one pool.

## Stage modules

| Stage | Module dir | Key files | Output model |
|-------|-----------|-----------|--------------|
| 1 | `discover/` | `merge.py` (orchestrator), `geckoterminal.py`, `birdeye.py`, `alchemy.py`, `rpc.py` | `DiscoveredContract` |
| 2 | `enrich/` | `enricher.py` (orchestrator), `defillama.py`, `defillama_protocols.py` (catalog path), `etherscan.py`, `github.py`, `homepage_scrape.py`, `evm_factory_check.py`, `solana_wrapper_check.py`, `solana_rpc.py` (resolves a DefiLlama Solana catalog candidate to its real on-chain program + upgrade-authority type — Stage 1 has no Solana leg, so catalog Solana rows are otherwise DefiLlama-only with no code pointer), `ottersec.py`, `bounty.py` (curated bounty registry) + `immunefi.py` (live Immunefi catalogue — address/name match) + `bugbounty_directory.py` (broad fallback: the lissy93/bug-bounties directory of ~3k programs — catches HackerOne/Bugcrowd/Intigriti/self-hosted bounties the Immunefi-centric sources miss; conservative domain/distinctive-name match, paying programs only; consulted only after curated seeds + live Immunefi both miss) + `immunefi_catalog.py` (bounty-first discovery — seeds a candidate per active Immunefi program; see `immunefi-scan` mode) + `immunefi_profile.py` (pure extractor: raw program dict → `BountyProfile`, the 12-criteria target-selection record) + `immunefi_filter.py` (`ProgramFilter` + `FilterFunnel` — every immunefi-scan constraint, applied pre-enrichment with a named reason per drop) | `EnrichedCandidate` |
| 3 | `audit_check/` | `checker.py` (orchestrator), `contests.py` (Sherlock/Cantina via GitHub search), `score.py` | `AuditedCandidate` |
| 4 | `rank/` | `priority.py` (6-factor discovery formula), `bounty_priority.py` (12-criteria bounty formula — `immunefi-scan` only), `report.py` (markdown + per-candidate YAML; picks the summary layout from `priority_formula`) | `CandidateRecord` |

## Priority formula (rank/priority.py)

Weighted sum on a 0-10 scale, cutoff 5.0:

```
priority = 0.25·tvl_score    +  0.20·freshness_score  +  0.30·audit_gap_score
         + 0.15·activity_score + 0.10·edge_match_score + 0.10·bounty_score
```

Each sub-score is normalized to [0, 10]. `audit_gap_score` carries the most weight by design — under-audited is the whole point. `edge_match_score` boosts protocols whose name/slug/type contains an `EDGE_MATCH_KEYWORDS` token (`leverage`, `vault`, `pendle`, `aave`, `anchor`, `noir`, `zk`, etc. — see `config.Settings.EDGE_MATCH_KEYWORDS`).

This formula ranks *discovery*: of all the protocols on chain, which are worth a look. `immunefi-scan` uses the formula below instead.

## Bounty priority formula (rank/bounty_priority.py) — immunefi-scan only

Weighted sum on a 0-10 scale, cutoff 5.0, over the 12 target-selection criteria. Every candidate already has a bounty here, so the question is not "is this worth a look" but "is this program worth a solo researcher's weeks":

| # | Criterion | Weight | Field | Signal |
|---|-----------|--------|-------|--------|
| 1 | Current TVL / funds at risk | 0.12 | `tvl_score` | reused from `priority.py` |
| 2 | Maximum + minimum bounty | 0.12 | `bounty_size_score` | log-scaled ceiling (60%) blended with the critical *floor* (40%) — EV tracks the floor, not the headline |
| 3 | Bounty calculation | 0.08 | `bounty_calc_score` | reward model (`range`/`fixed`/`up_to`, % of funds at risk, 10% economic rule) blended 50/50 with `max_payout_vs_tvl_pct` |
| 4 | Last update | 0.05 | `program_update_score` | `updatedDate` decay over 730d — a dormant program's triage queue is unread |
| 5 | Program age | 0.06 | `program_age_score` | flat 10 for 90d, decaying to 0 at 3y — every live month is another sweep of the same surface |
| 6 | Known issues | 0.07 | `known_issues_score` | `10 − 1.5·count`; each published issue is a pre-closed submission area |
| 7 | Audit history | 0.15 | `audit_gap_score` | `priority.audit_gap_score` plus up to +3 when the newest audit is >540d old |
| 8 | Protocol architecture | 0.07 | `architecture_score` | scope size (3-25 contracts is the solo-readable band) × smart-contract share of assets |
| 9 | Recent upgrades / features | 0.10 | `upgrade_activity_score` | `assets[].addedAt` churn — delta-watch's thesis on the bounty side: scope added after the last audit is unreviewed code on a live fund path |
| 10 | Your technical edge | 0.08 | `edge_match_score` | reused from `priority.py` |
| 11 | Likely researcher competition | 0.06 | `competition_score` | inverse crowding: invite-only floors it; Boosts, leaderboards and $1M+ headlines pull down; KYC and small programs push up |
| 12 | Historical payout / resolution | 0.04 | `resolution_quality_score` | leaderboard payouts (hard evidence), Vault escrow, Safe Harbor, arbitration, publication category; paid mediation subtracts |

Audit history keeps the largest single weight, as in the discovery formula. Funds at risk + bounty size together (0.24) set what a finding is worth; scope churn (0.10) locates where to look.

**Unknown is neutral, not zero.** Every sub-score returns 5.0 when its input is missing, so a thin catalogue record is neither rewarded nor punished — the same convention `priority.py` uses for unresolved TVL and audit records. A 5.0 in a report row means *unknown*, not *average*.

Scores from the two formulas are **not comparable**; `CandidateRecord.priority_formula` (`"tvl"` / `"bounty"`) records which produced a given row, and `report.py` selects the summary table layout from it.

## Audit-density scoring (audit_check/score.py)

`audit_density_score` is an integer; `under_audited = audit_density_score <= 2`. Signal weights:

- DefiLlama audit links: 1 point each, cap 3
- GitHub `audits/` folder present: 1 point
- Sherlock/Cantina contest hit: 3 points each (Code4rena removed: the fine-grained `github` PAT gets HTTP 422 on `org:code-423n4`, so it only burned search quota)
- Solodit / docs mention: deferred to v2

**Allowlist override**: `KNOWN_AUDITED_SLUG_PREFIXES` in `score.py` short-circuits known upstreams (e.g. `uniswap-*` pools) so each V4 pool doesn't surface as a false-positive "under-audited" candidate.

**Batch H fix in `checker.check_one`**: candidates with a non-zero `defillama_audit_count` skip the GitHub contest search entirely (Stage 3's purpose is to find what DefiLlama missed; re-confirming saturates GitHub search's 30/min rate limit). Concurrency is capped at 2 with a per-scan `token_cache` shared across all candidates so brand-collapsing protocols (Aave/Aave V2/Aave V3 → `aave`) only cost one round-trip.

## HTTP client (http.py)

All upstream calls go through `http.get_json()` — tenacity retries (`RETRYABLE` tuple), exponential backoff, 429/5xx wrapped as `ReadTimeout` to trigger retry. Per-client headers passed via kwarg, not stored. Tests inject `client=` to mock with `pytest-httpx`. Don't bypass this layer when adding new sources.

## Data models (models.py)

The stage progression mirrors the class hierarchy: `DiscoveredContract` (Stage 1) → `EnrichedCandidate` (Stage 2 extends) → `AuditedCandidate` (Stage 3 extends with `audit_density_score`) → `CandidateRecord` (Stage 4 extends with scoring + `why_interesting` + `focus_areas_suggested`). Each Stage's output is a strict superset of the previous.

`CandidateRecord` field names mirror `VAULT_CONTEXT.md` section labels so YAML frontmatter lifts directly into Phase 2a templates without a translation layer. Don't rename these fields without checking the vault template first.

## Adding a new discovery / enrichment source

1. Drop a new file under `discover/<source>.py` or `enrich/<source>.py` exposing a single async function.
2. Wire it into the corresponding orchestrator (`discover/merge.py` for Stage 1, `enrich/enricher.py` for Stage 2).
3. Use `http.get_json(client=client)` — never instantiate `httpx.AsyncClient` directly outside `http.py` / `make_client()`.
4. Use `config.get_secret("<name>", required=...)` for API keys.
5. Add a `DiscoverySource` or `AuditSourceKind` enum entry in `models.py` if it's a new evidence kind.
6. Mock it in tests with `pytest-httpx` (see `tests/test_discover_geckoterminal.py` for the pattern).

## Vault handoff (Phase 2a)

When a candidate is picked, say in Claude Code: `new audit on <slug> at ~/audit/<date>-<slug>/`. Stage A of the vault workflow reads `reports/<date>-scan/candidates/<rank>-<slug>.md`, lifts the YAML frontmatter into a `VAULT_CONTEXT.md` draft, and proposes for approval per Phase 2a gates. The scanner itself does NOT touch the vault.

The base path for handoffs is configurable via `AUDIT_DIR` in `.env` (default `~/audit`).
