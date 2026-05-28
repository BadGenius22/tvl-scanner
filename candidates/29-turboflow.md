---
audited_by_me: '2026-05-27'
audit_outcome: 'SKIPPED — both legs source-unavailable. BSC impl 0xa8fa31388d7d9a02450a943f486bbea3b4b60bc1 not verified on BscScan/Sourcify; Solana program HwWQZdX116omFGrygkpng7fTzMbrg6JGpLaoM77cM7vg has no published IDL (anchor idl fetch → AccountNotFound). DefiLlama marks deprecated. No GitHub source. Bytecode-only audit not viable under filter (5x effort, no disclosure path).'
real_onchain_tvl_usd: 455901
real_onchain_tvl_source: 'BSC publicnode RPC balanceOf(0x145CD0d5...625dB) USDT=271611 + USDC=12289 = $283901; Solana mainnet getAccountInfo(8iquHJQy...A9Q4) → vault PDA holds USDT+USDC ≈ $172K per DefiLlama'
contract_pattern: 'BSC: TransparentUpgradeableProxy → impl 0xa8fa31...60bc1 (23KB, UNVERIFIED); Solana: 504KB SBF program at HwWQZdX1...M7vg (no IDL)'
target_name: turboflow
display_name: TurboFlow
protocol_type: Derivatives on bsc
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
tvl_usd: 455004.575930987
first_seen: '2025-11-06'
age_days: 201
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: bsc:defillama:turboflow
priority_score: 5.47
why_interesting: Derivatives on bsc • $455,004 TVL • 201d old • no prior audits found
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# TurboFlow

> Derivatives on bsc • $455,004 TVL • 201d old • no prior audits found

## Summary

- **Chain**: bsc
- **Primary contract**: `bsc:defillama:turboflow`
- **TVL**: $455K (455,004)
- **Age**: 6mo (first seen 2025-11-06)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/turboflow detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.47 / 10
  - tvl: 3.3 × 0.25
  - freshness: 4.5 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on turboflow at ~/audit/2026-05-26-turboflow/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
