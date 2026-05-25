---
target_name: atomiq-exchange
display_name: atomiq exchange
protocol_type: Cross Chain Bridge on solana
languages:
- rust
chains:
- solana
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
tvl_usd: 265578.44542617165
first_seen: '2026-02-17'
age_days: 97
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: solana:defillama:atomiq-exchange
priority_score: 5.75
why_interesting: Cross Chain Bridge on solana • $265,578 TVL • 97d old • no prior
  audits found
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# atomiq exchange

> Cross Chain Bridge on solana • $265,578 TVL • 97d old • no prior audits found

## Summary

- **Chain**: solana
- **Primary contract**: `solana:defillama:atomiq-exchange`
- **TVL**: $266K (265,578)
- **Age**: 3mo (first seen 2026-02-17)
- **Languages**: rust

## Reproducible build (OtterSec)

- **Status**: — Not registered in OtterSec
  - This is the default for most Solana programs (<20% are registered). NOT a red flag — but you cannot trust that the github_repo matches the deployed bytecode byte-for-byte without running `solana-verify` yourself.

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/atomiq-exchange detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.75 / 10
  - tvl: 2.1 × 0.25
  - freshness: 7.3 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on atomiq-exchange at ~/audit/2026-05-25-atomiq-exchange/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
