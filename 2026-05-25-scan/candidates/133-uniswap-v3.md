---
target_name: uniswap-v3
display_name: Uniswap V3
protocol_type: Dexs on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 20
audit_sources_found:
- source: defillama
  url: https://github.com/Uniswap/uniswap-v3-core/tree/main/audits
  title: null
  published_at: null
- source: defillama
  url: https://github.com/Uniswap/uniswap-v3-periphery/tree/main/audits
  title: null
  published_at: null
- source: defillama
  url: https://github.com/ConsenSys/Uniswap-audit-report-2018-12
  title: null
  published_at: null
- source: github_audits_folder
  url: https://github.com/Uniswap/v3-core/tree/HEAD/audits
  title: null
  published_at: null
- source: bounty_trust
  url: https://cantina.xyz/competitions/uniswap
  title: Trusted via cantina bounty (max $2,250,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
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
  title: Name 'uniswap-v3' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (0d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($1,421,200 TVL) — favor impact-driven finding scoping
bounty_program: cantina
bounty_url: https://cantina.xyz/competitions/uniswap
bounty_max_payout_usd: 2250000
tvl_usd: 1421200.733
first_seen: '2026-05-25'
age_days: 0
unique_users_30d: 60
github_repo: https://github.com/Uniswap/v3-core
loc_estimate: 16887
docs_url: null
primary_contract: ethereum:0x010dba86222fa9ea17af0c6ec59569f009ba9d1d
priority_score: 5.11
why_interesting: 'Dexs on ethereum • $1,421,200 TVL • 0d old • ~16887 LOC • audit_density=20
  • bounty: cantina'
scan_date: '2026-05-25'
is_verified: true
contract_name: UniswapV3Pool
is_proxy: false
proxy_impl_address: null
compiler_version: v0.7.6+commit.7338295f
defillama_audit_count: 2
defillama_audit_note: null
---

# Uniswap V3

> Dexs on ethereum • $1,421,200 TVL • 0d old • ~16887 LOC • audit_density=20 • bounty: cantina

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:0x010dba86222fa9ea17af0c6ec59569f009ba9d1d`
- **TVL**: $1.4M (1,421,200)
- **Age**: 0d (first seen 2026-05-25)
- **Unique users 30d**: 60
- **LOC estimate**: ~16,887
- **GitHub**: https://github.com/Uniswap/v3-core
- **Languages**: solidity

## On-chain verification (Etherscan V2)

- **Status**: ✓ Verified
- **Contract name**: `UniswapV3Pool`
- **Compiler**: `v0.7.6+commit.7338295f`

## Bounty program

- **Platform**: cantina
- **URL**: https://cantina.xyz/competitions/uniswap
- **Max payout**: $2,250,000

## Audit history

- **Audit density score**: 20 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/uniswap-v3 detail)
- Sources found:
  - `defillama` (1pt): https://github.com/Uniswap/uniswap-v3-core/tree/main/audits
  - `defillama` (1pt): https://github.com/Uniswap/uniswap-v3-periphery/tree/main/audits
  - `defillama` (1pt): https://github.com/ConsenSys/Uniswap-audit-report-2018-12
  - `github_audits_folder` (1pt): https://github.com/Uniswap/v3-core/tree/HEAD/audits
  - `bounty_trust` (4pt): Trusted via cantina bounty (max $2,250,000) — bounty platforms vet protocols against audit reports during onboarding
  - `factory_attribution` (4pt): Verified source identifier 'UniswapV3Pool' matches known audited protocol family — audit attribution by source
  - `factory_attribution` (4pt): factory() returns Uniswap V3 factory (0x1f98431c8ad98523631ae4a59f267346ea31f984) — pool of audited upstream protocol uniswap-v3
  - `factory_attribution` (4pt): Name 'uniswap-v3' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.11 / 10
  - tvl: 5.8 × 0.25
  - freshness: 10.0 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 4.5 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Brand-new contract (0d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($1,421,200 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on uniswap-v3 at ~/audit/2026-05-25-uniswap-v3/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
