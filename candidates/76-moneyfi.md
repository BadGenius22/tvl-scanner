---
target_name: moneyfi
display_name: MoneyFi
protocol_type: Yield Aggregator on base
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
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 684036.0372643231
first_seen: '2025-07-01'
age_days: 329
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: base:defillama:moneyfi
priority_score: 4.99
why_interesting: Yield Aggregator on base • $684,036 TVL • 329d old • no prior audits
  found
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# MoneyFi

> Yield Aggregator on base • $684,036 TVL • 329d old • no prior audits found

## Summary

- **Chain**: base
- **Primary contract**: `base:defillama:moneyfi`
- **TVL**: $684K (684,036)
- **Age**: 10mo (first seen 2025-07-01)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/moneyfi detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 4.99 / 10
  - tvl: 4.2 × 0.25
  - freshness: 1.0 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on moneyfi at ~/audit/2026-05-26-moneyfi/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
