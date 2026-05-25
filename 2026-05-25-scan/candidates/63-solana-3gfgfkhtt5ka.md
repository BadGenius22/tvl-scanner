---
target_name: solana-3gfgfkhtt5ka
display_name: pump_amm
protocol_type: unknown protocol on solana
languages:
- rust
chains:
- solana
inferred_platform: private
inferred_mode: private
audit_density_score: 0
audit_sources_found: []
under_audited: true
edge_match_keywords: []
focus_areas_suggested:
- Not registered in OtterSec verified-builds DB (default for most Solana programs).
  If this candidate progresses to audit, run `solana-verify` yourself to confirm the
  github_repo commit matches the deployed bytecode before starting.
- Brand-new contract (0d old) — check initialization racing, first-caller bootstrap
  invariants
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 126164.3979120132
first_seen: '2026-05-25'
age_days: 0
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: solana:3GFGFkhTt5kahf5R6KXAPZD49AUwS9urkqpWSGiQ12BV
priority_score: 5.88
why_interesting: unknown protocol on solana • $126,164 TVL • 0d old • no prior audits
  found
scan_date: '2026-05-25'
is_verified: false
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: null
defillama_audit_note: null
---

# pump_amm

> unknown protocol on solana • $126,164 TVL • 0d old • no prior audits found

## Summary

- **Chain**: solana
- **Primary contract**: `solana:3GFGFkhTt5kahf5R6KXAPZD49AUwS9urkqpWSGiQ12BV`
- **TVL**: $126K (126,164)
- **Age**: 0d (first seen 2026-05-25)
- **Languages**: rust

## Reproducible build (OtterSec)

- **Status**: — Not registered in OtterSec
  - This is the default for most Solana programs (<20% are registered). NOT a red flag — but you cannot trust that the github_repo matches the deployed bytecode byte-for-byte without running `solana-verify` yourself.

## Audit history

- **Audit density score**: 0 (under-audited)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.88 / 10
  - tvl: 0.5 × 0.25
  - freshness: 10.0 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Not registered in OtterSec verified-builds DB (default for most Solana programs). If this candidate progresses to audit, run `solana-verify` yourself to confirm the github_repo commit matches the deployed bytecode before starting.
- Brand-new contract (0d old) — check initialization racing, first-caller bootstrap invariants
- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on solana-3gfgfkhtt5ka at ~/audit/2026-05-25-solana-3gfgfkhtt5ka/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
