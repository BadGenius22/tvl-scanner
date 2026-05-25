---
target_name: maple
display_name: Maple
protocol_type: Lending on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 7
audit_sources_found:
- source: defillama
  url: https://github.com/maple-labs/maple-core#audit-reports
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: github_audits_folder
  url: https://github.com/maple-labs/maple-core-v2/tree/HEAD/audits
  title: null
  published_at: null
- source: bounty_trust
  url: https://immunefi.com/bounty/maplefinance/
  title: Trusted via immunefi bounty (max $500,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($1,936,130,488 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/maplefinance/
bounty_max_payout_usd: 500000
tvl_usd: 1936130488.6742113
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/maple-labs/maple-core-v2
loc_estimate: 76774
docs_url: null
primary_contract: ethereum:defillama:maple
priority_score: 5.26
why_interesting: 'Lending on ethereum • $1,936,130,488 TVL • 180d old • ~76774 LOC
  • audit_density=7 • bounty: immunefi'
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Maple

> Lending on ethereum • $1,936,130,488 TVL • 180d old • ~76774 LOC • audit_density=7 • bounty: immunefi

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:maple`
- **TVL**: $1936.1M (1,936,130,488)
- **Age**: 6mo (first seen 2025-11-26)
- **LOC estimate**: ~76,774
- **GitHub**: https://github.com/maple-labs/maple-core-v2
- **Languages**: solidity

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/maplefinance/
- **Max payout**: $500,000

## Audit history

- **Audit density score**: 7 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/maple detail)
- Sources found:
  - `defillama` (1pt): https://github.com/maple-labs/maple-core#audit-reports
  - `defillama` (1pt): DefiLlama audit (no link)
  - `github_audits_folder` (1pt): https://github.com/maple-labs/maple-core-v2/tree/HEAD/audits
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $500,000) — bounty platforms vet protocols against audit reports during onboarding

## Priority breakdown

- **Composite**: 5.26 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Real money at stake ($1,936,130,488 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on maple at ~/audit/2026-05-25-maple/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
