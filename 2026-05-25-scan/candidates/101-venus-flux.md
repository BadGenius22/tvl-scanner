---
target_name: venus-flux
display_name: Venus Flux
protocol_type: Lending on bsc
languages:
- solidity
chains:
- bsc
inferred_platform: private
inferred_mode: private
audit_density_score: 4
audit_sources_found:
- source: factory_attribution
  url: null
  title: Name 'venus-flux' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($16,051,444 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 16051444.31385518
first_seen: '2026-03-05'
age_days: 81
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: bsc:defillama:venus-flux
priority_score: 5.41
why_interesting: Lending on bsc • $16,051,444 TVL • 81d old • audit_density=4
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Venus Flux

> Lending on bsc • $16,051,444 TVL • 81d old • audit_density=4

## Summary

- **Chain**: bsc
- **Primary contract**: `bsc:defillama:venus-flux`
- **TVL**: $16.1M (16,051,444)
- **Age**: 2mo (first seen 2026-03-05)
- **Languages**: solidity

## Audit history

- **Audit density score**: 4 (already audited)
- **DefiLlama audit count**: 0 (from /protocol/venus-flux detail)
- Sources found:
  - `factory_attribution` (4pt): Name 'venus-flux' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.41 / 10
  - tvl: 10.0 × 0.25
  - freshness: 7.8 × 0.20
  - audit_gap: 2.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($16,051,444 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on venus-flux at ~/audit/2026-05-25-venus-flux/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
