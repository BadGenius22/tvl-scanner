---
target_name: hakka-finance
display_name: Hakka Finance
protocol_type: Derivatives on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 1
audit_sources_found:
- source: defillama
  url: https://github.com/hakkafinance/audit-reports
  title: null
  published_at: null
under_audited: true
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($4,649,026 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 4649026.858084613
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:hakka-finance
priority_score: 6.25
why_interesting: Derivatives on ethereum • $4,649,026 TVL • 180d old • audit_density=1
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: null
defillama_audit_note: null
---

# Hakka Finance

> Derivatives on ethereum • $4,649,026 TVL • 180d old • audit_density=1

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:hakka-finance`
- **TVL**: $4.6M (4,649,026)
- **Age**: 6mo (first seen 2025-11-26)
- **Languages**: solidity

## Audit history

- **Audit density score**: 1 (under-audited)
- Sources found:
  - `defillama` (1pt): https://github.com/hakkafinance/audit-reports

## Priority breakdown

- **Composite**: 6.25 / 10
  - tvl: 8.3 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 8.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($4,649,026 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on hakka-finance at ~/audit/2026-05-25-hakka-finance/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
