---
target_name: polygon-389f8b632b
display_name: polygon:0x389f8b63…
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
- 'EIP-1967 proxy detected → implementation at `0x498236f2591194985d6ba318885dcfcc6ad6a5bf`.
  Audit BOTH slots: the proxy itself (upgrade authority, initializer guard) and the
  current implementation. Check for upgrade race conditions and uninitialized slot
  exploits.'
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 810499.0497573768
first_seen: '2025-11-25'
age_days: 181
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: polygon:0x389f8b632b7770951d791da4d8edb9f258623aef
priority_score: 5.89
why_interesting: unknown protocol on polygon • $810,499 TVL • 181d old • no prior
  audits found
scan_date: '2026-05-25'
is_verified: true
contract_name: TransparentUpgradeableProxy
is_proxy: true
proxy_impl_address: '0x498236f2591194985d6ba318885dcfcc6ad6a5bf'
compiler_version: v0.8.9+commit.e5eed63a
defillama_audit_count: null
defillama_audit_note: null
---

# polygon:0x389f8b63…

> unknown protocol on polygon • $810,499 TVL • 181d old • no prior audits found

## Summary

- **Chain**: polygon
- **Primary contract**: `polygon:0x389f8b632b7770951d791da4d8edb9f258623aef`
- **TVL**: $810K (810,499)
- **Age**: 6mo (first seen 2025-11-25)
- **Languages**: solidity

## On-chain verification (Etherscan V2)

- **Status**: ✓ Verified
- **Contract name**: `TransparentUpgradeableProxy`
- **Compiler**: `v0.8.9+commit.e5eed63a`
- **Proxy**: ✓ EIP-1967 proxy detected → impl `0x498236f2591194985d6ba318885dcfcc6ad6a5bf`
  - ⚠ When auditing, check BOTH the proxy and the implementation. Unverified implementation behind a verified proxy is a common obfuscation pattern.

## Audit history

- **Audit density score**: 0 (under-audited)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.89 / 10
  - tvl: 4.5 × 0.25
  - freshness: 5.0 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- EIP-1967 proxy detected → implementation at `0x498236f2591194985d6ba318885dcfcc6ad6a5bf`. Audit BOTH slots: the proxy itself (upgrade authority, initializer guard) and the current implementation. Check for upgrade race conditions and uninitialized slot exploits.
- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on polygon-389f8b632b at ~/audit/2026-05-25-polygon-389f8b632b/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
