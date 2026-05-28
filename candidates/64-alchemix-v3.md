---
target_name: alchemix-v3
display_name: Alchemix V3
protocol_type: Synthetics on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 6
audit_sources_found:
- source: defillama
  url: https://github.com/runtimeverification/publications/blob/main/reports/smart-contracts/Alchemix_v3.pdf
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: factory_attribution
  url: null
  title: Name 'alchemix-v3' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (32d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($35,451,381 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 35451381.11003903
first_seen: '2026-04-24'
age_days: 32
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:alchemix-v3
priority_score: 5.07
why_interesting: Synthetics on ethereum • $35,451,381 TVL • 32d old • audit_density=6
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Alchemix V3

> Synthetics on ethereum • $35,451,381 TVL • 32d old • audit_density=6

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:alchemix-v3`
- **TVL**: $35.5M (35,451,381)
- **Age**: 1mo (first seen 2026-04-24)
- **Languages**: solidity

## Audit history

- **Audit density score**: 6 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/alchemix-v3 detail)
- Sources found:
  - `defillama` (1pt): https://github.com/runtimeverification/publications/blob/main/reports/smart-contracts/Alchemix_v3.pdf
  - `defillama` (1pt): DefiLlama audit (no link)
  - `factory_attribution` (4pt): Name 'alchemix-v3' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.07 / 10
  - tvl: 10.0 × 0.25
  - freshness: 9.1 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (32d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($35,451,381 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on alchemix-v3 at ~/audit/2026-05-26-alchemix-v3/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
