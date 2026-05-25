---
target_name: multichain
display_name: Multichain
protocol_type: Bridge on bsc
languages:
- solidity
chains:
- bsc
inferred_platform: private
inferred_mode: private
audit_density_score: 3
audit_sources_found:
- source: defillama
  url: https://github.com/anyswap/Anyswap-Audit/blob/master/TrailOfBits/Anyswap-CrossChain-Bridge-TrailofBits-Audit-Final%20Report.pdf
  title: null
  published_at: null
- source: defillama
  url: https://github.com/anyswap/Anyswap-Audit/blob/master/SlowMist/AnySwap%20CrossChain-Bridge%20Security%20Audit%20Report.pdf
  title: null
  published_at: null
- source: defillama
  url: https://github.com/anyswap/Anyswap-Audit/blob/master/SlowMist/Anyswap%20Smart%20Contract%20Security%20Audit.pdf
  title: null
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($44,796,152 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 44796152.76472669
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/Multichain-DAO/SBT-contract
loc_estimate: 1471
docs_url: null
primary_contract: bsc:defillama:multichain
priority_score: 5.46
why_interesting: Bridge on bsc • $44,796,152 TVL • 180d old • ~1471 LOC • audit_density=3
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Multichain

> Bridge on bsc • $44,796,152 TVL • 180d old • ~1471 LOC • audit_density=3

## Summary

- **Chain**: bsc
- **Primary contract**: `bsc:defillama:multichain`
- **TVL**: $44.8M (44,796,152)
- **Age**: 6mo (first seen 2025-11-26)
- **LOC estimate**: ~1,471
- **GitHub**: https://github.com/Multichain-DAO/SBT-contract
- **Languages**: solidity

## Audit history

- **Audit density score**: 3 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/multichain detail)
- Sources found:
  - `defillama` (1pt): https://github.com/anyswap/Anyswap-Audit/blob/master/TrailOfBits/Anyswap-CrossChain-Bridge-TrailofBits-Audit-Final%20Report.pdf
  - `defillama` (1pt): https://github.com/anyswap/Anyswap-Audit/blob/master/SlowMist/AnySwap%20CrossChain-Bridge%20Security%20Audit%20Report.pdf
  - `defillama` (1pt): https://github.com/anyswap/Anyswap-Audit/blob/master/SlowMist/Anyswap%20Smart%20Contract%20Security%20Audit.pdf

## Priority breakdown

- **Composite**: 5.46 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 4.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($44,796,152 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on multichain at ~/audit/2026-05-25-multichain/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
