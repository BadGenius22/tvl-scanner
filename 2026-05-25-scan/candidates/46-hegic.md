---
target_name: hegic
display_name: Hegic
protocol_type: Options on arbitrum
languages:
- solidity
chains:
- arbitrum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://github.com/peckshield/publications/blob/master/audit_reports/PeckShield-Audit-Report-Hegic-v1.0.pdf
  title: null
  published_at: null
- source: defillama
  url: https://github.com/hegic/contracts/blob/main/packages/herge/docs/PeckShield-Audit-Report-Hegic-Herge-Protocol-Upgrade-v1.0.pdf
  title: null
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($10,070,227 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 10070227.096504029
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: arbitrum:defillama:hegic
priority_score: 6.06
why_interesting: Options on arbitrum • $10,070,227 TVL • 180d old • audit_density=2
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Hegic

> Options on arbitrum • $10,070,227 TVL • 180d old • audit_density=2

## Summary

- **Chain**: arbitrum
- **Primary contract**: `arbitrum:defillama:hegic`
- **TVL**: $10.1M (10,070,227)
- **Age**: 6mo (first seen 2025-11-26)
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/hegic detail)
- Sources found:
  - `defillama` (1pt): https://github.com/peckshield/publications/blob/master/audit_reports/PeckShield-Audit-Report-Hegic-v1.0.pdf
  - `defillama` (1pt): https://github.com/hegic/contracts/blob/main/packages/herge/docs/PeckShield-Audit-Report-Hegic-Herge-Protocol-Upgrade-v1.0.pdf

## Priority breakdown

- **Composite**: 6.06 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($10,070,227 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on hegic at ~/audit/2026-05-25-hegic/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
