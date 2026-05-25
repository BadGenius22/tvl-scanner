---
target_name: ledgity-yield
display_name: Ledgity Yield
protocol_type: Yield on base
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
- Brand-new contract (33d old) — check initialization racing, first-caller bootstrap
  invariants
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
- Real money at stake ($3,132,153 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 3132153.435709269
first_seen: '2026-04-22'
age_days: 33
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: base:defillama:ledgity-yield
priority_score: 7.44
why_interesting: Yield on base • $3,132,153 TVL • 33d old • no prior audits found
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Ledgity Yield

> Yield on base • $3,132,153 TVL • 33d old • no prior audits found

## Summary

- **Chain**: base
- **Primary contract**: `base:defillama:ledgity-yield`
- **TVL**: $3.1M (3,132,153)
- **Age**: 1mo (first seen 2026-04-22)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/ledgity-yield detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 7.44 / 10
  - tvl: 7.5 × 0.25
  - freshness: 9.1 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (33d old) — check initialization racing, first-caller bootstrap invariants
- No prior audits found in any source — start with standard sanity pass before specialized depth
- Real money at stake ($3,132,153 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on ledgity-yield at ~/audit/2026-05-25-ledgity-yield/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
