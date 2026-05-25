---
target_name: arche
display_name: Arche
protocol_type: Yield on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://github.com/Kann-Audits/Kann-Audits/blob/main/reports/pdf-format/Arche-security-review-2026-05-03.pdf
  title: null
  published_at: null
- source: defillama
  url: https://github.com/yieldarche/arche-audits/blob/main/reports/sherlock-arche-money-collaborative-audit-2026-05-11.pdf
  title: null
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (33d old) — check initialization racing, first-caller bootstrap
  invariants
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 563433.7163894202
first_seen: '2026-04-22'
age_days: 33
unique_users_30d: null
github_repo: https://github.com/yieldarche/arche-audits
loc_estimate: 0
docs_url: null
primary_contract: ethereum:defillama:arche
priority_score: 5.31
why_interesting: Yield on ethereum • $563,433 TVL • 33d old • audit_density=2
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Arche

> Yield on ethereum • $563,433 TVL • 33d old • audit_density=2

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:arche`
- **TVL**: $563K (563,433)
- **Age**: 1mo (first seen 2026-04-22)
- **GitHub**: https://github.com/yieldarche/arche-audits
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/arche detail)
- Sources found:
  - `defillama` (1pt): https://github.com/Kann-Audits/Kann-Audits/blob/main/reports/pdf-format/Arche-security-review-2026-05-03.pdf
  - `defillama` (1pt): https://github.com/yieldarche/arche-audits/blob/main/reports/sherlock-arche-money-collaborative-audit-2026-05-11.pdf

## Priority breakdown

- **Composite**: 5.31 / 10
  - tvl: 3.8 × 0.25
  - freshness: 9.1 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (33d old) — check initialization racing, first-caller bootstrap invariants

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on arche at ~/audit/2026-05-25-arche/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
