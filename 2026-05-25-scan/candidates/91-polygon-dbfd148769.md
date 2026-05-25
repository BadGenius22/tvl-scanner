---
target_name: polygon-dbfd148769
display_name: Uniswap V4 (Polygon)
protocol_type: unknown protocol on polygon
languages:
- solidity
chains:
- polygon
inferred_platform: private
inferred_mode: private
audit_density_score: 4
audit_sources_found:
- source: factory_attribution
  url: null
  title: Name 'uniswap' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- ⚠ UNVERIFIED on Etherscan — source code is not public. Confirm the team has a plan
  to verify before committing audit time; auditing unverified bytecode is rarely productive.
- Brand-new contract (2d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($1,311,506 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 1311506.0888
first_seen: '2026-05-23'
age_days: 2
unique_users_30d: 11700
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: polygon:0xdbfd148769a661e366afc3fcf9c953e4da23fec718fe39c29e1769b0922a33c4
priority_score: 5.49
why_interesting: unknown protocol on polygon • $1,311,506 TVL • 2d old • audit_density=4
scan_date: '2026-05-25'
is_verified: false
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: null
defillama_audit_note: null
---

# Uniswap V4 (Polygon)

> unknown protocol on polygon • $1,311,506 TVL • 2d old • audit_density=4

## Summary

- **Chain**: polygon
- **Primary contract**: `polygon:0xdbfd148769a661e366afc3fcf9c953e4da23fec718fe39c29e1769b0922a33c4`
- **TVL**: $1.3M (1,311,506)
- **Age**: 2d (first seen 2026-05-23)
- **Unique users 30d**: 11,700
- **Languages**: solidity

## On-chain verification (Etherscan V2)

- **Status**: ✗ UNVERIFIED
  - ⚠ **Red flag**: the deployed bytecode is not verified on Etherscan. Either the team hasn't verified yet (ultra-fresh deployment) or they're hiding source. Do not audit without source — confirm the team has a plan to verify before committing time.

## Audit history

- **Audit density score**: 4 (already audited)
- Sources found:
  - `factory_attribution` (4pt): Name 'uniswap' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.49 / 10
  - tvl: 5.6 × 0.25
  - freshness: 9.9 × 0.20
  - audit_gap: 2.0 × 0.30
  - activity: 10.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- ⚠ UNVERIFIED on Etherscan — source code is not public. Confirm the team has a plan to verify before committing audit time; auditing unverified bytecode is rarely productive.
- Brand-new contract (2d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($1,311,506 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on polygon-dbfd148769 at ~/audit/2026-05-25-polygon-dbfd148769/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
