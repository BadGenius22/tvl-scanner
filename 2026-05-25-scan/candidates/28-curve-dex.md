---
target_name: curve-dex
display_name: Curve DEX
protocol_type: Dexs on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 14
audit_sources_found:
- source: defillama
  url: https://docs.curve.finance/references/audits/
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: bounty_trust
  url: https://immunefi.com/bounty/curve/
  title: Trusted via immunefi bounty (max $250,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
- source: factory_attribution
  url: null
  title: Verified source identifier 'Curve.Fi' matches known audited protocol family
    — audit attribution by source
  published_at: null
- source: factory_attribution
  url: null
  title: Name 'curve-dex' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (0d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($35,972,175 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/curve/
bounty_max_payout_usd: 250000
tvl_usd: 35972175.6327
first_seen: '2026-05-25'
age_days: 0
unique_users_30d: 60
github_repo: https://github.com/curvefi/curve-contract
loc_estimate: 195
docs_url: null
primary_contract: ethereum:0x862cb4e988fb66e72f128d1183829f8c05b6c6a0
priority_score: 6.17
why_interesting: 'Dexs on ethereum • $35,972,175 TVL • 0d old • ~195 LOC • audit_density=14
  • bounty: immunefi'
scan_date: '2026-05-25'
is_verified: true
contract_name: Twocrypto
is_proxy: false
proxy_impl_address: null
compiler_version: vyper:0.4.3
defillama_audit_count: 2
defillama_audit_note: null
---

# Curve DEX

> Dexs on ethereum • $35,972,175 TVL • 0d old • ~195 LOC • audit_density=14 • bounty: immunefi

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:0x862cb4e988fb66e72f128d1183829f8c05b6c6a0`
- **TVL**: $36.0M (35,972,175)
- **Age**: 0d (first seen 2026-05-25)
- **Unique users 30d**: 60
- **LOC estimate**: ~195
- **GitHub**: https://github.com/curvefi/curve-contract
- **Languages**: solidity

## On-chain verification (Etherscan V2)

- **Status**: ✓ Verified
- **Contract name**: `Twocrypto`
- **Compiler**: `vyper:0.4.3`

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/curve/
- **Max payout**: $250,000

## Audit history

- **Audit density score**: 14 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/curve-dex detail)
- Sources found:
  - `defillama` (1pt): https://docs.curve.finance/references/audits/
  - `defillama` (1pt): DefiLlama audit (no link)
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $250,000) — bounty platforms vet protocols against audit reports during onboarding
  - `factory_attribution` (4pt): Verified source identifier 'Curve.Fi' matches known audited protocol family — audit attribution by source
  - `factory_attribution` (4pt): Name 'curve-dex' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 6.17 / 10
  - tvl: 10.0 × 0.25
  - freshness: 10.0 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 4.5 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Brand-new contract (0d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($35,972,175 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on curve-dex at ~/audit/2026-05-25-curve-dex/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
