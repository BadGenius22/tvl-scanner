---
target_name: beefy
display_name: Beefy
protocol_type: Yield Aggregator on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 6
audit_sources_found:
- source: defillama
  url: https://github.com/beefyfinance/beefy-audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: bounty_trust
  url: https://immunefi.com/bounty/beefyfinance/
  title: Trusted via immunefi bounty (max $100,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($124,736,952 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/beefyfinance/
bounty_max_payout_usd: 100000
tvl_usd: 124736952.37870541
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/beefyfinance/beefy-contracts
loc_estimate: 181266
docs_url: null
primary_contract: ethereum:defillama:beefy
priority_score: 5.26
why_interesting: 'Yield Aggregator on ethereum • $124,736,952 TVL • 180d old • ~181266
  LOC • audit_density=6 • bounty: immunefi'
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Beefy

> Yield Aggregator on ethereum • $124,736,952 TVL • 180d old • ~181266 LOC • audit_density=6 • bounty: immunefi

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:beefy`
- **TVL**: $124.7M (124,736,952)
- **Age**: 6mo (first seen 2025-11-27)
- **LOC estimate**: ~181,266
- **GitHub**: https://github.com/beefyfinance/beefy-contracts
- **Languages**: solidity

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/beefyfinance/
- **Max payout**: $100,000

## Audit history

- **Audit density score**: 6 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/beefy detail)
- Sources found:
  - `defillama` (1pt): https://github.com/beefyfinance/beefy-audits
  - `defillama` (1pt): DefiLlama audit (no link)
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $100,000) — bounty platforms vet protocols against audit reports during onboarding

## Priority breakdown

- **Composite**: 5.26 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Real money at stake ($124,736,952 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on beefy at ~/audit/2026-05-26-beefy/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
