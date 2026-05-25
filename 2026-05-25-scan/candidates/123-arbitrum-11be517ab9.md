---
target_name: arbitrum-11be517ab9
display_name: Uniswap V3 (Arbitrum)
protocol_type: unknown protocol on arbitrum
languages:
- solidity
chains:
- arbitrum
inferred_platform: private
inferred_mode: private
audit_density_score: 12
audit_sources_found:
- source: factory_attribution
  url: null
  title: Verified source identifier 'UniswapV3Pool' matches known audited protocol
    family — audit attribution by source
  published_at: null
- source: factory_attribution
  url: https://github.com/Uniswap/v3-core/tree/main/audits
  title: factory() returns Uniswap V3 factory (0x1f98431c8ad98523631ae4a59f267346ea31f984)
    — pool of audited upstream protocol uniswap-v3
  published_at: null
- source: factory_attribution
  url: null
  title: Name 'uniswap' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (0d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($2,612,651,292 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 2612651292.6628
first_seen: '2026-05-25'
age_days: 0
unique_users_30d: 90
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: arbitrum:0x11be517ab9686b93c89b479267a9312fd09adf91
priority_score: 5.23
why_interesting: unknown protocol on arbitrum • $2,612,651,292 TVL • 0d old • audit_density=12
scan_date: '2026-05-25'
is_verified: true
contract_name: UniswapV3Pool
is_proxy: false
proxy_impl_address: null
compiler_version: v0.7.6+commit.7338295f
defillama_audit_count: null
defillama_audit_note: null
---

# Uniswap V3 (Arbitrum)

> unknown protocol on arbitrum • $2,612,651,292 TVL • 0d old • audit_density=12

## Summary

- **Chain**: arbitrum
- **Primary contract**: `arbitrum:0x11be517ab9686b93c89b479267a9312fd09adf91`
- **TVL**: $2612.7M (2,612,651,292)
- **Age**: 0d (first seen 2026-05-25)
- **Unique users 30d**: 90
- **Languages**: solidity

## On-chain verification (Etherscan V2)

- **Status**: ✓ Verified
- **Contract name**: `UniswapV3Pool`
- **Compiler**: `v0.7.6+commit.7338295f`

## Audit history

- **Audit density score**: 12 (already audited)
- Sources found:
  - `factory_attribution` (4pt): Verified source identifier 'UniswapV3Pool' matches known audited protocol family — audit attribution by source
  - `factory_attribution` (4pt): factory() returns Uniswap V3 factory (0x1f98431c8ad98523631ae4a59f267346ea31f984) — pool of audited upstream protocol uniswap-v3
  - `factory_attribution` (4pt): Name 'uniswap' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.23 / 10
  - tvl: 10.0 × 0.25
  - freshness: 10.0 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 4.9 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (0d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($2,612,651,292 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on arbitrum-11be517ab9 at ~/audit/2026-05-25-arbitrum-11be517ab9/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
