---
target_name: avalon-superearn
display_name: Avalon Superearn
protocol_type: Yield on ethereum
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
  title: Name 'avalon-superearn' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($30,416,318 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 30416318.040114623
first_seen: '2026-02-18'
age_days: 97
unique_users_30d: null
github_repo: https://github.com/avalonfinancexyz/website-ts
loc_estimate: 0
docs_url: null
primary_contract: ethereum:defillama:avalon-superearn
priority_score: 5.32
why_interesting: Yield on ethereum • $30,416,318 TVL • 97d old • audit_density=4
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Avalon Superearn

> Yield on ethereum • $30,416,318 TVL • 97d old • audit_density=4

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:avalon-superearn`
- **TVL**: $30.4M (30,416,318)
- **Age**: 3mo (first seen 2026-02-18)
- **GitHub**: https://github.com/avalonfinancexyz/website-ts
- **Languages**: solidity

## Audit history

- **Audit density score**: 4 (already audited)
- **DefiLlama audit count**: 0 (from /protocol/avalon-superearn detail)
- Sources found:
  - `factory_attribution` (4pt): Name 'avalon-superearn' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.32 / 10
  - tvl: 10.0 × 0.25
  - freshness: 7.3 × 0.20
  - audit_gap: 2.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($30,416,318 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on avalon-superearn at ~/audit/2026-05-26-avalon-superearn/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
