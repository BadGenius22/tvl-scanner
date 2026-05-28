---
target_name: acre
display_name: Acre
protocol_type: Yield on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 4
audit_sources_found:
- source: homepage_scrape
  url: https://acre.fi/
  title: quantstamp audit cited on protocol homepage
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($4,306,163 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 4306163.810264772
first_seen: '2026-02-24'
age_days: 91
unique_users_30d: null
github_repo: https://github.com/acre-btc/acre
loc_estimate: 46066
docs_url: null
primary_contract: ethereum:defillama:acre
priority_score: 4.89
why_interesting: Yield on ethereum • $4,306,163 TVL • 91d old • ~46066 LOC • audit_density=4
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Acre

> Yield on ethereum • $4,306,163 TVL • 91d old • ~46066 LOC • audit_density=4

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:acre`
- **TVL**: $4.3M (4,306,163)
- **Age**: 3mo (first seen 2026-02-24)
- **LOC estimate**: ~46,066
- **GitHub**: https://github.com/acre-btc/acre
- **Languages**: solidity

## Audit history

- **Audit density score**: 4 (already audited)
- **DefiLlama audit count**: 0 (from /protocol/acre detail)
- Sources found:
  - `homepage_scrape` (4pt): quantstamp audit cited on protocol homepage

## Priority breakdown

- **Composite**: 4.89 / 10
  - tvl: 8.2 × 0.25
  - freshness: 7.5 × 0.20
  - audit_gap: 2.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($4,306,163 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on acre at ~/audit/2026-05-26-acre/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
