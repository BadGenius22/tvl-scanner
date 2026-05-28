---
target_name: surf-liquid
display_name: Surf Liquid
protocol_type: Yield on base
languages:
- solidity
chains:
- base
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
tvl_usd: 228445.2025167465
first_seen: '2025-09-25'
age_days: 243
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: base:defillama:surf-liquid
priority_score: 4.87
why_interesting: Yield on base • $228,445 TVL • 243d old • no prior audits found
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Surf Liquid

> Yield on base • $228,445 TVL • 243d old • no prior audits found

## Summary

- **Chain**: base
- **Primary contract**: `base:defillama:surf-liquid`
- **TVL**: $228K (228,445)
- **Age**: 8mo (first seen 2025-09-25)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/surf-liquid detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 4.87 / 10
  - tvl: 1.8 × 0.25
  - freshness: 3.3 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on surf-liquid at ~/audit/2026-05-26-surf-liquid/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
