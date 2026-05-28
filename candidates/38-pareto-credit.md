---
target_name: pareto-credit
display_name: Pareto Credit
protocol_type: RWA Lending on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://docs.pareto.credit/developers/security/audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($182,089,344 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 182089344.55495274
first_seen: '2025-07-14'
age_days: 316
unique_users_30d: null
github_repo: https://github.com/pareto-credit/USP
loc_estimate: 8026
docs_url: null
primary_contract: ethereum:defillama:pareto-credit
priority_score: 5.32
why_interesting: RWA Lending on ethereum • $182,089,344 TVL • 316d old • ~8026 LOC
  • audit_density=2
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Pareto Credit

> RWA Lending on ethereum • $182,089,344 TVL • 316d old • ~8026 LOC • audit_density=2

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:pareto-credit`
- **TVL**: $182.1M (182,089,344)
- **Age**: 10mo (first seen 2025-07-14)
- **LOC estimate**: ~8,026
- **GitHub**: https://github.com/pareto-credit/USP
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/pareto-credit detail)
- Sources found:
  - `defillama` (1pt): https://docs.pareto.credit/developers/security/audits
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 5.32 / 10
  - tvl: 10.0 × 0.25
  - freshness: 1.3 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($182,089,344 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on pareto-credit at ~/audit/2026-05-26-pareto-credit/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
