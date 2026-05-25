---
target_name: stablehodl
display_name: StableHodl
protocol_type: Yield on polygon
languages:
- solidity
chains:
- polygon
inferred_platform: private
inferred_mode: private
audit_density_score: 0
audit_sources_found: []
under_audited: true
edge_match_keywords: []
focus_areas_suggested:
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
- Real money at stake ($6,958,056 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 6958056.579578877
first_seen: '2025-06-23'
age_days: 336
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: polygon:defillama:stablehodl
priority_score: 6.21
why_interesting: Yield on polygon • $6,958,056 TVL • 336d old • no prior audits found
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# StableHodl

> Yield on polygon • $6,958,056 TVL • 336d old • no prior audits found

## Summary

- **Chain**: polygon
- **Primary contract**: `polygon:defillama:stablehodl`
- **TVL**: $7.0M (6,958,056)
- **Age**: 11mo (first seen 2025-06-23)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/stablehodl detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 6.21 / 10
  - tvl: 9.2 × 0.25
  - freshness: 0.8 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth
- Real money at stake ($6,958,056 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on stablehodl at ~/audit/2026-05-25-stablehodl/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
