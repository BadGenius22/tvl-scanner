---
target_name: hyperlane
display_name: Hyperlane
protocol_type: Cross Chain Bridge on bsc
languages:
- solidity
- rust
chains:
- bsc
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 8
audit_sources_found:
- source: bounty_trust
  url: https://immunefi.com/bounty/hyperlane/
  title: Trusted via immunefi bounty (max $2,500,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
- source: factory_attribution
  url: null
  title: Name 'hyperlane' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($145,514,843 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/hyperlane/
bounty_max_payout_usd: 2500000
tvl_usd: 145514843.7159093
first_seen: '2026-02-27'
age_days: 88
unique_users_30d: null
github_repo: https://github.com/hyperlane-xyz/hyperlane-monorepo
loc_estimate: 624427
docs_url: null
primary_contract: bsc:defillama:hyperlane
priority_score: 5.77
why_interesting: 'Cross Chain Bridge on bsc • $145,514,843 TVL • 88d old • ~624427
  LOC • audit_density=8 • bounty: immunefi'
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Hyperlane

> Cross Chain Bridge on bsc • $145,514,843 TVL • 88d old • ~624427 LOC • audit_density=8 • bounty: immunefi

## Summary

- **Chain**: bsc
- **Primary contract**: `bsc:defillama:hyperlane`
- **TVL**: $145.5M (145,514,843)
- **Age**: 2mo (first seen 2026-02-27)
- **LOC estimate**: ~624,427
- **GitHub**: https://github.com/hyperlane-xyz/hyperlane-monorepo
- **Languages**: solidity, rust

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/hyperlane/
- **Max payout**: $2,500,000

## Audit history

- **Audit density score**: 8 (already audited)
- **DefiLlama audit count**: 0 (from /protocol/hyperlane detail)
- Sources found:
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $2,500,000) — bounty platforms vet protocols against audit reports during onboarding
  - `factory_attribution` (4pt): Name 'hyperlane' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.77 / 10
  - tvl: 10.0 × 0.25
  - freshness: 7.6 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Real money at stake ($145,514,843 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on hyperlane at ~/audit/2026-05-26-hyperlane/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
