---
target_name: wepiggy
display_name: WePiggy
protocol_type: Lending on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://github.com/WePiggy/wepiggy-contracts/tree/master/docs/audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Standard breadth sweep on solidity code; no edge-match tailwinds
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 967574.8889552103
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/WePiggy/wepiggy-contracts
loc_estimate: 15319
docs_url: null
primary_contract: ethereum:defillama:wepiggy
priority_score: 4.8
why_interesting: Lending on ethereum • $967,574 TVL • 180d old • ~15319 LOC • audit_density=2
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# WePiggy

> Lending on ethereum • $967,574 TVL • 180d old • ~15319 LOC • audit_density=2

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:wepiggy`
- **TVL**: $968K (967,574)
- **Age**: 6mo (first seen 2025-11-27)
- **LOC estimate**: ~15,319
- **GitHub**: https://github.com/WePiggy/wepiggy-contracts
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/wepiggy detail)
- Sources found:
  - `defillama` (1pt): https://github.com/WePiggy/wepiggy-contracts/tree/master/docs/audits
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 4.80 / 10
  - tvl: 4.9 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Standard breadth sweep on solidity code; no edge-match tailwinds

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on wepiggy at ~/audit/2026-05-26-wepiggy/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
