# tvl-scanner

TVL-weighted attack surface scanner for under-audited smart contract protocols.

Surfaces protocols that (a) hold real money (>$100K TVL), (b) are fresh (<12 months old), and (c) have had zero or very few prior audits. Feeds the `VAULT_CONTEXT.md` Phase 2a pipeline in the Dewaxindo Workspace vault so picked candidates flow directly into DewaxGuard scans without re-typing metadata.

Plan: `~/.claude/plans/warm-bubbling-dragonfly.md`

## Setup

**Prerequisites**: Python 3.11+, `pass` + GPG (for secret storage), `gh` CLI.

```bash
git clone git@github.com:BadGenius22/tvl-scanner.git
cd tvl-scanner
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Secrets** are stored in `pass` under the `tvl-scanner/` prefix. Required for v1:

```bash
pass insert --echo tvl-scanner/github      # fine-grained PAT, Public Repositories (read-only)
pass insert --echo tvl-scanner/birdeye     # https://docs.birdeye.so
```

Optional for v2:

```bash
pass insert --echo tvl-scanner/alchemy     # https://www.alchemy.com
pass insert --echo tvl-scanner/etherscan   # https://etherscan.io/apis
pass insert --echo tvl-scanner/dune        # https://dune.com/docs/api/
```

Verify:

```bash
pass ls tvl-scanner/
```

## Usage

```bash
# v1 manual run
python -m tvl_scanner run --chains solana,arbitrum,base --min-tvl 100000

# view latest report
cat reports/$(ls -t reports | head -1)
```

Output: `reports/YYYY-MM-DD-scan.md` (summary) + `reports/YYYY-MM-DD-scan/candidates/*.md` (per-candidate YAML records for Phase 2a lifting).

## Architecture

Four sequential stages, each producing a JSON artifact:

```
[Stage 1: Discover]  → artifacts/candidates.json
[Stage 2: Enrich]    → artifacts/enriched.json
[Stage 3: Audit-check] → artifacts/audit_status.json
[Stage 4: Rank]      → reports/YYYY-MM-DD-scan.md + candidates/
```

See the plan file for the full design.

## Vault integration (Phase 2a handoff)

When you pick a candidate, say in Claude Code:

> `new audit on <slug> at /home/dewaxindo/audit/<date>-<slug>/`

Stage A of the vault's audit-file workflow reads the per-candidate file at `reports/YYYY-MM-DD-scan/candidates/<rank>-<slug>.md`, lifts its YAML fields into a `VAULT_CONTEXT.md` draft, and proposes it for approval per the Phase 2a safety gates. Scanner does not touch the vault directly.

## Development

```bash
pytest                       # run tests
ruff check src/              # lint
mypy src/                    # type check
```

## Status

**v1 (in progress)**: GeckoTerminal + Birdeye discovery, GitHub + DefiLlama enrichment, C4/Sherlock/Cantina audit-check, priority formula, dual output.
