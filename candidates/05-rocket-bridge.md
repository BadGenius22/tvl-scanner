---
audited_by_me: '2026-05-27'
audit_outcome: 'CLEAN under filter — 0 Critical/High/Med/Low, 10 Informational defense-in-depth (no balance-delta, no MIN_VALIDATORS floor, no rate limit, sticky-votes×live-quorum coupling, validator-supplied nonce w/o source-chain anchor, no destination-chainId, etc). All drain paths require admin/UPGRADER compromise, validator-majority collusion, or external validatorSet bug — all OUT of user filter. Bridge.sol is 225 LOC, tight code. Report at /Users/dewaxindo/Documents/Work/Audit/tvl-scanner-targets/2026-05-27-rocket-bridge/AUDIT_REPORT.md'
real_onchain_tvl_usd: 221089
real_onchain_tvl_source: 'Arbitrum RPC eth_call balanceOf(0xde26aeE5...c8f2) — pure USDC, matches DefiLlama'
contract_pattern: 'EIP-1967 proxy → OZ UUPS v5 impl 0xa982aa25...da7c (Sourcify full_match); AccessControl + Pausable + ReentrancyGuard; validator-multisig withdrawal bridge; 225 LOC in scope'
target_name: rocket-bridge
display_name: Rocket Bridge
protocol_type: Bridge on arbitrum
languages:
- solidity
chains:
- arbitrum
inferred_platform: private
inferred_mode: private
audit_density_score: 0
audit_sources_found: []
under_audited: true
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (56d old) — check initialization racing, first-caller bootstrap
  invariants
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 221014.45536066388
first_seen: '2026-03-31'
age_days: 56
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: arbitrum:defillama:rocket-bridge
priority_score: 5.87
why_interesting: Bridge on arbitrum • $221,014 TVL • 56d old • no prior audits found
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Rocket Bridge

> Bridge on arbitrum • $221,014 TVL • 56d old • no prior audits found

## Summary

- **Chain**: arbitrum
- **Primary contract**: `arbitrum:defillama:rocket-bridge`
- **TVL**: $221K (221,014)
- **Age**: 1mo (first seen 2026-03-31)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/rocket-bridge detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.87 / 10
  - tvl: 1.7 × 0.25
  - freshness: 8.5 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (56d old) — check initialization racing, first-caller bootstrap invariants
- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on rocket-bridge at ~/audit/2026-05-26-rocket-bridge/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
