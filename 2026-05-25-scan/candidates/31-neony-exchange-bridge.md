---
target_name: neony-exchange-bridge
display_name: Neony Exchange Bridge
protocol_type: Bridge on solana
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
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 410928.04695930565
first_seen: '2026-03-16'
age_days: 70
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: solana:defillama:neony-exchange-bridge
priority_score: 6.13
why_interesting: Bridge on solana • $410,928 TVL • 70d old • no prior audits found
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Neony Exchange Bridge

> Bridge on solana • $410,928 TVL • 70d old • no prior audits found

## Summary

- **Chain**: solana
- **Primary contract**: `solana:defillama:neony-exchange-bridge`
- **TVL**: $411K (410,928)
- **Age**: 2mo (first seen 2026-03-16)
- **Languages**: rust

## Reproducible build (OtterSec)

- **Status**: — Not registered in OtterSec
  - This is the default for most Solana programs (<20% are registered). NOT a red flag — but you cannot trust that the github_repo matches the deployed bytecode byte-for-byte without running `solana-verify` yourself.

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/neony-exchange-bridge detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 6.13 / 10
  - tvl: 3.1 × 0.25
  - freshness: 8.1 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on neony-exchange-bridge at ~/audit/2026-05-25-neony-exchange-bridge/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
