---
target_name: spark-savings
display_name: Spark Savings
protocol_type: Yield on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 9
audit_sources_found:
- source: github_audits_folder
  url: https://github.com/sparkdotfi/spark-psm/tree/HEAD/audits
  title: null
  published_at: null
- source: bounty_trust
  url: https://immunefi.com/bounty/spark/
  title: Trusted via immunefi bounty (max $5,000,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
- source: factory_attribution
  url: null
  title: Name 'spark-savings' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($2,165,733,227 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/spark/
bounty_max_payout_usd: 5000000
tvl_usd: 2165733227.5886664
first_seen: '2025-09-12'
age_days: 256
unique_users_30d: null
github_repo: https://github.com/sparkdotfi/spark-psm
loc_estimate: 9213
docs_url: null
primary_contract: ethereum:defillama:spark-savings
priority_score: 4.85
why_interesting: 'Yield on ethereum • $2,165,733,227 TVL • 256d old • ~9213 LOC •
  audit_density=9 • bounty: immunefi'
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Spark Savings

> Yield on ethereum • $2,165,733,227 TVL • 256d old • ~9213 LOC • audit_density=9 • bounty: immunefi

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:spark-savings`
- **TVL**: $2165.7M (2,165,733,227)
- **Age**: 8mo (first seen 2025-09-12)
- **LOC estimate**: ~9,213
- **GitHub**: https://github.com/sparkdotfi/spark-psm
- **Languages**: solidity

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/spark/
- **Max payout**: $5,000,000

## Audit history

- **Audit density score**: 9 (already audited)
- **DefiLlama audit count**: 0 (from /protocol/spark-savings detail)
- Sources found:
  - `github_audits_folder` (1pt): https://github.com/sparkdotfi/spark-psm/tree/HEAD/audits
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $5,000,000) — bounty platforms vet protocols against audit reports during onboarding
  - `factory_attribution` (4pt): Name 'spark-savings' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 4.85 / 10
  - tvl: 10.0 × 0.25
  - freshness: 3.0 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Real money at stake ($2,165,733,227 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on spark-savings at ~/audit/2026-05-26-spark-savings/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
