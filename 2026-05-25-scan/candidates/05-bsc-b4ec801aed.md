---
target_name: bsc-b4ec801aed
display_name: FstSwap
protocol_type: unknown protocol on bsc
languages:
- solidity
chains:
- bsc
inferred_platform: private
inferred_mode: private
audit_density_score: 0
audit_sources_found: []
under_audited: true
edge_match_keywords: []
focus_areas_suggested:
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
- Real money at stake ($4,732,673 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 4732673.299968191
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: bsc:0xb4ec801aed8c92f2e69589518aaa127afb37d8c9
priority_score: 6.86
why_interesting: unknown protocol on bsc • $4,732,673 TVL • 180d old • no prior audits
  found
scan_date: '2026-05-25'
is_verified: true
contract_name: FstswapPair
is_proxy: false
proxy_impl_address: null
compiler_version: v0.5.16+commit.9c3226ce
defillama_audit_count: null
defillama_audit_note: null
---

# FstSwap

> unknown protocol on bsc • $4,732,673 TVL • 180d old • no prior audits found

## Summary

- **Chain**: bsc
- **Primary contract**: `bsc:0xb4ec801aed8c92f2e69589518aaa127afb37d8c9`
- **TVL**: $4.7M (4,732,673)
- **Age**: 6mo (first seen 2025-11-26)
- **Languages**: solidity

## On-chain verification (Etherscan V2)

- **Status**: ✓ Verified
- **Contract name**: `FstswapPair`
- **Compiler**: `v0.5.16+commit.9c3226ce`

## Audit history

- **Audit density score**: 0 (under-audited)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 6.86 / 10
  - tvl: 8.4 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth
- Real money at stake ($4,732,673 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on bsc-b4ec801aed at ~/audit/2026-05-25-bsc-b4ec801aed/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
