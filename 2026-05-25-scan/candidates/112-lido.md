---
target_name: lido
display_name: Lido
protocol_type: Liquid Staking on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 10
audit_sources_found:
- source: defillama
  url: https://github.com/lidofinance/audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: bounty_trust
  url: https://immunefi.com/bounty/lido/
  title: Trusted via immunefi bounty (max $2,000,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
- source: factory_attribution
  url: null
  title: Name 'lido' matches known audited protocol family — audit attribution by
    name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($18,735,164,102 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/lido/
bounty_max_payout_usd: 2000000
tvl_usd: 18735164102.90675
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:lido
priority_score: 5.26
why_interesting: 'Liquid Staking on ethereum • $18,735,164,102 TVL • 180d old • audit_density=10
  • bounty: immunefi'
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Lido

> Liquid Staking on ethereum • $18,735,164,102 TVL • 180d old • audit_density=10 • bounty: immunefi

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:lido`
- **TVL**: $18735.2M (18,735,164,102)
- **Age**: 6mo (first seen 2025-11-26)
- **Languages**: solidity

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/lido/
- **Max payout**: $2,000,000

## Audit history

- **Audit density score**: 10 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/lido detail)
- Sources found:
  - `defillama` (1pt): https://github.com/lidofinance/audits
  - `defillama` (1pt): DefiLlama audit (no link)
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $2,000,000) — bounty platforms vet protocols against audit reports during onboarding
  - `factory_attribution` (4pt): Name 'lido' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.26 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Real money at stake ($18,735,164,102 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on lido at ~/audit/2026-05-25-lido/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
