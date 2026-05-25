---
target_name: convex-finance
display_name: Convex Finance
protocol_type: Yield on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 6
audit_sources_found:
- source: defillama
  url: https://github.com/convex-eth/platform/blob/main/audit/Convex%20Platform%20Security%20Audit%20Report.pdf
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: bounty_trust
  url: https://immunefi.com/bounty/convexfinance/
  title: Trusted via immunefi bounty (max $1,000,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($578,406,444 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/convexfinance/
bounty_max_payout_usd: 1000000
tvl_usd: 578406444.6213148
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/convex-eth/platform
loc_estimate: 40709
docs_url: null
primary_contract: ethereum:defillama:convex-finance
priority_score: 5.26
why_interesting: 'Yield on ethereum • $578,406,444 TVL • 180d old • ~40709 LOC • audit_density=6
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

# Convex Finance

> Yield on ethereum • $578,406,444 TVL • 180d old • ~40709 LOC • audit_density=6 • bounty: immunefi

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:convex-finance`
- **TVL**: $578.4M (578,406,444)
- **Age**: 6mo (first seen 2025-11-26)
- **LOC estimate**: ~40,709
- **GitHub**: https://github.com/convex-eth/platform
- **Languages**: solidity

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/convexfinance/
- **Max payout**: $1,000,000

## Audit history

- **Audit density score**: 6 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/convex-finance detail)
- Sources found:
  - `defillama` (1pt): https://github.com/convex-eth/platform/blob/main/audit/Convex%20Platform%20Security%20Audit%20Report.pdf
  - `defillama` (1pt): DefiLlama audit (no link)
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $1,000,000) — bounty platforms vet protocols against audit reports during onboarding

## Priority breakdown

- **Composite**: 5.26 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Real money at stake ($578,406,444 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on convex-finance at ~/audit/2026-05-25-convex-finance/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
