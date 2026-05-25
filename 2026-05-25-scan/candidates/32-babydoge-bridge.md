---
target_name: babydoge-bridge
display_name: BabyDoge Bridge
protocol_type: Bridge on bsc
languages:
- solidity
chains:
- bsc
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
tvl_usd: 634426.4448299028
first_seen: '2026-01-24'
age_days: 121
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: bsc:defillama:babydoge-bridge
priority_score: 6.09
why_interesting: Bridge on bsc • $634,426 TVL • 121d old • no prior audits found
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# BabyDoge Bridge

> Bridge on bsc • $634,426 TVL • 121d old • no prior audits found

## Summary

- **Chain**: bsc
- **Primary contract**: `bsc:defillama:babydoge-bridge`
- **TVL**: $634K (634,426)
- **Age**: 4mo (first seen 2026-01-24)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/babydoge-bridge detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 6.09 / 10
  - tvl: 4.0 × 0.25
  - freshness: 6.7 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on babydoge-bridge at ~/audit/2026-05-25-babydoge-bridge/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
