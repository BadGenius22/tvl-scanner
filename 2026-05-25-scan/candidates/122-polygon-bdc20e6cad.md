---
target_name: polygon-bdc20e6cad
display_name: polygon:0xbdc20e6c…
protocol_type: unknown protocol on polygon
languages:
- solidity
chains:
- polygon
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
tvl_usd: 193900.91171723048
first_seen: '2025-12-17'
age_days: 159
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: polygon:0xbdc20e6cad7962acf934bcdba62c32f4c6423d7a
priority_score: 5.24
why_interesting: unknown protocol on polygon • $193,900 TVL • 159d old • no prior
  audits found
scan_date: '2026-05-25'
is_verified: true
contract_name: TurboWallet
is_proxy: false
proxy_impl_address: null
compiler_version: v0.8.30+commit.73712a01
defillama_audit_count: null
defillama_audit_note: null
---

# polygon:0xbdc20e6c…

> unknown protocol on polygon • $193,900 TVL • 159d old • no prior audits found

## Summary

- **Chain**: polygon
- **Primary contract**: `polygon:0xbdc20e6cad7962acf934bcdba62c32f4c6423d7a`
- **TVL**: $194K (193,900)
- **Age**: 5mo (first seen 2025-12-17)
- **Languages**: solidity

## On-chain verification (Etherscan V2)

- **Status**: ✓ Verified
- **Contract name**: `TurboWallet`
- **Compiler**: `v0.8.30+commit.73712a01`

## Audit history

- **Audit density score**: 0 (under-audited)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.24 / 10
  - tvl: 1.4 × 0.25
  - freshness: 5.6 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on polygon-bdc20e6cad at ~/audit/2026-05-25-polygon-bdc20e6cad/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
