---
target_name: rho-x-lp-vault
display_name: Rho X LP Vault
protocol_type: Yield on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 0
audit_sources_found: []
under_audited: true
edge_match_keywords:
- vault
focus_areas_suggested:
- Audit share/asset conversion math carefully; first-depositor share inflation is
  common in vault patterns
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 956863.1753634012
first_seen: '2026-02-04'
age_days: 110
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:rho-x-lp-vault
priority_score: 6.87
why_interesting: 'Yield on ethereum • $956,863 TVL • 110d old • no prior audits found
  • edge-match: vault'
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Rho X LP Vault

> Yield on ethereum • $956,863 TVL • 110d old • no prior audits found • edge-match: vault

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:rho-x-lp-vault`
- **TVL**: $957K (956,863)
- **Age**: 3mo (first seen 2026-02-04)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/rho-x-lp-vault detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 6.87 / 10
  - tvl: 4.9 × 0.25
  - freshness: 7.0 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 5.0 × 0.10 (keywords: vault)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Audit share/asset conversion math carefully; first-depositor share inflation is common in vault patterns
- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on rho-x-lp-vault at ~/audit/2026-05-25-rho-x-lp-vault/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
