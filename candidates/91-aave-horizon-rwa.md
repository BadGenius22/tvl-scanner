---
target_name: aave-horizon-rwa
display_name: Aave Horizon RWA
protocol_type: RWA Lending on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 6
audit_sources_found:
- source: defillama
  url: https://github.com/aave/aave-v3-horizon/tree/main/audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: factory_attribution
  url: null
  title: Name 'aave-horizon-rwa' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords:
- aave
focus_areas_suggested:
- Check integration seams with external lending/yield primitive — cross-protocol trust
  boundary
- Real money at stake ($345,686,603 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 345686603.0449461
first_seen: '2025-12-10'
age_days: 167
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:aave-horizon-rwa
priority_score: 4.83
why_interesting: 'RWA Lending on ethereum • $345,686,603 TVL • 167d old • audit_density=6
  • edge-match: aave'
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Aave Horizon RWA

> RWA Lending on ethereum • $345,686,603 TVL • 167d old • audit_density=6 • edge-match: aave

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:aave-horizon-rwa`
- **TVL**: $345.7M (345,686,603)
- **Age**: 5mo (first seen 2025-12-10)
- **Languages**: solidity

## Audit history

- **Audit density score**: 6 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/aave-horizon-rwa detail)
- Sources found:
  - `defillama` (1pt): https://github.com/aave/aave-v3-horizon/tree/main/audits
  - `defillama` (1pt): DefiLlama audit (no link)
  - `factory_attribution` (4pt): Name 'aave-horizon-rwa' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 4.83 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.4 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 5.0 × 0.10 (keywords: aave)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Check integration seams with external lending/yield primitive — cross-protocol trust boundary
- Real money at stake ($345,686,603 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on aave-horizon-rwa at ~/audit/2026-05-26-aave-horizon-rwa/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
