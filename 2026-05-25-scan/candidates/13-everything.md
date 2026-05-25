---
target_name: everything
display_name: Everything
protocol_type: Lending on arbitrum
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
- Brand-new contract (40d old) — check initialization racing, first-caller bootstrap
  invariants
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 578739.8877241766
first_seen: '2026-04-15'
age_days: 40
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: arbitrum:defillama:everything
priority_score: 6.48
why_interesting: Lending on arbitrum • $578,739 TVL • 40d old • no prior audits found
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Everything

> Lending on arbitrum • $578,739 TVL • 40d old • no prior audits found

## Summary

- **Chain**: arbitrum
- **Primary contract**: `arbitrum:defillama:everything`
- **TVL**: $579K (578,739)
- **Age**: 1mo (first seen 2026-04-15)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/everything detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 6.48 / 10
  - tvl: 3.8 × 0.25
  - freshness: 8.9 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (40d old) — check initialization racing, first-caller bootstrap invariants
- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on everything at ~/audit/2026-05-25-everything/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
