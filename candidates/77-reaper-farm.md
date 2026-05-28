---
target_name: reaper-farm
display_name: Reaper Farm
protocol_type: Yield Aggregator on bsc
languages:
- solidity
chains:
- bsc
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://solidity.finance/audits/ReaperFarm
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($1,368,544 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 1368544.7827431285
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: bsc:defillama:reaper-farm
priority_score: 4.98
why_interesting: Yield Aggregator on bsc • $1,368,544 TVL • 180d old • audit_density=2
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Reaper Farm

> Yield Aggregator on bsc • $1,368,544 TVL • 180d old • audit_density=2

## Summary

- **Chain**: bsc
- **Primary contract**: `bsc:defillama:reaper-farm`
- **TVL**: $1.4M (1,368,544)
- **Age**: 6mo (first seen 2025-11-27)
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/reaper-farm detail)
- Sources found:
  - `defillama` (1pt): https://solidity.finance/audits/ReaperFarm
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 4.98 / 10
  - tvl: 5.7 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($1,368,544 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on reaper-farm at ~/audit/2026-05-26-reaper-farm/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
