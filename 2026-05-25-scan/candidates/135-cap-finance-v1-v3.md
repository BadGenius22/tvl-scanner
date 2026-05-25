---
target_name: cap-finance-v1-v3
display_name: Cap Finance v1-v3
protocol_type: Derivatives on arbitrum
languages:
- solidity
chains:
- arbitrum
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
tvl_usd: 189067.65989730635
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: arbitrum:defillama:cap-finance-v1-v3
priority_score: 5.11
why_interesting: Derivatives on arbitrum • $189,067 TVL • 180d old • no prior audits
  found
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Cap Finance v1-v3

> Derivatives on arbitrum • $189,067 TVL • 180d old • no prior audits found

## Summary

- **Chain**: arbitrum
- **Primary contract**: `arbitrum:defillama:cap-finance-v1-v3`
- **TVL**: $189K (189,067)
- **Age**: 6mo (first seen 2025-11-26)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/cap-finance-v1-v3 detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.11 / 10
  - tvl: 1.4 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on cap-finance-v1-v3 at ~/audit/2026-05-25-cap-finance-v1-v3/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
