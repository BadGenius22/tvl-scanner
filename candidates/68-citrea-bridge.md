---
target_name: citrea-bridge
display_name: Citrea Bridge
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
  title: Name 'citrea-bridge' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($6,705,019 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 6705019.667165597
first_seen: '2026-02-03'
age_days: 112
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:citrea-bridge
priority_score: 5.02
why_interesting: Bridge on ethereum • $6,705,019 TVL • 112d old • audit_density=4
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Citrea Bridge

> Bridge on ethereum • $6,705,019 TVL • 112d old • audit_density=4

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:citrea-bridge`
- **TVL**: $6.7M (6,705,019)
- **Age**: 3mo (first seen 2026-02-03)
- **Languages**: solidity

## Audit history

- **Audit density score**: 4 (already audited)
- **DefiLlama audit count**: 0 (from /protocol/citrea-bridge detail)
- Sources found:
  - `factory_attribution` (4pt): Name 'citrea-bridge' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.02 / 10
  - tvl: 9.1 × 0.25
  - freshness: 6.9 × 0.20
  - audit_gap: 2.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($6,705,019 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on citrea-bridge at ~/audit/2026-05-26-citrea-bridge/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
