---
target_name: ethereum-be62ca06ba
display_name: ethereum:0xbe62ca06…
protocol_type: unknown protocol on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 4
audit_sources_found:
- source: factory_attribution
  url: null
  title: Verified source identifier 'Richard Meissner -' matches known audited protocol
    family — audit attribution by source
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- 'EIP-1967 proxy detected → implementation at `0x41675c099f32341bf84bfc5382af534df5c7461a`.
  Audit BOTH slots: the proxy itself (upgrade authority, initializer guard) and the
  current implementation. Check for upgrade race conditions and uninitialized slot
  exploits.'
- Real money at stake ($6,443,539 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 6443539.478519731
first_seen: '2026-02-27'
age_days: 87
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:0xbe62ca06ba4b03055b4d859ea6fc38fbef28019e
priority_score: 5.13
why_interesting: unknown protocol on ethereum • $6,443,539 TVL • 87d old • audit_density=4
scan_date: '2026-05-25'
is_verified: true
contract_name: SafeProxy
is_proxy: true
proxy_impl_address: '0x41675c099f32341bf84bfc5382af534df5c7461a'
compiler_version: v0.7.6+commit.7338295f
defillama_audit_count: null
defillama_audit_note: null
---

# ethereum:0xbe62ca06…

> unknown protocol on ethereum • $6,443,539 TVL • 87d old • audit_density=4

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:0xbe62ca06ba4b03055b4d859ea6fc38fbef28019e`
- **TVL**: $6.4M (6,443,539)
- **Age**: 2mo (first seen 2026-02-27)
- **Languages**: solidity

## On-chain verification (Etherscan V2)

- **Status**: ✓ Verified
- **Contract name**: `SafeProxy`
- **Compiler**: `v0.7.6+commit.7338295f`
- **Proxy**: ✓ EIP-1967 proxy detected → impl `0x41675c099f32341bf84bfc5382af534df5c7461a`
  - ⚠ When auditing, check BOTH the proxy and the implementation. Unverified implementation behind a verified proxy is a common obfuscation pattern.

## Audit history

- **Audit density score**: 4 (already audited)
- Sources found:
  - `factory_attribution` (4pt): Verified source identifier 'Richard Meissner -' matches known audited protocol family — audit attribution by source

## Priority breakdown

- **Composite**: 5.13 / 10
  - tvl: 9.1 × 0.25
  - freshness: 7.6 × 0.20
  - audit_gap: 2.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- EIP-1967 proxy detected → implementation at `0x41675c099f32341bf84bfc5382af534df5c7461a`. Audit BOTH slots: the proxy itself (upgrade authority, initializer guard) and the current implementation. Check for upgrade race conditions and uninitialized slot exploits.
- Real money at stake ($6,443,539 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on ethereum-be62ca06ba at ~/audit/2026-05-25-ethereum-be62ca06ba/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
