---
target_name: dango-bridge
display_name: Dango Bridge
protocol_type: Bridge on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 4
audit_sources_found:
- source: factory_attribution
  url: null
  title: Name 'dango-bridge' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (41d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($3,877,602 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 3877602.8656186503
first_seen: '2026-04-15'
age_days: 41
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:dango-bridge
priority_score: 5.11
why_interesting: Bridge on ethereum • $3,877,602 TVL • 41d old • audit_density=4
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Dango Bridge

> Bridge on ethereum • $3,877,602 TVL • 41d old • audit_density=4

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:dango-bridge`
- **TVL**: $3.9M (3,877,602)
- **Age**: 1mo (first seen 2026-04-15)
- **Languages**: solidity

## Audit history

- **Audit density score**: 4 (already audited)
- **DefiLlama audit count**: 0 (from /protocol/dango-bridge detail)
- Sources found:
  - `factory_attribution` (4pt): Name 'dango-bridge' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.11 / 10
  - tvl: 7.9 × 0.25
  - freshness: 8.9 × 0.20
  - audit_gap: 2.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (41d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($3,877,602 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on dango-bridge at ~/audit/2026-05-26-dango-bridge/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
