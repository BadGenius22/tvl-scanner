---
target_name: tranchess-yield
display_name: Tranchess Yield
protocol_type: Yield on bsc
languages:
- solidity
chains:
- bsc
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://github.com/peckshield/publications/blob/master/audit_reports/PeckShield-Audit-Report-Tranchess-v1.0.pdf
  title: null
  published_at: null
- source: defillama
  url: https://www.certik.org/projects/tranchess
  title: null
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($5,715,735 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 5715735.725166125
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: bsc:defillama:tranchess-yield
priority_score: 5.76
why_interesting: Yield on bsc • $5,715,735 TVL • 180d old • audit_density=2
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Tranchess Yield

> Yield on bsc • $5,715,735 TVL • 180d old • audit_density=2

## Summary

- **Chain**: bsc
- **Primary contract**: `bsc:defillama:tranchess-yield`
- **TVL**: $5.7M (5,715,735)
- **Age**: 6mo (first seen 2025-11-27)
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/tranchess-yield detail)
- Sources found:
  - `defillama` (1pt): https://github.com/peckshield/publications/blob/master/audit_reports/PeckShield-Audit-Report-Tranchess-v1.0.pdf
  - `defillama` (1pt): https://www.certik.org/projects/tranchess

## Priority breakdown

- **Composite**: 5.76 / 10
  - tvl: 8.8 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($5,715,735 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on tranchess-yield at ~/audit/2026-05-26-tranchess-yield/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
