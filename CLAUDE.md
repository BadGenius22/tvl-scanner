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

Top-level orchestration lives in `src/tvl_scanner/pipeline.py`. There are **two parallel discovery paths** that converge before Stage 2 enrichment, deduped by `defillama_slug`:

- **Pool-based** (`discover/`): GeckoTerminal + Birdeye + Alchemy fresh-deployments + RPC active-holders → `DiscoveredContract` → standard `enrich_all`
- **Catalog-based** (`enrich/defillama_protocols.py`): DefiLlama `/protocols` catalog → already an `EnrichedCandidate` (skips Stage 2)

The dedup step (`pipeline._dedupe_enriched`) prefers the DefiLlama catalog record when both paths match the same `defillama_slug`, because catalog TVL is protocol-level (higher) while pool TVL is just one pool.

## Stage modules

| Stage | Module dir | Key files | Output model |
|-------|-----------|-----------|--------------|
| 1 | `discover/` | `merge.py` (orchestrator), `geckoterminal.py`, `birdeye.py`, `alchemy.py`, `rpc.py` | `DiscoveredContract` |
| 2 | `enrich/` | `enricher.py` (orchestrator), `defillama.py`, `defillama_protocols.py` (catalog path), `etherscan.py`, `github.py`, `homepage_scrape.py`, `evm_factory_check.py`, `solana_wrapper_check.py`, `ottersec.py` | `EnrichedCandidate` |
| 3 | `audit_check/` | `checker.py` (orchestrator), `contests.py` (C4/Sherlock/Cantina via GitHub search), `score.py` | `AuditedCandidate` |
| 4 | `rank/` | `priority.py` (formula), `report.py` (markdown + per-candidate YAML) | `CandidateRecord` |

## Priority formula (rank/priority.py)

Weighted sum on a 0-10 scale, cutoff 5.0:

```
priority = 0.25·tvl_score    +  0.20·freshness_score  +  0.30·audit_gap_score
         + 0.15·activity_score + 0.10·edge_match_score + 0.10·bounty_score
```

Each sub-score is normalized to [0, 10]. `audit_gap_score` carries the most weight by design — under-audited is the whole point. `edge_match_score` boosts protocols whose name/slug/type contains an `EDGE_MATCH_KEYWORDS` token (`leverage`, `vault`, `pendle`, `aave`, `anchor`, `noir`, `zk`, etc. — see `config.Settings.EDGE_MATCH_KEYWORDS`).

## Audit-density scoring (audit_check/score.py)

`audit_density_score` is an integer; `under_audited = audit_density_score <= 2`. Signal weights:

- DefiLlama audit links: 1 point each, cap 3
- GitHub `audits/` folder present: 1 point
- C4/Sherlock/Cantina contest hit: 3 points each
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
