---
target_name: base-a9d51f7cf1
display_name: base:0xa9d51f7c…
protocol_type: unknown protocol on base
languages:
- solidity
chains:
- base
inferred_platform: private
inferred_mode: private
audit_density_score: 0
audit_sources_found: []
under_audited: true
edge_match_keywords: []
focus_areas_suggested:
- 'EIP-1967 proxy detected → implementation at `0x4d5b75471623d22f8d97fb0f20d29ae26cbc8e84`.
  Audit BOTH slots: the proxy itself (upgrade authority, initializer guard) and the
  current implementation. Check for upgrade race conditions and uninitialized slot
  exploits.'
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 623035.3057743495
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: base:0xa9d51f7cf1548bc6636bc405ef480fe502cc71a8
priority_score: 5.76
why_interesting: unknown protocol on base • $623,035 TVL • 180d old • no prior audits
  found
scan_date: '2026-05-25'
is_verified: true
contract_name: ERC1967Proxy
is_proxy: true
proxy_impl_address: '0x4d5b75471623d22f8d97fb0f20d29ae26cbc8e84'
compiler_version: v0.8.9+commit.e5eed63a
defillama_audit_count: null
defillama_audit_note: null
---

# base:0xa9d51f7c…

> unknown protocol on base • $623,035 TVL • 180d old • no prior audits found

## Summary

- **Chain**: base
- **Primary contract**: `base:0xa9d51f7cf1548bc6636bc405ef480fe502cc71a8`
- **TVL**: $623K (623,035)
- **Age**: 6mo (first seen 2025-11-26)
- **Languages**: solidity

## On-chain verification (Etherscan V2)

- **Status**: ✓ Verified
- **Contract name**: `ERC1967Proxy`
- **Compiler**: `v0.8.9+commit.e5eed63a`
- **Proxy**: ✓ EIP-1967 proxy detected → impl `0x4d5b75471623d22f8d97fb0f20d29ae26cbc8e84`
  - ⚠ When auditing, check BOTH the proxy and the implementation. Unverified implementation behind a verified proxy is a common obfuscation pattern.

## Audit history

- **Audit density score**: 0 (under-audited)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.76 / 10
  - tvl: 4.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- EIP-1967 proxy detected → implementation at `0x4d5b75471623d22f8d97fb0f20d29ae26cbc8e84`. Audit BOTH slots: the proxy itself (upgrade authority, initializer guard) and the current implementation. Check for upgrade race conditions and uninitialized slot exploits.
- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on base-a9d51f7cf1 at ~/audit/2026-05-25-base-a9d51f7cf1/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
