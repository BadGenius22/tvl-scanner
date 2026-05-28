---
target_name: yfii
display_name: YFII
protocol_type: Yield Aggregator on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 1
audit_sources_found:
- source: defillama
  url: https://github.com/yfii/audit
  title: null
  published_at: null
under_audited: true
edge_match_keywords: []
focus_areas_suggested:
- Standard breadth sweep on solidity code; no edge-match tailwinds
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 391919.6874309803
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/yfii/yvault
loc_estimate: 67290
docs_url: null
primary_contract: ethereum:defillama:yfii
priority_score: 4.91
why_interesting: Yield Aggregator on ethereum • $391,919 TVL • 180d old • ~67290 LOC
  • audit_density=1
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 1
defillama_audit_note: null
---

# YFII

> Yield Aggregator on ethereum • $391,919 TVL • 180d old • ~67290 LOC • audit_density=1

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:yfii`
- **TVL**: $392K (391,919)
- **Age**: 6mo (first seen 2025-11-27)
- **LOC estimate**: ~67,290
- **GitHub**: https://github.com/yfii/yvault
- **Languages**: solidity

## Audit history

- **Audit density score**: 1 (under-audited)
- **DefiLlama audit count**: 1 (from /protocol/yfii detail)
- Sources found:
  - `defillama` (1pt): https://github.com/yfii/audit

## Priority breakdown

- **Composite**: 4.91 / 10
  - tvl: 3.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 8.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Standard breadth sweep on solidity code; no edge-match tailwinds

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on yfii at ~/audit/2026-05-26-yfii/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
