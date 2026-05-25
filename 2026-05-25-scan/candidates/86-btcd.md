---
target_name: btcd
display_name: BTCD
protocol_type: Yield on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://docs.btcd.fi/security-and-audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (4d old) — check initialization racing, first-caller bootstrap
  invariants
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 746642.1197783775
first_seen: '2026-05-21'
age_days: 4
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:btcd
priority_score: 5.62
why_interesting: Yield on ethereum • $746,642 TVL • 4d old • audit_density=2
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# BTCD

> Yield on ethereum • $746,642 TVL • 4d old • audit_density=2

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:btcd`
- **TVL**: $747K (746,642)
- **Age**: 4d (first seen 2026-05-21)
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/btcd detail)
- Sources found:
  - `defillama` (1pt): https://docs.btcd.fi/security-and-audits
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 5.62 / 10
  - tvl: 4.4 × 0.25
  - freshness: 9.9 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (4d old) — check initialization racing, first-caller bootstrap invariants

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on btcd at ~/audit/2026-05-25-btcd/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
