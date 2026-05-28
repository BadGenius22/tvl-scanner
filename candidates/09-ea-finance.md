---
audited_by_me: '2026-05-27'
audit_outcome: 'HIGH: claimRewards has no solvency check — late stakers lose principal as reward accrual outruns the ~8.8K wCC buffer (~44 days runway). Self-triggering by time alone, no admin compromise needed. POC-PASS on BSC fork (single claim creates 11K wCC deficit; 3 claims over 2yrs create 82K deficit). 1 Low (admin retroactive rate change) + 10 Info. Owner is single EOA (no multisig). Report at /Users/dewaxindo/Documents/Work/Audit/tvl-scanner-targets/2026-05-27-ea-finance/AUDIT_REPORT.md'
real_onchain_tvl_usd: 408195
real_onchain_tvl_source: 'BSC publicnode RPC: balanceOf(0x23EbC3770f98c01EDAB20eb1eF17Ee633c19b467)=2594791.98 wCC; staking.getContractInfo() returns totalStaked=2576271.44 wCC, totalFees=9716.62 wCC, buffer=8803.92 wCC; DefiLlama-equivalent ~$408K at CC peg'
contract_pattern: 'StakingRewardsWCC (505 LOC) + wCC LayerZero V2 OFT (custom 140 LOC over OZ + LZ). Plain non-proxy contracts. Owner is EOA 0x0a06...6b5b (single-key). Canton Bridge mint/burn dead code (0 RoleGranted events). Only LZ peer: Base eid 30184.'
target_name: ea-finance
display_name: EA Finance
protocol_type: Liquid Restaking on bsc
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
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 420608.2932762147
first_seen: '2026-01-15'
age_days: 131
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: bsc:defillama:ea-finance
priority_score: 5.81
why_interesting: Liquid Restaking on bsc • $420,608 TVL • 131d old • no prior audits
  found
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# EA Finance

> Liquid Restaking on bsc • $420,608 TVL • 131d old • no prior audits found

## Summary

- **Chain**: bsc
- **Primary contract**: `bsc:defillama:ea-finance`
- **TVL**: $421K (420,608)
- **Age**: 4mo (first seen 2026-01-15)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/ea-finance detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.81 / 10
  - tvl: 3.1 × 0.25
  - freshness: 6.4 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on ea-finance at ~/audit/2026-05-26-ea-finance/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
