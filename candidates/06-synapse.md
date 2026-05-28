---
target_name: synapse
display_name: Synapse
protocol_type: Cross Chain Bridge on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 4
audit_sources_found:
- source: bounty_trust
  url: https://immunefi.com/bounty/synapseprotocol/
  title: Trusted via immunefi bounty (max $1,000,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($16,824,882 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/synapseprotocol/
bounty_max_payout_usd: 1000000
tvl_usd: 16824882.053063534
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/synapsecns/sanguine
loc_estimate: 246192
docs_url: null
primary_contract: ethereum:defillama:synapse
priority_score: 5.86
why_interesting: 'Cross Chain Bridge on ethereum • $16,824,882 TVL • 180d old • ~246192
  LOC • audit_density=4 • bounty: immunefi'
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Synapse

> Cross Chain Bridge on ethereum • $16,824,882 TVL • 180d old • ~246192 LOC • audit_density=4 • bounty: immunefi

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:synapse`
- **TVL**: $16.8M (16,824,882)
- **Age**: 6mo (first seen 2025-11-27)
- **LOC estimate**: ~246,192
- **GitHub**: https://github.com/synapsecns/sanguine
- **Languages**: solidity

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/synapseprotocol/
- **Max payout**: $1,000,000

## Audit history

- **Audit density score**: 4 (already audited)
- **DefiLlama audit count**: 0 (from /protocol/synapse detail)
- Sources found:
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $1,000,000) — bounty platforms vet protocols against audit reports during onboarding

## Priority breakdown

- **Composite**: 5.86 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 2.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Real money at stake ($16,824,882 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on synapse at ~/audit/2026-05-26-synapse/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
