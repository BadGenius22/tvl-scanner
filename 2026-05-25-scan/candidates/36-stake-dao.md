---
target_name: stake-dao
display_name: Stake DAO
protocol_type: Yield on ethereum
languages:
- solidity
- rust
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://docs.stakedao.org/audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($157,681,197 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 157681197.39265418
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/stake-dao/votemarket-sp1
loc_estimate: 6119
docs_url: null
primary_contract: ethereum:defillama:stake-dao
priority_score: 6.06
why_interesting: Yield on ethereum • $157,681,197 TVL • 180d old • ~6119 LOC • audit_density=2
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Stake DAO

> Yield on ethereum • $157,681,197 TVL • 180d old • ~6119 LOC • audit_density=2

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:stake-dao`
- **TVL**: $157.7M (157,681,197)
- **Age**: 6mo (first seen 2025-11-26)
- **LOC estimate**: ~6,119
- **GitHub**: https://github.com/stake-dao/votemarket-sp1
- **Languages**: solidity, rust

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/stake-dao detail)
- Sources found:
  - `defillama` (1pt): https://docs.stakedao.org/audits
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 6.06 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($157,681,197 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on stake-dao at ~/audit/2026-05-25-stake-dao/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
