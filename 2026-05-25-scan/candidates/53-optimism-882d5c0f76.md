---
target_name: optimism-882d5c0f76
display_name: optimism:0x882d5c0f…
protocol_type: unknown protocol on optimism
languages:
- solidity
chains:
- optimism
inferred_platform: private
inferred_mode: private
audit_density_score: 0
audit_sources_found: []
under_audited: true
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (41d old) — check initialization racing, first-caller bootstrap
  invariants
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 239011.60368537117
first_seen: '2026-04-14'
age_days: 41
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: optimism:0x882d5c0f76faf5ef6b44844b1db1e294c5eed685
priority_score: 6.0
why_interesting: unknown protocol on optimism • $239,011 TVL • 41d old • no prior
  audits found
scan_date: '2026-05-25'
is_verified: true
contract_name: CLPool
is_proxy: false
proxy_impl_address: null
compiler_version: v0.7.6+commit.7338295f
defillama_audit_count: null
defillama_audit_note: null
---

# optimism:0x882d5c0f…

> unknown protocol on optimism • $239,011 TVL • 41d old • no prior audits found

## Summary

- **Chain**: optimism
- **Primary contract**: `optimism:0x882d5c0f76faf5ef6b44844b1db1e294c5eed685`
- **TVL**: $239K (239,011)
- **Age**: 1mo (first seen 2026-04-14)
- **Languages**: solidity

## On-chain verification (Etherscan V2)

- **Status**: ✓ Verified
- **Contract name**: `CLPool`
- **Compiler**: `v0.7.6+commit.7338295f`

## Audit history

- **Audit density score**: 0 (under-audited)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 6.00 / 10
  - tvl: 1.9 × 0.25
  - freshness: 8.9 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (41d old) — check initialization racing, first-caller bootstrap invariants
- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on optimism-882d5c0f76 at ~/audit/2026-05-25-optimism-882d5c0f76/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
