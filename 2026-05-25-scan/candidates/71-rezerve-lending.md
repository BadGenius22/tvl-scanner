---
target_name: rezerve-lending
display_name: Rezerve Lending
protocol_type: Lending on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 0
audit_sources_found: []
under_audited: true
edge_match_keywords: []
focus_areas_suggested:
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
- Real money at stake ($1,337,383 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 1337383.237327207
first_seen: '2025-09-16'
age_days: 251
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:rezerve-lending
priority_score: 5.78
why_interesting: Lending on ethereum • $1,337,383 TVL • 251d old • no prior audits
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

# Rezerve Lending

> Lending on ethereum • $1,337,383 TVL • 251d old • no prior audits found

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:rezerve-lending`
- **TVL**: $1.3M (1,337,383)
- **Age**: 8mo (first seen 2025-09-16)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/rezerve-lending detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.78 / 10
  - tvl: 5.6 × 0.25
  - freshness: 3.1 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth
- Real money at stake ($1,337,383 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on rezerve-lending at ~/audit/2026-05-25-rezerve-lending/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
